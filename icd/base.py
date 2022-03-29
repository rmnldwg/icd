"""
This module defines dataclasses that can parse, display and provide utilities 
for the International statistical classification of diseases and related health 
problems (10th revision).
"""
from __future__ import annotations
from multiprocessing.sharedctypes import Value
import os
from dataclasses import dataclass, field
from platform import release
from typing import List, Optional, Dict

import untangle
import requests
from tqdm import tqdm

from ._config import DATA_DIR


@dataclass
class ICDEntry():
    """
    Base dataclass representing an ICD chapter, block or category of ICD 10, 
    ICD 10-CM or ICD 11.
    """
    code: str
    """The chapter number, block range or ICD code of the entry."""
    title: str
    """Description of the chapter, block or category."""
    revision: str = field(init=False)
    kind: str = field(repr=False, default="entry")
    """Can be `entry`, `root`, `chapter`, `block` or `category`."""
    parent: Optional[ICDEntry] = field(
        default=None, repr=False, compare=False
    )
    """Direct ancestor of the entry."""
    children: List[ICDEntry] = field(
        default_factory=lambda: [], repr=False, compare=False
    )
    """List of direct descendants of the entry."""
    
    def __post_init__(self):
        """
        Make sure `kind` & `revision` take on allowed values and get the 
        release & revision from the root of the codex.
        """
        if self.kind not in ["entry", "root", "chapter", "block", "category"]:
            raise ValueError(
                "Attribute kind must be one of 'root', 'chapter', 'block' or "
                "'category'"
            )
        if self.revision not in ["10", "10-CM", "11"]:
            raise ValueError(
                "This package only supports ICD '10', '10-CM' or '11', not "
                f"{self.revision}"
            )
        return
    
    def __str__(self):
        return f"{self.kind} {self.code}: {self.title}"
    
    def __len__(self):
        return 1 + sum([len(child) for child in self.children])
    
    @property
    def release(self):
        """
        The release of the ICD codex. E.g. `2022` for the release including 
        corrections made prior to the year 2022.
        """
        if isinstance(self, ICDRoot):
            return self._release
        else:
            return self.get_root().release
    
    @release.setter
    def release(self, new_release):
        if not isinstance(self, ICDRoot):
            raise AttributeError(
                "Can only set attribute `release` on `ICDRoot` objects."
            )
        else:
            self._release = new_release
    
    @property
    def is_root(self) -> bool:
        return self.parent is None
    
    def get_root(self) -> ICDRoot:
        """Recursively find the root of the ICD codex from any entry."""
        if self.is_root:
            return self
        else:
            return self.parent.get_root()
    
    @property
    def depth(self):
        if self.is_root:
            return 1
        else:
            return 1 + self.parent.depth
    
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    @property
    def leaves(self):
        """Returns an iterator over all leaves of the ICD tree."""
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.leaves
    
    @property
    def entries(self):
        """
        Returns an iterator over all entries in the ICD (sub-)tree (of which 
        this entry is the root). This includes chapters, blocks and categories, 
        not only categories as is the case for `ICDEntry.leaves`.
        """
        yield self
        for child in self.children:
            yield from child.entries
    
    @property
    def depth_in_kind(self):
        """
        A `depth_in_kind` of 1 indicates that the parent of this entry is of 
        a different kind, while a value of 2 means that the parent is still of 
        the same kind, but the grantparent is different.
        """
        if type(self.parent) != type(self):
            return 1
        else:
            return self.parent.depth_in_kind + 1
    
    @property
    def _child_dict(self) -> Dict[str, ICDEntry]:
        return {child.code: child for child in self.children}
    
    def tree(self, prefix="", maxdepth: Optional[int] = None):
        """
        Render the current object and all descendants in a pretty tree.
        
        With `maxdepth` one can choose up to which depth of the tree the output 
        should be rendered.
        
        To display the output nicely, put it in a `print` statement lie so:
        
        ```python
        print(codex.tree(maxdepth=2))
        ```
        """
        tree_str = f"{str(self)}\n"
        
        if maxdepth is not None and maxdepth <= self.depth:
            return tree_str
        
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
    
    def ancestry(self):
        """
        Render ancestry from root directly to the current entry. Like with the 
        `tree()` method, this should be put inside a `print()` statement.
        """
        if self.is_root:
            return str(self) + "\n"
        else:
            ancestry_str = self.parent.ancestry()
            n = self.depth - 2
            return ancestry_str + n * "    " + "└───" + str(self) + "\n"
             
    def add_child(self, new_child: ICDEntry):
        """
        Add new child in a consistent manner. I.e., if the to-be-added child 
        is a block that would actually belong in an existing block, put it 
        there instead.
        """
        if new_child in self.children:
            return
        
        are_children_block = all(
            [isinstance(child, ICDBlock) for child in self.children]
        )
        if are_children_block and isinstance(new_child, ICDBlock):
            for block in self.children:
                if block.should_contain(new_child):
                    block.add_child(new_child)
                    return
                elif new_child.should_contain(block):
                    self.remove_child(block)
                    new_child.add_child(block)
        
        new_child.parent = self
        self.children.append(new_child)
    
    def remove_child(self, child: ICDEntry):
        """
        Remove `child` from `self.children` list in a cautios manner. This 
        means that if the child has already been added as some other object's 
        child and has hence already a new `parent` attribute, it won't be 
        deleted.
        """
        if child in self.children:
            self.children.remove(child)
            if child.parent == self:
                child.parent = None
    
    def search(self, code: str, maxdepth: Optional[int] = None) -> List[ICDEntry]:
        """
        Search a given code in the tree.
        
        The argument `code` can be a chapter number, block range or actual ICD 
        code of a disease. It may even only be a part of an ICD code. 
        `maxdepth` is the maximum recusion depth the method will go into for 
        the search.
        
        It returns the a list of entries that match the given code.
        """
        res = []
        
        if code in self.code:
            res = [self]
        
        if maxdepth is not None and maxdepth <= self.depth:
            return []
        
        for child in self.children:
            res = [*res, *child.search(code, maxdepth=maxdepth)]
        return res
    
    def exists(self, code: str, maxdepth: Optional[int] = None) -> bool:
        """
        Check if a given code exists in the codex tree.
        """
        if self.code == code:
            return True
        
        if maxdepth is not None and maxdepth <= self.depth:
            return False
        
        return any([child.exists(code, maxdepth) for child in self.children])
    
    def get(
        self, 
        code: str, 
        maxdepth: Optional[int] = None,
        kind: str = "category",
    ) -> ICDCategory:
        """
        Return the ICD category with the given code if it exists.
        """
        if self.code == code and self.kind == kind:
            return self
        
        if maxdepth is not None and maxdepth <= self.depth:
            return None
        
        for child in self.children:
            if (category := child.get(code, maxdepth)) is not None:
                return category



@dataclass
class ICDRoot(ICDEntry):
    """
    Root of the ICD 10 tree. It serves as an entry point for the recursive 
    parsing of the XML data file and also stores the version of the data.
    """
    code: str = field(init=False)
    title: str = field(init=False)
    _release: str = ""
    kind: str = field(repr=False, default="root")
    
    def __post_init__(self):
        tmp = super().__post_init__()
        self.code = f"ICD-{self.revision}"
        return tmp
    
    @property
    def chapter(self) -> ICDChapter:
        """Returns a dictionary containing all the ICD chapters loaded under a 
        roman-numeral key. E.g., chapter 2 can be accessed via something like 
        `root.chapter['II']`."""
        return self._child_dict


@dataclass
class ICDChapter(ICDEntry):
    """
    One of the 22 chapters in the ICD codex. In the XML data obtained from the 
    [CDC](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICDCM/2022/) 
    the chapter numbers are given in arabic numerals, but the WHO's API uses 
    roman numerals to identify chapters, so the `code` attribute is converted. 
    E.g., chapter `2` will be accessible from the root via `root.chapter['II']`.
    """
    kind: str = field(repr=False, default="chapter")
    
    def __post_init__(self):
        """Romanize chapter number and get release from root."""
        tmp = super().__post_init__()
        
        units     = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
        tens      = ['', 'X', 'XX', 'XXX', 'XL', 'L', 'LX', 'LXX', 'LXXX', 'XC']
        hundrets  = ['', 'C', 'CC', 'CCC', 'CD', 'D', 'DC', 'DCC', 'DCCC', 'CM']
        thousands = ['', 'M', 'MM', 'MMM']
        roman_letters = [*units[1:], *tens[1:], *hundrets[1:], *thousands[1:]]
        
        if (
            type(self.code) == str 
            and 
            all([c in roman_letters for c in self.code])
        ):
            return tmp
        
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
        
        return tmp
    
    @property
    def block(self) -> Dict[str, ICDBlock]:
        """Returns a dictionary containing all blocks loaded for this chapter 
        under a key corresponding to their ICD-range. E.g., block `C00-C96` 
        contains all categories with codes ranging from `C00` to `C96`."""
        return self._child_dict


@dataclass
class ICDBlock(ICDEntry):
    """
    A block of ICD codes within a chapter. A block specifies a range of ICD 
    codes that are described in that block. It may also contain other blocks, 
    not necessarily categories as direct children. The `code` attribute of a 
    block might be something like `C00-C96`.
    """
    kind: str = field(repr=False, default="block")
    
    @property
    def block(self) -> ICDBlock:
        """Like :class:`ICDChapter`, a block might have blocks as children, 
        which can be accessed in the exact same way as for the chapter."""
        if len(self.children) > 0 and isinstance(self.children[0], ICDBlock):
            return self._child_dict
    
    @property
    def category(self) -> ICDCategory:
        """In case the block does not have blocks, but categories as children, 
        they can be accessed via the `category` attribute, which also returns a 
        dictionary, just like `block`."""
        if len(self.children) > 0 and isinstance(self.children[0], ICDCategory):
            return self._child_dict
    
    def should_contain(self, block: ICDBlock) -> bool:
        raise NotImplementedError(
            "Method to check whether one block should contain another needs to "
            "be implemented in inheriting classes."
        )
    
    def find(self, code: str, maxdepth:int = None) -> ICDBlock:
        """Stop searching when code is surely not in block."""
        if self.should_contain(code):
            return None
        return super().find(code, maxdepth)


@dataclass
class ICDCategory(ICDEntry):
    """
    A category of the ICD system. These are the only entries in the ICD codex 
    for which the `code` attribute actually holds a valid ICD code in the regex 
    form `[A-Z][0-9]{2}(.[0-9]{1,3})?`.
    """
    kind: str = field(repr=False, default="category")
    
    @property
    def category(self) -> ICDCategory:
        """If there exists a finer classification of the category, this 
        property returns them as a dictionary of respective ICDs as key and the 
        actual entry as value."""
        return self._child_dict
