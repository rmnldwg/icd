"""
## Python module for use with the base ICD-10

This is an independent python implementation of the **International Statistical
Classification of Diseases and Related Health Problems, 10th Revision**
(ICD-10) as defined by the **World Health Organization** (WHO).

The data files are obtained from the WHO's [download area][WHO download],
which requires one to be logged in to access the underlying files.

[WHO download]: https://apps.who.int/classifications/apps/icd/ClassificationDownload/DLArea/Download.aspx
"""
from __future__ import annotations

import os
from typing import Optional

import requests
import untangle
from rich.progress import track

from ._config import DATA_DIR
from .base import ICDBlock, ICDCategory, ICDChapter, ICDEntry, ICDRoot


class ICD10Entry(ICDEntry):
    """
    Class representing an entry in the 10th ICD revision.
    """
    revision: str = "10"

    def request(
        self,
        auth_method: str = "args",
        icd_api_id: Optional[str] = None,
        icd_api_secret: Optional[str] = None,
        api_ver: int = 2,
        lang: str = "en",
    ) -> str:
        """
        Return information on an entry from WHO's ICD API.

        This function provides two ways for authenticating to the API: One can
        simply provide the `ClientId` as `icd_api_id` and the `ClientSecret` as
        `icd_api_secret`, in which case `auth_method` must be set to `"args"`.
        Or the two strings can be set as environment variables aptly named
        `ICD_API_ID` and `ICD_API_SECRET`. In that case, set `auth_method` to
        `"env"`.

        There are two major versions of the ICD API that can be chosen by
        setting `api_ver` to either `1` ot `2`.

        The API provides its response in different languages, which can be
        selected by setting `lang`, e.g. to `"en"`.
        """
        if auth_method == "env":
            icd_api_id = os.environ["ICD_API_ID"]
            icd_api_secret = os.environ["ICD_API_SECRET"]
        elif auth_method != "args":
            raise ValueError("`auth_method` must be either 'args' or 'env'.")

        if icd_api_id is None or icd_api_secret is None:
            raise ValueError("Both ICD_API_ID and ICD_API_SECRET must be set.")

        # Authenticate
        token_endpoint = "https://icdaccessmanagement.who.int/connect/token"
        payload = {
            "client_id": icd_api_id,
            "client_secret": icd_api_secret,
            "scope": "icdapi_access",
            "grant_type": "client_credentials"
        }
        response = requests.post(token_endpoint, data=payload)
        if response.status_code != requests.codes.ok:
            raise requests.HTTPError("Access denied.")
        access_token = response.json()["access_token"]

        # Make request
        uri = f"https://id.who.int/icd/release/10/{self.release}/{self.code}"
        headers = {
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
            "Accept-Language": lang,
            "API-Version": f"v{api_ver}",
        }
        response = requests.get(uri, headers=headers)

        # check if request was successful, if not, try to get another release
        if response.status_code != requests.codes.ok:
            fallback_uri = f"https://id.who.int/icd/release/10/{self.code}"
            response = requests.get(fallback_uri, headers=headers)

            if response.status_code == requests.codes.ok:
                latest_uri = response.json()["latestRelease"]
                response = requests.get(latest_uri, headers=headers)
            else:
                raise requests.HTTPError(
                    f"Could not resolve code {self.code}",
                    response=response
                )

        return response.json()


class ICD10Root(ICDRoot, ICD10Entry):
    """
    Subclass of the base `ICDRoot` that implements a method `from_xml` to load
    the ICD-10 codex from an XML file as provided by the WHO.
    """
    def __init__(self, title: str, release: str, *args, **kwargs):
        super().__init__(
            "ICD-10 root",
            title,
            release,
            *args,
            **kwargs,
        )

    @classmethod
    def from_xml(cls, xml_title: untangle.Element) -> ICD10Root:
        """Create root from XML Title element."""
        root = cls(
            title=xml_title.cdata,
            release=xml_title["version"]
        )
        return root


class ICD10Chapter(ICDChapter, ICD10Entry):
    """
    Subclass of the general `ICDChapter` class implementing a specialized
    XML parsing method for initialization.
    """
    def __init__(self, code: str, title: str, *args, **kwargs):
        """Romanize the chapter number if necessary."""
        if (
            isinstance(code, str)
            and
            all(c in "IVXLCDM" for c in code)
        ):
            super().__init__(code, title, *args, **kwargs)
            return

        try:
            chapter_num = int(code)
        except ValueError as val_err:
            raise ValueError("Chapter number must be integer") from val_err

        code = self.romanize(chapter_num)
        super().__init__(code, title, *args, **kwargs)

    @classmethod
    def from_xml(
        cls,
        xml_class: untangle.Element,
        root: ICD10Root
    ) -> ICD10Chapter:
        """Create a chapter from an XML Class element."""
        for r in xml_class.Rubric:
            if r["kind"] == "preferred":
                preferred_title = r.Label.cdata
        chapter = cls(
            code=xml_class["code"],
            title=preferred_title
        )
        root.add_child(chapter)
        return chapter


class ICD10Block(ICDBlock, ICD10Entry):
    """
    Class inheriting from `ICDBlock` that implements a XML parsing method
    as well as functionality to infer whether another block should be be a
    descendant of the current one.
    """
    @classmethod
    def from_xml(cls, xml_class: untangle.Element, *_) -> ICD10Block:
        """Create a block from an XML Class element."""
        for rubric in xml_class.Rubric:
            if rubric["kind"] == "preferred":
                preferred_title = rubric.Label.cdata
        block = cls(
            code=xml_class["code"],
            title=preferred_title
        )
        return block

    @property
    def start_code(self) -> str:
        """Returns the first ICD code included in this block."""
        return self.code.split("-", maxsplit=1)[0]

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
                "Block code must be <start_code>-<end_code> or only <code>, "
                f"but not {self.code}"
            )

    def should_contain(self, block: ICD10Block) -> bool:
        """Check whether this block should contain the given block"""
        if not isinstance(block, ICD10Block):
            return False

        if self == block:
            return False

        has_start_ge = block.start_code >= self.start_code
        has_end_le = block.end_code <= self.end_code
        if has_start_ge and has_end_le:
            return True

        return False


class ICD10Category(ICDCategory, ICD10Entry):
    """
    Subclass of `ICDCategory` implementing an XML parsing classmethod for
    initialization from WHO's data.
    """
    def __init__(self, code: str, title: str, *args, **kwargs):
        super().__init__(code, title, *args, **kwargs)

    @classmethod
    def from_xml(cls, xml_class: untangle.Element, *_) -> ICD10Category:
        """Create a category from an XML Class element."""
        for rubric in xml_class.Rubric:
            if rubric["kind"] == "preferred":
                preferred_title = rubric.Label.cdata
        category = cls(
            code=xml_class["code"],
            title=preferred_title
        )
        return category


def get_codex(release: str = "2019", verbose: bool = False) -> ICD10Root:
    """
    Parse ICD-10 XML codex given a release year and create an explorable tree
    of ICD-10 entries from it.

    Set `verbose` to `True` for progress update of data loading and parsing.
    """
    verboseprint = print if verbose else lambda *a, **k: None

    xml_path = os.path.join(
        DATA_DIR, "icd-10/", f"icd10{release}en.xml"
    )

    verboseprint(f"Looking for XML file at {xml_path}...", end="")
    if not os.path.exists(xml_path):
        verboseprint("FAILED")
        raise IOError(f"File {xml_path} does not exist")
    verboseprint("FOUND")

    verboseprint("Parsing XML...", end="")
    xml_root = untangle.parse(xml_path).ClaML
    verboseprint("SUCCESS")

    root = ICD10Root.from_xml(xml_title=xml_root.Title)
    xml_entry_dict = {}
    cls = {
        "chapter": ICD10Chapter,
        "block": ICD10Block,
        "category": ICD10Category
    }
    # put all xml entries and ICD objects (created from that entry) into one
    # large dictionary for easier connecting
    iterator = track(
        xml_root.Class,
        description="Create entries and sort by code",
        disable=not verbose
    )
    for xml_class in iterator:
        xml_entry_dict[xml_class["code"]] = (
            xml_class,
            cls[xml_class["kind"]].from_xml(xml_class, root)
        )

    iterator = track(
        xml_entry_dict.items(),
        description="Append entries to tree",
        disable=not verbose,
    )
    for _, xml_entry_tuple in iterator:
        xml_class, entry = xml_entry_tuple
        if hasattr(xml_class, "SubClass"):
            for subcls in xml_class.SubClass:
                sub_xml, sub_entry = xml_entry_dict[subcls["code"]]
                has_supercls = hasattr(sub_xml, "SuperClass")
                if has_supercls and sub_xml.SuperClass["code"] != entry.code:
                    raise RuntimeError(
                        "Parent code of child that is supposed to be added "
                        "does not match current entry"
                    )
                entry.add_child(sub_entry)
    verboseprint("DONE")

    return root
