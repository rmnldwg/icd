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

import re
from typing import Callable

import pandas as pd
import requests
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)

from icd.base import ICDBlock

from icd._config import DATA_DIR
from icd.base import (
    ICDBlock,
    ICDCategory,
    ICDChapter,
    ICDEntry,
    ICDRoot,
    create_headers,
    get_hostname,
)


def fetch_description_from_linearization(
    numeric_id: str,
    release_id: str = "2023-01",
    linearization_name: str  = "mms",
    api_ver: int = 2,
) -> str:
    """
    Get the description of an entry from the ICD API using its linearization URI.

    The description is either stored as `definition` or `codingNote` of the JSON
    response from the ICD API.

    Examples:
    >>> fetch_description_from_linearization("662394760")
    'A condition characterised by the dysfunction or lack of function of a surgically created urine reservoir within the body, specifically along the path by which urine enters the pouch.'
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}/{numeric_id}"
    response = requests.get(uri, headers=create_headers(api_ver=api_ver))
    response.raise_for_status()
    parsed_response = response.json()

    if "definition" in parsed_response:
        return parsed_response["definition"]["@value"]
    if "longDefinition" in parsed_response:
        return parsed_response["longDefinition"]["@value"]
    if "codingNote" in parsed_response:
        return parsed_response["codingNote"]["@value"]

    return ""


def fetch_description_from_code(
    code: str,
    release_id: str = "2023-01",
    linearization_name: str  = "mms",
    api_ver: int = 2,
) -> str:
    """
    Get the description of an entry from the ICD API using its ICD code.

    This first needs to fetch the numeric ID of the entry from the API and then
    uses the `fetch_description_from_linearization` function to get the actual
    description.

    Examples:
    >>> fetch_description_from_code("5C81.0")
    'A disorder characterised by low levels of high-density lipoprotein in the blood.'
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}/codeinfo/{code}"
    response = requests.get(uri, headers=create_headers(api_ver=api_ver))
    response.raise_for_status()
    parsed_response = response.json()

    if "stemId" in parsed_response:
        linearization_uri = parsed_response["stemId"]
        numeric_id = linearization_uri.split("/")[-1]
        return fetch_description_from_linearization(
            numeric_id=numeric_id,
            release_id=release_id,
            linearization_name=linearization_name,
        )

    return ""


def strip_dashes(text: str) -> str:
    """Remove leading dashes and spaces ffrom a string."""
    return re.sub(r"^[ -]+", "", text)


class ICD11Entry(ICDEntry):
    """
    Class representing any entry in the 11th revision of ICD.
    """
    revision: str = "11"
    """Major revision of the ICD codex"""

    def description(self) -> str:
        """
        Get the description of the entry from the ICD API.

        Example:
        >>> ICD11Entry(code="EK11", title="Protein contact dermatitis").description()
        'Immediate contact dermatitis due to exposure to proteins from plants, animal tissue and other organic matter.'
        """
        if not hasattr(self, "_description") or self._description is None:
            self._description = fetch_description_from_code(self.code)

        return self._description


class ICD11Root(ICDRoot, ICD11Entry):
    """
    Subclass of the `ICDRoot` to provide a classmethod for generating the
    entire codex from a pandas `DataFrame`.
    """

    @classmethod
    def from_table(cls, table: pd.DataFrame, advance: Callable) -> ICD11Root:
        """
        Create root from a pandas table and initialize codex generation
        """
        root = cls(
            code="ICD-11 root",
            title=(
                "International Statistical Classification of Diseases and "
                "Related Health Problems, 11th Revision"
            ),
            release="2023-01",   # At the time of writing, this is the latest release
        )
        advance()

        is_chapter = table["ClassKind"] == "chapter"
        is_not_V_or_X = table["ChapterNo"].str.match(r"^[^VX]")
        chapter_rows = table.loc[is_chapter & is_not_V_or_X]

        for _, chapter_row in chapter_rows.iterrows():
            chapter = ICD11Chapter.from_series(chapter_row, table, advance=advance)
            root.add_child(chapter)

        return root


class ICD11Chapter(ICDChapter, ICD11Entry):
    """
    Subclass of the general `ICDChapter` adapted for the 11th revision of the ICD.
    """
    @classmethod
    def from_series(
        cls,
        series: pd.Series,
        table: pd.DataFrame,
        advance: Callable,
    ) -> ICD11Chapter:
        """
        Create chapter from a pandas series.
        """
        chapter = cls(
            code=series["ChapterNo"],
            title=strip_dashes(series["Title"]),
        )
        advance()

        is_block = table["ClassKind"] == "block"
        is_same_chapter = table["ChapterNo"] == chapter.code
        has_depth_1 = table["DepthInKind"] == 1
        block_rows = table.loc[is_block & is_same_chapter & has_depth_1]

        for _, block_row in block_rows.iterrows():
            block = ICD11Block.from_series(block_row, table, advance=advance)
            chapter.add_child(block)

        return chapter


class ICD11Block(ICDBlock, ICD11Entry):
    """
    Subclass of the general `ICDBlock` adapted for the 11th revision of the ICD.
    """
    @classmethod
    def from_series(
        cls,
        series: pd.Series,
        table: pd.DataFrame,
        advance: Callable,
    ) -> ICD11Block:
        """
        Create block from a pandas series.
        """
        block = cls(
            code=series["BlockId"],
            title=strip_dashes(series["Title"]),
        )
        advance()
        block_depth = series["DepthInKind"]

        is_block = table["ClassKind"] == "block"
        is_descendant = table[f"Grouping{block_depth}"] == block.code
        
        if block_depth < 5:
            is_not_deeper = table[f"Grouping{block_depth + 1}"].isna()
        else:
            is_not_deeper = True

        sub_block_rows = table.loc[is_block & is_descendant & is_not_deeper]

        for _, sub_block_row in sub_block_rows.iterrows():
            sub_block = ICD11Block.from_series(sub_block_row, table, advance=advance)
            block.add_child(sub_block)

        is_category = table["ClassKind"] == "category"
        categery_rows = table.loc[is_category & is_descendant & is_not_deeper]

        for _, category_row in categery_rows.iterrows():
            category = ICD11Category.from_series(category_row, table, advance=advance)
            block.add_child(category)

        return block


    def should_contain(self, block: ICDBlock) -> bool:
        """
        Not implementable for ICD 11, but necessary for the `base.ICDEntry.add_child`
        method.`
        """
        return True


class ICD11Category(ICDCategory, ICD11Entry):
    """
    Subclass of the general `ICDCategory` adapted for the 11th revision of the ICD.
    """
    @classmethod
    def from_series(
        cls,
        series: pd.Series,
        table: pd.DataFrame,
        advance: Callable,
    ) -> ICD11Category:
        """
        Create category from a pandas series.
        """
        category = cls(
            code=series["Code"],
            title=strip_dashes(series["Title"]),
        )
        advance()
        category_depth = series["DepthInKind"]

        if series["isLeaf"]:
            return category

        is_category = table["ClassKind"] == "category"
        has_depth_plus_1 = table["DepthInKind"] == category_depth + 1
        does_code_match = table["Code"].str.startswith(category.code, na=False)
        sub_category_rows = table.loc[is_category & has_depth_plus_1 & does_code_match]

        for _, sub_category_row in sub_category_rows.iterrows():
            sub_category = ICD11Category.from_series(sub_category_row, table, advance=advance)
            category.add_child(sub_category)

        return category


def get_codex(verbose: bool = True) -> ICD11Root:
    """
    Get the entire ICD 11 codex as an `ICD11Root` object.
    """
    table = pd.read_csv(DATA_DIR / "icd-11" / "simpletabulation.csv", low_memory=False)
    is_not_V_or_X = table["ChapterNo"].str.match(r"^[^VX]")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(
            "Generating ICD 11 codex...",
            total=is_not_V_or_X.sum(),
            visible=verbose,
        )
        advance = lambda: progress.update(task, advance=1)
        codex = ICD11Root.from_table(table, advance=advance)

    return codex
