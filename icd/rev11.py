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
import logging

import re
from typing import Callable

import pandas as pd
import requests
from rich.progress import track

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
    logging.info(f"Succesfully fetched JSON data from {uri}")
    logging.debug(f"JSON data: {parsed_response}")
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
    Fetch the numeric "stem ID" of an entry from the ICD API using its code.

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
    the information of the entry, like a definition or its parent/children.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release_id}/{linearization_name}/{stem_id}"
    return _fetch_and_parse_response(uri, api_ver)


def _depth_from_title(title: str) -> int:
    """Count the number of dashes at the beginning of the title."""
    dashes = re.match(r"^(\-\s)*", title).group(0)
    return dashes.count("-") + 1


class ICD11Entry(ICDEntry):
    """
    Class representing any entry in the 11th revision of ICD.
    """
    revision: str = "11"
    """Major revision of the ICD codex"""

    def __init__(self, *args, stem_id: str, **kwargs):
        self.stem_id = stem_id
        super().__init__(*args, **kwargs)


    @staticmethod
    def from_series(row: pd.Series) -> ICD11Entry:
        """
        Create an entry from the row of the ICD's simple tabulation spreadsheet.
        """
        if row["ClassKind"] == "chapter":
            return ICD11Chapter.from_series(row)
        elif row["ClassKind"] == "block":
            return ICD11Block.from_series(row)
        elif row["ClassKind"] == "category":
            return ICD11Category.from_series(row)
        else:
            raise ValueError(f"Unknown ClassKind {row['ClassKind']} for row {row}")


    @property
    def api_info(self) -> dict:
        """
        Provide the information of the entry from the ICD API.

        This is a cached property, so the information is only fetched once.
        Nonetheless, this may be considered an expesive operation and not just a
        simple attribute access.
        """
        if not hasattr(self, "_api_info"):
            self._api_info = fetch_info(
                stem_id=self.stem_id,
                release_id=self.release,
                linearization_name="mms",
                api_ver=2,
            )

        return self._api_info


class ICD11Root(ICDRoot, ICD11Entry):
    """
    Subclass of the `ICDRoot` to provide classmethods for generating the codex from
    either a pandas `DataFrame` or directly from the ICD API.
    """


class ICD11Chapter(ICDChapter, ICD11Entry):
    """
    Subclass of the general `ICDChapter` adapted for the 11th revision of the ICD.
    """
    @property
    def description(self) -> str:
        """
        Description of the entry.
        """
        return self.api_info["definition"]["@value"]

    @classmethod
    def from_series(cls, row: pd.Series) -> ICD11Chapter:
        """
        Create chapter from a pandas series.
        """
        return cls(
            code=row["ChapterNo"],
            title=row["Title"],
            stem_id=row["Linearization (release) URI"].split("/")[-1],
        )


class ICD11Block(ICDBlock, ICD11Entry):
    """
    Subclass of the general `ICDBlock` adapted for the 11th revision of the ICD.
    """
    @classmethod
    def from_series(cls, row: pd.Series) -> ICD11Block:
        """
        Create block from a pandas series.
        """
        return cls(
            code=row["BlockId"],
            title=row["Title"],
            stem_id=row["Linearization (release) URI"].split("/")[-1],
        )

    def should_contain(self, block: ICDBlock) -> bool:
        """
        Not implementable for ICD 11, but necessary for the `base.ICDEntry.add_child`
        method.`
        """
        this_depth = _depth_from_title(self._title)
        other_depth = _depth_from_title(block._title)

        if other_depth == this_depth + 1:
            return True

        return False


class ICD11Category(ICDCategory, ICD11Entry):
    """
    Subclass of the general `ICDCategory` adapted for the 11th revision of the ICD.
    """
    @property
    def description(self) -> str:
        """
        Description of the entry.
        """
        return self.api_info["definition"]["@value"]

    @classmethod
    def from_series(
        cls,
        row: pd.Series,
    ) -> ICD11Category:
        """
        Create category from a pandas series.
        """
        return cls(
            code=row["Code"],
            title=row["Title"],
            stem_id=row["Linearization (release) URI"].split("/")[-1],
        )


def get_codex(verbose: bool = True) -> ICD11Root:
    """
    Get the entire ICD 11 codex as an `ICD11Root` object.

    This function simply iterates over the table and adds the entries to the codex
    based on their depth. The depth is inferred from the number of dashes in the
    title of the entry.

    E.g., the block with code `BlockL2-MB4` has the title
    `- - symptoms or signs involving the nervous system` in the simple tabulation
    (which was obtained from [here]). Hence, its depth is 2 and it is added as a
    child of the last block with depth 1.

    Note that in the [ICD browser], no code is assigned to the blocks.

    [here]: https://icd.who.int/browse11/Downloads/Download?fileName=simpletabulation.zip
    [browser]: https://icd.who.int/browse11/l-m/en
    """
    table_dir = DATA_DIR / "icd-11"
    table_files = sorted(table_dir.glob("*-*-simpletabulation.csv"))
    latest_table = table_files[-1]
    release = re.match(r"(\d{4}-\d{2})", latest_table.name).group(1)

    table = pd.read_csv(latest_table, low_memory=False)

    codex = ICD11Root(
        code="ICD-11 root",
        title=(
            "International Statistical Classification of Diseases and "
            "Related Health Problems, 11th Revision"
        ),
        release=release,
        stem_id="",
    )
    last_entry_by_depth = {0: codex}

    for _, row in track(
        table.iterrows(),
        total=len(table),
        description=f"Generate ICD 11 codex (release: {release})...",
        disable=not verbose,
    ):
        depth = _depth_from_title(row["Title"])
        
        next_entry = ICD11Entry.from_series(row)
        last_entry_by_depth[depth - 1].add_child(next_entry)

        last_entry_by_depth[depth] = next_entry

    # Assign block codex to the supplementary chapters, because they have no `BlockId`
    # in the simple tabulation.
    for entry in codex.entries:
        if entry.kind == "block" and pd.isna(entry.code):
            for sub_entry in entry.entries:
                if not pd.isna(sub_entry.code):
                    entry.code = f"BlockL{entry.depth_in_kind}-{sub_entry.code[:3]}"
                    break

            if pd.isna(entry.code):
                entry.code = f"BlockL{entry.depth_in_kind}-???"

    return codex
