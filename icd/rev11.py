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


def _fetch_and_parse_response(uri: str, api_ver: int = 2) -> dict:
    """Fetch response for a given URI and parse it as JSON."""
    response = requests.get(uri, headers=create_headers(api_ver=api_ver))
    response.raise_for_status()
    parsed_response = response.json()
    return parsed_response


def fetch_available_releases(
    linearization_name: str = "mms",
    api_ver: int = 2,
) -> list[str]:
    """
    Fetch the available releases of a given linearization in the ICD API.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{linearization_name}"
    return _fetch_and_parse_response(uri, api_ver)["release"]


def fetch_root(
    release_id: str = "2023-01",
    linearization_name: str = "mms",
    api_ver: int = 2,
) -> dict:
    """
    Fetch the root entry of a given linearization release from the ICD API.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}"
    return _fetch_and_parse_response(uri, api_ver)


def fetch_id(
    code: str,
    release_id: str = "2023-01",
    linearization_name: str  = "mms",
    api_ver: int = 2,
) -> str:
    """
    Fetch the numeric ID of an entry from the ICD API using its code.

    This is useful for fetching the linearization URI of an entry when only the code
    is known.

    Examples:
    >>> fetch_id(code="EK11")
    '144637523'
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}/codeinfo/{code}"
    parsed_response = _fetch_and_parse_response(uri, api_ver)

    try:
        linearization_uri = parsed_response["stemId"]
        return linearization_uri.split("/")[-1]
    except KeyError as key_err:
        raise KeyError(
            f"Could not find stemId in response from the ICD API for the code {code}. "
            f"Response: {parsed_response}"
        ) from key_err


def fetch_info(
    stem_id: str,
    release_id: str = "2023-01",
    linearization_name: str  = "mms",
    api_ver: int = 2,
) -> dict:
    """
    Fetch the information of an entry from the ICD API using its stem ID.

    When knowing the linearization ID of an entry, this function can be used to fetch
    the information of the entry.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}/{stem_id}"
    return _fetch_and_parse_response(uri, api_ver)


def _strip_dashes(text: str) -> str:
    """Remove leading dashes and spaces ffrom a string."""
    return re.sub(r"^[ -]+", "", text)


class ICD11Entry(ICDEntry):
    """
    Class representing any entry in the 11th revision of ICD.
    """
    revision: str = "11"
    """Major revision of the ICD codex"""


class ICD11Root(ICDRoot, ICD11Entry):
    """
    Subclass of the `ICDRoot` to provide classmethods for generating the codex from
    either a pandas `DataFrame` or directly from the ICD API.
    """
    # @classmethod
    # def from_api(cls, advance: Callable) -> ICD11Root:

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

        table["Grouping6"] = None
        is_chapter = table["ClassKind"] == "chapter"
        is_not_V_or_X = table["ChapterNo"].str.match(r"^[^VX]")
        chapter_rows = table.loc[is_chapter & is_not_V_or_X]

        for _, chapter_row in chapter_rows.iterrows():
            chapter_num = chapter_row["ChapterNo"]
            chapter_table = table.loc[table["ChapterNo"] == chapter_num]
            chapter = ICD11Chapter.from_series(chapter_row, chapter_table, advance=advance)
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
            title=_strip_dashes(series["Title"]),
        )
        advance()

        is_block = table["ClassKind"] == "block"
        is_same_chapter = table["ChapterNo"] == chapter.code
        has_depth_1 = table["DepthInKind"] == 1
        block_rows = table.loc[is_block & is_same_chapter & has_depth_1]

        for _, block_row in block_rows.iterrows():
            block = ICD11Block.from_series(block_row, table, advance=advance)
            chapter.add_child(block)

        is_category = table["ClassKind"] == "category"
        has_no_grouping = table["Grouping1"].isna()
        has_depth_1 = table["DepthInKind"] == 1
        category_rows = table.loc[is_category & is_same_chapter & has_no_grouping & has_depth_1]

        for _, category_row in category_rows.iterrows():
            category = ICD11Category.from_series(category_row, table, advance=advance)
            chapter.add_child(category)

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
            title=_strip_dashes(series["Title"]),
        )
        advance()
        block_depth = series["DepthInKind"]

        is_block = table["ClassKind"] == "block"
        is_descendant = table[f"Grouping{block_depth}"] == block.code
        is_one_deeper = table["DepthInKind"] == block_depth + 1

        sub_block_rows = table.loc[is_block & is_descendant & is_one_deeper]

        for _, sub_block_row in sub_block_rows.iterrows():
            sub_table = table.loc[is_descendant]
            sub_block = ICD11Block.from_series(sub_block_row, sub_table, advance=advance)
            block.add_child(sub_block)

        is_category = table["ClassKind"] == "category"
        is_under_block = table["DepthInKind"] == 1
        is_one_deeper = table[f"Grouping{block_depth + 1}"].isna()
        category_rows = table.loc[is_category & is_descendant & is_under_block & is_one_deeper]

        for _, category_row in category_rows.iterrows():
            sub_table = table.loc[is_category & is_descendant]
            category = ICD11Category.from_series(category_row, sub_table, advance=advance)
            block.add_child(category)

        return block


    def should_contain(self, block: ICDBlock) -> bool:
        """
        Not implementable for ICD 11, but necessary for the `base.ICDEntry.add_child`
        method.`
        """
        this_level = int(re.match(r"BlockL(\d+)", self.code).group(1))
        other_level = int(re.match(r"BlockL(\d+)", block.code).group(1))

        if other_level == this_level + 1:
            return True

        return False


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
            title=_strip_dashes(series["Title"]),
        )
        advance()
        category_depth = series["DepthInKind"]

        if series["isLeaf"]:
            return category

        is_category = table["ClassKind"] == "category"
        is_one_deeper = table["DepthInKind"] == category_depth + 1
        does_code_match = table["Code"].str.startswith(category.code, na=False)
        sub_category_rows = table.loc[is_category & is_one_deeper & does_code_match]

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
