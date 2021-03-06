"""
This module defines dataclasses that can parse, display and provide utilities
for the International statistical classification of diseases and related health
problems (10th revision).
"""
from __future__ import annotations

from typing import Dict, List, Optional


class ICDEntry():
    """
    Base class representing an abstract ICD chapter, block or category of ICD
    10, ICD 10-CM or ICD 11.
    """
    def __init__(
        self,
        code: str,
        title: str,
        kind: str,
        parent: ICDEntry = None,
        children: Optional[List[ICDEntry]] = None
    ):
        """
        Initialize base ICD entry and make sure `kind` & `revision`
        attributes take on allowed values. The attribute `kind` can only be one
        of 'root', 'chapter', 'block' or 'category', While currently this
        package only supports the 10th and 11th revision along with the CDC's
        clinical modification 10-CM as `revision` attribute.
        """
        if kind not in ["root", "chapter", "block", "category"]:
            raise ValueError(
                "Attribute kind must be one of 'root', 'chapter', 'block' or "
                f"'category', not {kind}"
            )

        self.parent = None
        if parent is not None:
            if not issubclass(type(parent), ICDEntry):
                raise TypeError(
                    "Parent entry of an ICD entry must inherit from `ICDEntry`"
                )
            parent.add_child(self)

        self.code = code
        self.title = title
        self.kind = kind

        self.children = []
        if children is not None:
            for child in children:
                self.add_child(child)


    def __str__(self):
        return f"{self.kind} {self.code}: {self.title}"

    def __repr__(self):
        return (
            self.__class__.__name__ +
            f"(code='{self.code}', title='{self.title}', kind='{self.kind}')"
        )

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

        return self.root.release

    @release.setter
    def release(self, new_release):
        if not isinstance(self, ICDRoot):
            raise AttributeError(
                "Can only set attribute `release` on `ICDRoot` objects."
            )

        self._release = new_release

    @property
    def is_root(self) -> bool:
        """
        Only `True` for the `ICDRoot` element that is at the top of the codex
        tree.
        """
        return self.parent is None

    @property
    def root(self) -> ICDRoot:
        """Recursively find the root of the ICD codex from any entry."""
        if self.is_root:
            return self

        return self.parent.root

    @property
    def chapter(self):
        """If the entry is a block or category, return the chapter it is in."""
        if self.kind == "root":
            raise AttributeError("Not part of any chapter")

        if self.kind == "chapter":
            return self

        return self.parent.chapter

    @property
    def block(self):
        """Return the closest ancestor that is a block."""
        if self.kind in ["root", "chapter"]:
            raise AttributeError("Not part of any block")

        if self.kind == "block":
            return self

        return self.parent.block

    @property
    def depth(self):
        """Return the depth of the entry in the codex tree."""
        if self.is_root:
            return 1

        return 1 + self.parent.depth

    @property
    def is_leaf(self) -> bool:
        """An entry is a leaf if it has no children."""
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
        if self.parent is None:
            return 1
        if self.kind != self.parent.kind:
            return 1
        return self.parent.depth_in_kind + 1

    def _child_dict(self, kind: Optional[str] = None) -> Dict[str, ICDEntry]:
        if kind is not None:
            return {c.code: c for c in self.children if c.kind == kind}
        return {c.code: c for c in self.children}

    def tree(
        self,
        prefix="",
        maxdepth: Optional[int] = None,
        print_out: bool = True
    ):
        """
        Print or return the current object and all descendants in a pretty tree.

        With `maxdepth` one can choose up to which depth of the tree the output
        should be rendered.

        `print_out=False` will only return the string with the rendered tree,
        while setting it to `True` (default) will directly print it out.
        """
        treeprint = print if print_out else lambda x: x

        res = f"{str(self)}\n"

        if maxdepth is not None and maxdepth <= self.depth:
            return treeprint(res)

        num_children = len(self.children)
        for i,child in enumerate(self.children):
            if i + 1 == num_children:
                branch = "????????????"
                new_prefix = prefix + "    "
            else:
                branch = "????????????"
                new_prefix = prefix + "???   "
            res += (
                prefix
                + branch
                + child.tree(new_prefix, maxdepth, print_out=False)
            )
        return treeprint(res)

    def ancestry(self, print_out: bool = True):
        """
        Print or return ancestry from root directly to the current entry.

        If `print_out` is set to `True`, the ancestry will be printed directly.
        Otherwise the string will just be returned.
        """
        ancestryprint = print if print_out else lambda x: x

        if self.is_root:
            return ancestryprint(str(self) + "\n")

        num = self.depth - 2
        return ancestryprint(
            self.parent.ancestry(print_out=False)
            + num * "    "
            + "????????????"
            + str(self)
            + "\n"
        )

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

                if new_child.should_contain(block):
                    self.remove_child(block)
                    new_child.add_child(block)

        if new_child.parent is not None:
            new_child.parent.remove_child(new_child)

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

    def code_matches(self, code: str) -> bool:
        """
        Check if a given ICD code (with or without the '.') matches the
        entry's code.
        """
        self_dotless_code = self.code.replace('.', '')
        return code in self.code or code in self_dotless_code

    def search(self, code: str, maxdepth: Optional[int] = None) -> List[ICDEntry]:
        """
        Search a given code in the tree.

        The argument `code` can be a chapter number, block range or actual ICD
        code of a disease. It may even only be a part of an ICD code.
        `maxdepth` is the maximum recusion depth the method will go into for
        the search. The `code` can be provided with or without the dot.

        It returns the a list of entries that match the given code.
        """
        res = []

        if maxdepth is not None and maxdepth <= self.depth:
            return res

        if self.code_matches(code):
            res = [self]

        for child in self.children:
            res = [*res, *child.search(code, maxdepth=maxdepth)]

        return res

    def exists(self, code: str, maxdepth: Optional[int] = None) -> bool:
        """
        Check if a given `code` exists in the codex tree.

        With `maxdepth` you can choose how deep the method goes down the tree
        for the search. The `code` can be provided with or without the dot.
        """
        if maxdepth is not None and maxdepth <= self.depth:
            return False

        if self.code_matches(code):
            return True

        return any(child.exists(code, maxdepth) for child in self.children)

    def get(
        self,
        code: str,
        maxdepth: Optional[int] = None,
        kind: str = "category",
    ) -> Optional[ICDEntry]:
        """
        Return the ICD category with the given `code` that is of the specified
        `kind` if it exists. Will work with or without the dot in the `code`.

        Set `maxdepth` to the maximum depth you want to go down the tree for
        the search.
        """
        if maxdepth is not None and maxdepth <= self.depth:
            return None

        if self.code_matches(code) and self.kind == kind:
            return self

        for child in self.children:
            if (category := child.get(code, maxdepth)) is not None:
                return category


class ICDRoot(ICDEntry):
    """
    Root of the ICD 10 tree. It serves as an entry point for the recursive
    parsing of the XML data file and also stores the version of the data.
    """
    def __init__(self, code: str, title: str, release: str, *args, **kwargs):
        super().__init__(code, title, *args, kind="root", **kwargs)
        self._release = release

    @property
    def chapters(self) -> Dict[str, ICDChapter]:
        """Returns a dictionary containing all the ICD chapters loaded under a
        roman-numeral key. E.g., chapter 2 can be accessed via something like
        `root.chapter['II']`."""
        return self._child_dict(kind="chapter")


class ICDChapter(ICDEntry):
    """
    One of the 22 chapters in the ICD codex. In the XML data obtained from the
    [CDC](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICDCM/2022/)
    the chapter numbers are given in arabic numerals, but the WHO's API uses
    roman numerals to identify chapters, so the `code` attribute is converted.
    E.g., chapter `2` will be accessible from the root via `root.chapter['II']`.
    """
    def __init__(self, code: str, title: str, *args, **kwargs):
        super().__init__(code, title, *args, kind="chapter", **kwargs)

    @property
    def blocks(self) -> Dict[str, ICDBlock]:
        """Returns a dictionary containing all blocks loaded for this chapter
        under a key corresponding to their ICD-range. E.g., block `C00-C96`
        contains all categories with codes ranging from `C00` to `C96`."""
        return self._child_dict(kind="block")

    @staticmethod
    def romanize(number: int):
        """Romanize an integer."""
        units     = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
        tens      = ['', 'X', 'XX', 'XXX', 'XL', 'L', 'LX', 'LXX', 'LXXX', 'XC']
        hundrets  = ['', 'C', 'CC', 'CCC', 'CD', 'D', 'DC', 'DCC', 'DCCC', 'CM']
        thousands = ['', 'M', 'MM', 'MMM']

        roman_num = thousands[number // 1000]
        number = number % 1000
        roman_num += hundrets[number // 100]
        number = number % 100
        roman_num += tens[number // 10]
        number = number % 10
        roman_num += units[number]

        return roman_num


class ICDBlock(ICDEntry):
    """
    A block of ICD codes within a chapter. A block specifies a range of ICD
    codes that are described in that block. It may also contain other blocks,
    not necessarily categories as direct children. The `code` attribute of a
    block might be something like `C00-C96`.
    """
    def __init__(self, code: str, title: str, *args, **kwargs):
        super().__init__(code, title, *args, kind="block", **kwargs)

    @property
    def blocks(self) -> Optional[ICDBlock]:
        """Like :class:`ICDChapter`, a block might have blocks as children,
        which can be accessed in the exact same way as for the chapter."""
        return self._child_dict(kind="block")

    @property
    def categories(self) -> Optional[ICDCategory]:
        """In case the block does not have blocks, but categories as children,
        they can be accessed via the `category` attribute, which also returns a
        dictionary, just like `block`."""
        return self._child_dict(kind="category")

    def should_contain(self, block: ICDBlock) -> bool:
        """Check whether a given block should be contained by this block."""
        raise NotImplementedError(
            "Method to check whether one block should contain another needs to "
            "be implemented in inheriting classes."
        )

    def find(self, code: str, maxdepth:int = None) -> ICDBlock:
        """Stop searching when code is surely not in block."""
        if self.should_contain(code):
            return None
        return super().get(code, maxdepth)


class ICDCategory(ICDEntry):
    """
    A category of the ICD system. These are the only entries in the ICD codex
    for which the `code` attribute actually holds a valid ICD code in the regex
    form `[A-Z][0-9]{2}(.[0-9]{1,3})?`.
    """
    def __init__(self, code: str, title: str, *args, **kwargs):
        super().__init__(code, title, *args, kind="category", **kwargs)

    @property
    def categories(self) -> ICDCategory:
        """If there exists a finer classification of the category, this
        property returns them as a dictionary of respective ICDs as key and the
        actual entry as value."""
        return self._child_dict(kind="category")
