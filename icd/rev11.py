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
from typing import Optional
import warnings

import re

import pandas as pd
import requests
from rich.progress import track

from .base import ICDBlock

from ._config import DATA_DIR
from .base import (
    ICDBlock,
    ICDCategory,
    ICDChapter,
    ICDEntry,
    ICDRoot,
    create_headers,
    get_hostname,
)

logger = logging.getLogger("icd")


class ManyAPICallsWarning(UserWarning):
    """Warning for when many API calls are made."""


def _fetch_and_parse_response(uri: str, api_ver: int = 2) -> dict:
    """Fetch response for a given URI and parse it as JSON."""
    response = requests.get(uri, headers=create_headers(api_ver=api_ver))
    response.raise_for_status()
    parsed_response = response.json()
    logger.info(f"Succesfully fetched JSON data from {uri}")
    logger.debug(f"JSON data: {parsed_response}")
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
    release: str = "2023-01",
    linearization_name: str = "mms",
    api_ver: int = 2,
) -> dict:
    """
    Fetch the root entry of a given linearization release from the ICD API.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release}/{linearization_name}"
    return _fetch_and_parse_response(uri, api_ver)


def fetch_id(
    code: str,
    release: str = "2023-01",
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
    uri = f"http://{hostname}/icd/release/11/{release}/{linearization_name}/codeinfo/{code}"
    parsed_response = _fetch_and_parse_response(uri, api_ver)

    try:
        linearization_uri = parsed_response["stemId"]
        return extract_stem_id(linearization_uri)
    except KeyError as key_err:
        raise KeyError(
            f"Could not find stemId in response from the ICD API for the code {code}. "
            f"Response: {parsed_response}"
        ) from key_err


def fetch_info(
    stem_id: str,
    release: str = "2023-01",
    linearization_name: str  = "mms",
    api_ver: int = 2,
) -> dict:
    """
    Fetch the information of an entry from the ICD API using its stem ID.

    When knowing the linearization ID of an entry, this function can be used to fetch
    the information of the entry, like a definition or its parent/children.

    For residual categories, the API does not provide any information, so this
    function will return a dummy definition.
    """
    hostname = get_hostname()
    uri = f"http://{hostname}/icd/release/11/{release}/{linearization_name}/{stem_id}"
    return _fetch_and_parse_response(uri, api_ver)


def _depth_from_title(title: str) -> int:
    """Count the number of dashes at the beginning of the title."""
    dashes = re.match(r"^(\-\s)*", title).group(0)
    return dashes.count("-") + 1


def extract_stem_id(linearization_uri: str) -> str:
    """
    Extract the stem ID from a linearization URI.

    The stem ID is the numeric ID of an entry in the ICD API and every linearization
    URI ends with it, or with the stem ID followed by a slash and either the word
    'other' or 'unspecified' for residual categories.

    So, possible linearization URIs are:
    - http://id.who.int/icd/release/11/2023-01/mms/1643222460
    - http://id.who.int/icd/release/11/2023-01/mms/1643222460/other
    - http://id.who.int/icd/release/11/2023-01/mms/1643222460/unspecified

    In the latter two cases, the stem ID should include the 'other' or 'unspecified'
    part, so that the stem ID is unique.

    Hence, the correct stem ID for the above URIs would be:
    - 1643222460
    - 1643222460/other
    - 1643222460/unspecified
    """
    stem_id = linearization_uri.split("/")[-1]
    if stem_id in ["other", "unspecified"]:
        stem_id = "/".join(linearization_uri.split("/")[-2:])
    return stem_id


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

    @staticmethod
    def from_api(stem_id, **api_kwargs) -> ICD11Entry:
        """
        Create an entry from the ICD API using its stem ID.
        """
        parsed_response = fetch_info(stem_id=stem_id, **api_kwargs)
        if "classKind" not in parsed_response:
            raise ValueError(
                f"Could not find classKind in response from the ICD API for stem ID "
                f"{stem_id}. Response: {parsed_response}"
            )

        if parsed_response["classKind"] == "chapter":
            new_entry = ICD11Chapter(
                code=parsed_response["code"],
                title=parsed_response["title"]["@value"],
                stem_id=stem_id,
            )
        elif parsed_response["classKind"] == "block":
            block_code = "BlockL?-???"
            for key in ["blockId", "codeRange"]:
                if key in parsed_response:
                    block_code = parsed_response[key]
                    break

            new_entry = ICD11Block(
                code=block_code,
                title=parsed_response["title"]["@value"],
                stem_id=stem_id,
            )
        elif parsed_response["classKind"] == "category":
            new_entry = ICD11Category(
                code=parsed_response["code"],
                title=parsed_response["title"]["@value"],
                stem_id=stem_id,
            )
        else:
            raise ValueError(
                f"Unknown class kind {parsed_response['classKind']} for stem ID {stem_id}"
            )

        for child_uri in parsed_response.get("child", []):
            child_stem_id = extract_stem_id(child_uri)
            try:
                child = ICD11Entry.from_api(stem_id=child_stem_id, **api_kwargs)
                new_entry.add_child(child)
            except ValueError:
                pass

        new_entry._api_info = parsed_response
        return new_entry

    @property
    def is_residual(self) -> bool:
        """
        Check whether the entry is a residual category.

        Residual categories are categories that are not further specified.
        """
        return self.stem_id in ["other", "unspecified"]

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
                release=self.release,
                linearization_name="mms",
                api_ver=2,
            )

        return self._api_info

    @property
    def description(self) -> str:
        """
        Description of the entry.
        """
        for key in ["definition", "longDefinition"]:
            if key in self.api_info:
                return self.api_info[key]["@value"]

        logger.info(f"Could not find description for {self}")
        return ""


class ICD11Root(ICDRoot, ICD11Entry):
    """
    Subclass of the `ICDRoot` to provide classmethods for generating the codex from
    either a pandas `DataFrame` or directly from the ICD API.
    """
    @classmethod
    def from_api(cls, **api_kwargs) -> ICD11Root:
        """
        Create the root of the ICD from the ICD API.

        Additional keyword arguments, like the `release` of the linearization, are
        passed to the `fetch_root` function.

        Note that this way of generating the codex is very expensive, as it consists
        of ca. 35,000 API calls. Therefore, this method should only be used with a
        locally running instance of the ICD API. Also, it is much slower than the
        `get_codex` method that constructs the codex from the simple tabulation.

        An advantage of this method is that it is always up-to-date. Also, it
        automatically fetches all information related to an entry, including its
        description. This is not the case when using the simple tabulation and looking
        up the description in that case requires an API call.
        """
        warnings.warn(
            "Fetching ICD-11 codex from ICD API consists of ca. 35,000 API calls.",
            ManyAPICallsWarning,
        )

        parsed_response = fetch_root(**api_kwargs)
        root = cls(
            code="ICD-11 root",
            title=parsed_response["title"]["@value"],
            release=parsed_response["releaseId"],
            stem_id="",
        )

        for child_uri in parsed_response["child"]:
            child_stem_id = extract_stem_id(child_uri)
            child = ICD11Entry.from_api(stem_id=child_stem_id, **api_kwargs)
            root.add_child(child)

        root._api_info = parsed_response
        return root


class ICD11Chapter(ICDChapter, ICD11Entry):
    """
    Subclass of the general `ICDChapter` adapted for the 11th revision of the ICD.
    """
    @classmethod
    def from_series(cls, row: pd.Series) -> ICD11Chapter:
        """
        Create chapter from a pandas series.
        """
        return cls(
            code=row["ChapterNo"],
            title=row["Title"],
            stem_id=extract_stem_id(row["Linearization (release) URI"]),
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
            stem_id=extract_stem_id(row["Linearization (release) URI"]),
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
            stem_id=extract_stem_id(row["Linearization (release) URI"]),
        )


def get_codex(table: Optional[pd.DataFrame] = None, verbose: bool = True) -> ICD11Root:
    """
    Get the entire ICD 11 codex from a simple tabulation as an `ICD11Root` object.

    This function simply iterates over the simple tabulation that can be downloaded
    from the [browser] of the WHO's ICD 11 ([direct link]). This table ships with an
    installation of this package and the latest of these tables is automatically used
    by this function. But it may also be provided as the `table` argument to this
    function.

    While iterating over the rows in the tabulation, it adds the entries to the codex
    based on their depth. The depth is inferred from the number of dashes in the title
    of the entry.

    E.g., the block with code `BlockL2-MB4` has the title
    `- - symptoms or signs involving the nervous system` in the simple tabulation.
    Hence, its depth is 2 and it is added as a child of the last block with depth 1.

    Note that in the ICD [browser], no code is assigned to the blocks.

    [direct link]: https://icd.who.int/browse11/Downloads/Download?fileName=simpletabulation.zip
    [browser]: https://icd.who.int/browse11/l-m/en

    Compared to the `from_api` method of the `ICD11Root` class, this method is much
    faster, but it is not always up-to-date. Also, it does not fetch the description
    of the entries by default. Consequently, when one wants to access the description
    of an entry, an additional API call is made.
    """
    if table is None:
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
