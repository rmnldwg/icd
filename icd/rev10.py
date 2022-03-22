"""
This module defines dataclasses that can parse, display and provide utilities 
for the ICD codex (10th revision). For convenience, data is provided in the 
`./data` directory, which is automatically parsed and made available as `codex` 
when `icd.rev10` is imported.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict

import untangle
import requests

from ._config import DATA_DIR


@dataclass
class ICD10Entry():
    """
    Base dataclass representing an ICD chapter, block or code of the 10th 
    ICD revision.
    """
    code: str
    """The chapter number, block range or ICD code of the entry."""
    title: str
    """Description of the chapter, block or diagnose."""
    _type: str
    parent: Optional[ICD10Entry] = field(default=None, repr=False)
    """Direct ancestor of the entry."""
    children: List[ICD10Entry] = field(default_factory=lambda: [], repr=False)
    """List of direct descendants of the entry."""
    
    def __str__(self):
        return f"{self._type} {self.code}: {self.title}"
    
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    @property
    def is_root(self) -> bool:
        return self.parent is None
    
    @property
    def _child_dict(self) -> Dict[str, ICD10Entry]:
        return {child.code: child for child in self.children}
    
    def tree(self, prefix="", maxdepth=None):
        """
        Render the current object and all descendants in a pretty tree.
        
        Args:
            prefix: This string will be prefixed to the output of every entry. 
                It should not be used directly, but is set by the recusion 
                algorithm automatically.
            maxdepth: Maximum depth of the tree that will be printed.
        
        Returns:
            The string containing the tree output. Use e.g. 
            `print(icd_chapter.tree())` to nicely visualize the output.
        """
        tree_str = f"{str(self)}\n"
        
        if isinstance(maxdepth, int) and maxdepth < 1:
            return tree_str
        elif isinstance(maxdepth, int):
            maxdepth = maxdepth - 1
        
        num_children = len(self.children)
        for i,child in enumerate(self.children):
            if i + 1 == num_children:
                branch = "└───"
                new_prefix = prefix + "    "
            else:
                branch = "├───"
                new_prefix = prefix + "│   "
            tree_str += prefix + branch + child.tree(new_prefix, maxdepth)
        return tree_str
            
    def add_child(self, new_child: ICD10Entry):
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
    
    def remove_child(self, child: ICD10Entry):
        """
        Remove `child` from `self.children` list in a cautios manner. This 
        means that if the child has already been added as some other object's 
        child and has hence already a new `parent` attribute, it won't be 
        deleted.
        """
        try:
            self.children.remove(child)
            if child.parent == self:
                child.parent = None
        except ValueError:
            pass
    
    def find(self, code: str, maxdepth: Optional[int] = None) -> ICD10Entry:
        """
        Find a given code in the tree.
        
        Args:
            code: The code that should be found inside the ICD tree. Can be a 
                chapter, block or diagnose.
            maxdepth: Maximum depth the recursion search will go into. If `None` 
                it will go down to all leaves.
        
        Returns:
            The entry (chapter, block, diagnose) if it matches, else `None`
        """
        if self.code == code:
            return self
        
        if maxdepth is not None and maxdepth < 1:
            return None
        
        for child in self.children:
            new_maxdepth = maxdepth - 1 if maxdepth is not None else None
            if (found := child.find(code, maxdepth=new_maxdepth)) is not None:
                return found
        
        return None


@dataclass
class ICD10Root(ICD10Entry):
    """
    Root of the ICD 10 tree. It serves as an entry point for the recursive 
    parsing of the XML data file and also stores the version of the data.
    """
    code: str = "ICD10"
    title: str = "10th revision of the International Classification of Disease"
    version: str = field(repr=False, default="")
    """Displays the version of the loaded ICD codex. E.g., 2022 for the version 
    including corrections made prior to the year 2022."""
    _type: str = field(repr=False, default="root")
    
    def __str__(self):
        return f"{self._type} {self.code} (v{self.version}): {self.title}"
    
    @classmethod
    def from_xml(cls, xml_root: untangle.Element) -> ICD10Root:
        """Create root and entire ICD tree from XML root entry."""
        root = cls(version=xml_root.version.cdata)        
        for xml_chapter in xml_root.chapter:
            root.add_child(ICD10Chapter.from_xml(xml_chapter))
        return root
    
    @property
    def chapter(self) -> ICD10Chapter:
        """Returns a dictionary containing all the ICD chapters loaded under a 
        roman-numeral key. E.g., chapter 2 can be accessed via something like 
        `root.chapter['II']`."""
        return self._child_dict


@dataclass
class ICD10Chapter(ICD10Entry):
    """
    One of the 22 chapters in the ICD codex. In the XML data obtained from the 
    [CDC](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2022/) 
    the chapter numbers are given in arabic numerals, but the WHO's API uses 
    roman numerals to identify chapters, so the `code` attribute is converted. 
    E.g., chapter `2` will be accessible from the root via `root.chapter['II']`.
    """
    _type: str = field(repr=False, default="chapter")
    
    def __post_init__(self):
        """Romanize chapter number."""
        units     = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
        tens      = ['', 'X', 'XX', 'XXX', 'XL', 'L', 'LX', 'LXX', 'LXXX', 'XC']
        hundrets  = ['', 'C', 'CC', 'CCC', 'CD', 'D', 'DC', 'DCC', 'DCCC', 'CM']
        thousands = ['', 'M', 'MM', 'MMM']
        try:
            chapter_num = int(self.code)
        except ValueError:
            raise ValueError("Chapter number must be integer")
        roman_num = thousands[chapter_num // 1000]
        chapter_num = chapter_num % 1000
        roman_num += hundrets[chapter_num // 100]
        chapter_num = chapter_num % 100
        roman_num += tens[chapter_num // 10]
        chapter_num = chapter_num % 10
        roman_num += units[chapter_num]
        self.code = roman_num
        
    @classmethod
    def from_xml(cls, xml_chapter: untangle.Element) -> ICD10Chapter:
        """Create chapter from respective XML chapter entry."""
        chapter = cls(
            code=xml_chapter.name.cdata,
            title=xml_chapter.desc.cdata,
        )
        for xml_section in xml_chapter.section:
            chapter.add_child(ICD10Block.from_xml(xml_section))
        
        return chapter
    
    @property
    def block(self) -> Dict[str, ICD10Block]:
        """Returns a dictionary containing all blocks loaded for this chapter 
        under a key corresponding to their ICD-range. E.g., block `C00-C96` 
        contains all diagnoses with codes ranging from `C00` to `C96`."""
        return self._child_dict


@dataclass
class ICD10Block(ICD10Entry):
    """
    A block of ICD codes within a chapter. A block specifies a range of ICD 
    codes that are described in that block. It may also contain other blocks, 
    not necessarily diagnoses as direct children. The `code` attribute of a 
    block might be something like `C00-C96`.
    """
    _type: str = field(repr=False, default="block")
    
    @property
    def start_code(self) -> str:
        """Returns the first ICD code included in this diagnose block."""
        return self.code.split("-")[0]
            
    @property
    def end_code(self) -> str:
        """Respectively returns the last ICD code of the block."""
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
    def block(self) -> ICD10Block:
        """Like :class:`ICD10Chapter`, a block might have blocks as children, 
        which can be accessed in the exact same way as for the chapter."""
        if len(self.children) > 0 and isinstance(self.children[0], ICD10Block):
            return self._child_dict
    
    @property
    def diagnose(self) -> ICD10Diagnose:
        """In case the block does not have blocks, but diagnoses as children, 
        they can be accessed via the `diagnose` attribute, which also returns a 
        dictionary, just like `block`."""
        if len(self.children) > 0 and isinstance(self.children[0], ICD10Diagnose):
            return self._child_dict
    
    def should_contain(self, block: ICD10Block) -> bool:
        """Check whether this block should contain the given block"""
        if self == block or block in self.children:
            return False
        
        has_start_ge = block.start_code >= self.start_code
        has_end_le = block.end_code <= self.end_code
        if has_start_ge and has_end_le:
            return True
        
        return False
    
    @classmethod
    def from_xml(cls, xml_section: untangle.Element) -> ICD10Block:
        """Create block of ICD diagnoses from XML section"""
        block = cls(
            code=xml_section["id"],
            title=xml_section.desc.cdata,
        )
        if hasattr(xml_section, "diag"):
            for xml_diag in xml_section.diag:
                block.add_child(ICD10Diagnose.from_xml(xml_diag))
        
        return block
    
    def find(self, code: str, maxdepth:int = None) -> ICD10Block:
        """Stop searching when code is surely not in block."""
        code_part = code.split(".")[0]
        if not (code_part >= self.start_code and code_part <= self.end_code):
            return None
        return super().find(code, maxdepth)


@dataclass
class ICD10Diagnose(ICD10Entry):
    """
    A diagnose of the ICD system. These are the only entries in the ICD codex 
    for which the `code` attribute actually holds a valid ICD code in the regex 
    form `[A-Z][0-9]{2}(.[0-9]{1,3})?`.
    """
    _type: str = field(repr=False, default="diagnose")
    
    @property
    def diagnose(self) -> ICD10Diagnose:
        """If there exists a finer classification of the diagnose, this 
        property returns them as a dictionary of respective ICDs as key and the 
        actual entry as value."""
        return self._child_dict
    
    @classmethod
    def from_xml(cls, xml_diag: untangle.Element) -> ICD10Diagnose:
        """Recursively create tree of diagnoses and subdiagnoses from XML."""
        diagnose = cls(
            code=xml_diag.name.cdata,
            title=xml_diag.desc.cdata,
        )
        if hasattr(xml_diag, "diag"):
            for xml_subdiag in xml_diag.diag:
                diagnose.add_child(ICD10Diagnose.from_xml(xml_subdiag))
        
        return diagnose


# Load the data and parse it
xml_file_path = os.path.join(DATA_DIR, "icd10cm_tabular_2022.xml")
xml_data = untangle.parse(xml_file_path).ICD10CM_tabular

codex = ICD10Root.from_xml(xml_data)
"""This is the entire ICD 10 CM codex, for convenience loaded from the
[CDC](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2022/)
in XML format. It can be accessed like this

```python
import icd.rev10

entire_icd10cm = icd.rev10.codex
```
"""