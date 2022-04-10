"""
## ICD-11 module

The latest revision of the **International Statistical Classification of
Diseases and Related Health Problems** is number eleven and it is implemented
in this independent python module.

The underlying offical data can be obtained from the
[WHO's ICD-11 browser][browser] tool in the 'Info' tab as a
[spreadsheet][download] file.

[browser]: https://icd.who.int/browse11/l-m/en
[download]: https://icd.who.int/browse11/Downloads/Download?fileName=simpletabulation.zip
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, TextIO

import requests
import pandas as pd

from ._config import DATA_DIR
from .base import ICDBlock, ICDCategory, ICDChapter, ICDEntry, ICDRoot


@dataclass
class ICD11Entry(ICDEntry):
    """
    Class representing any entry in the 11th revision of ICD.
    """
    foundation_uri: str = field(init=True, default=None)
    """Unique identifier for an entry that will not change. Only exists since
    revision 11 of the ICD codex. Not all entries have foundation URIs. Some 
    sub-entries are only modifications of an entry and hence only have a 
    `linearization_uri`."""
    linearization_uri: str = field(init=True, default=None)
    """Unique URI for the specific linearization. All entries except the root 
    have a linearization URI."""
    revision: str = "11"
    """Major revision of the ICD codex"""


@dataclass
class ICD11Root(ICDRoot, ICD11Entry):
    """
    Subclass of the `ICDRoot` to provide a classmethod for generating the
    entire codex from a pandas `DataFrame`.
    """
    title: str = field(init=True)
    """Title describing the codex stored under this root."""
    _release: str = "2022-02"
    """As there is only one release so far for the ICD-11, this is hardcoded 
    for now. When the WHO publishes more & updated releases, this probably 
    needs to be updated."""

    @classmethod
    def from_table(cls, table: pd.DataFrame) -> ICD11Root:
        """
        Create root from a pandas table and initialize recursive codex
        generation
        """
        root = cls(
            title=(
                "International Statistical Classification of Diseases and "
                "Related Health Problems, 11th Revision"
            )
        )
        
        is_chapter = table["ClassKind"] == "chapter"
        chapter_rows = table.loc[is_chapter]
        
        for chapter_row in chapter_rows:
            chapter_no = chapter_row["ChapterNo"]
            is_chapter_no = table["ChapterNo"] == chapter_no
            chapter_table = table.loc[is_chapter_no]
            root.add_child(ICD11Chapter.from_table(chapter_table))
        
        return root


@dataclass
class ICD11Chapter(ICDChapter, ICD11Entry):
    """
    Subclass of the general `ICDChapter` class implementing a classmethod for 
    creating an entire chapter recusively from a pandas `DataFrame`.
    """
    @classmethod
    def from_table(cls, table: pd.DataFrame) -> ICD11Chapter:
        """
        Create chapter and blocks underneath the chapter from a `DataFrame`.
        """
        chapter_row = table.loc[table["ClassKind"] == "chapter"].iloc[0]
        chapter = cls(
            code=chapter_row["ChapterNo"],
            title=chapter_row["Title"],
            foundation_uri=chapter_row["Foundation URI"],
            linearization_uri=chapter_row["Linearization (release) URI"],
        )
        
        is_l1_block = table["BlockId"].str.startswith("BlockL1")
        l1_block_rows = table.loc[is_l1_block]
        
        for l1_block_row in l1_block_rows:
            l1_block_id = l1_block_row["BlockId"]
            l1_block_table = table.loc[table["Grouping1"] == l1_block_id]
            chapter.add_child(ICD11Block.from_table(l1_block_table))
        
        return chapter


@dataclass
class ICD11Block(ICDBlock, ICD11Entry):
    """"""
    @classmethod
    def from_table(cls, table: pd.DataFrame) -> ICD11Block:
        """"""
        return cls()