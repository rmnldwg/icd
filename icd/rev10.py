from dataclasses import dataclass, field
from typing import List, Optional

import untangle
import requests


@dataclass
class ICD10Entry():
    """
    Dataclass representing an ICD chapter, block or code of the 10th 
    ICD revision.
    """
    code: str
    title: str
    _type: str
    parent: Optional[object] = field(default=None, repr=False)
    children: List[object] = field(default_factory=lambda: [], repr=False)
    
    def __str__(self):
        return f"{self._type} {self.code}: {self.title}"
    
    @property
    def is_leaf(self):
        return len(self.children) == 0
    
    @property
    def is_root(self):
        return self.parent is None
    
    @property
    def _child_dict(self):
        return {child.code: child for child in self.children}
    
    def tree(self, prefix=""):
        tree_str = f"{prefix}{str(self)}\n"
        for child in self.children:
            new_prefix = prefix + "\t"
            tree_str += child.tree(prefix=new_prefix)
        return tree_str
            
    def add_child(self, new_child):
        """
        Add new child in a consistent manner. I.e., if the to-be-added child 
        is a block that would actually belong in an existing block, put it 
        there instead.
        """
        are_children_block = all(
            [isinstance(child, ICD10Block) for child in self.children]
        )
        if are_children_block and isinstance(new_child, ICD10Block):
            for block in self.children:
                if block.should_contain(new_child):
                    block.add_child(new_child)
                    return
                elif new_child.should_contain(block):
                    self.remove_child(block)
                    new_child.add_child(block)
        
        new_child.parent = self
        self.children.append(new_child)
    
    def remove_child(self, child):
        try:
            self.children.remove(child)
            if child.parent == self:
                child.parent = None
        except ValueError:
            pass

@dataclass
class ICD10Root(ICD10Entry):
    """
    Root of the ICD 10 tree.
    """
    code: str = "ICD10"
    title: str = "10th revision of the International Classification of Disease"
    _type: str = field(repr=False, default="root")
    
    @classmethod
    def from_xml(cls, xml_root: untangle.Element):
        """Create root and entire ICD tree from XML root entry."""
        root = cls()        
        for xml_chapter in xml_root.chapter:
            root.add_child(ICD10Chapter.from_xml(xml_chapter))
        return root
    
    @property
    def chapter(self):
        return self._child_dict


@dataclass
class ICD10Chapter(ICD10Entry):
    """
    One of 22 chapters of the ICD.
    """
    _type: str = field(repr=False, default="chapter")
    
    def __post_init__(self):
        # TODO: Romanize the chapter number
        self.code = self.code
        
    @classmethod
    def from_xml(cls, xml_chapter):
        """Create chapter from respective XML chapter entry."""
        chapter = cls(
            code=xml_chapter.name.cdata,
            title=xml_chapter.desc.cdata,
        )
        for xml_section in xml_chapter.section:
            chapter.add_child(ICD10Block.from_xml(xml_section))
        
        return chapter
    
    @property
    def block(self):
        return self._child_dict


@dataclass
class ICD10Block(ICD10Entry):
    """
    A block of ICD codes within a chapter.
    """
    _type: str = field(repr=False, default="block")
    
    @property
    def start_code(self):
        return self.code.split("-")[0]
            
    @property
    def end_code(self):
        split_code = self.code.split("-")
        if len(split_code) == 1:
            return self.start_code
        elif len(split_code) == 2:
            return split_code[1]
        else:
            raise ValueError(
                f"Block code must be <start_code>-<end_code> or only <code>, "
                "but not {self.code}"
            )
    
    @property
    def block(self):
        if len(self.children) > 0 and isinstance(self.children[0], ICD10Block):
            return self._child_dict
    
    @property
    def diagnose(self):
        if len(self.children) > 0 and isinstance(self.children[0], ICD10Diagnose):
            return self._child_dict
    
    def should_contain(self, block):
        """Check whether this block should contain the given block"""
        if self == block or block in self.children:
            return False
        
        has_start_ge = block.start_code >= self.start_code
        has_end_le = block.end_code <= self.end_code
        if has_start_ge and has_end_le:
            return True
        
        return False
    
    @classmethod
    def from_xml(cls, xml_section):
        """Create block of ICD diagnoses from XML section"""
        block = cls(
            code=xml_section["id"],
            title=xml_section.desc.cdata,
        )
        if hasattr(xml_section, "diag"):
            for xml_diag in xml_section.diag:
                block.add_child(ICD10Diagnose.from_xml(xml_diag))
        
        return block

@dataclass
class ICD10Diagnose(ICD10Entry):
    """
    A diagnose of the ICD system.
    """
    _type: str = field(repr=False, default="diagnose")
    
    @property
    def diagnose(self):
        return self._child_dict
    
    @classmethod
    def from_xml(cls, xml_diag):
        """Recursively create tree of diagnoses and subdiagnoses from XML."""
        diagnose = cls(
            code=xml_diag.name.cdata,
            title=xml_diag.desc.cdata,
        )
        if hasattr(xml_diag, "diag"):
            for xml_subdiag in xml_diag.diag:
                diagnose.add_child(ICD10Diagnose.from_xml(xml_subdiag))
        
        return diagnose