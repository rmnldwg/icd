"""
## Module to handle ICD-10-CM

This independently developed python module implements the **International 
Classification of Diseases, tenth revision, Clinical Modification** (ICD-10-CM) 
as defined by the **Centers for Disease Control and Prevention** (CDC).

It differs slightly from the ICD-10 as defined by the WHO, namely in the 
following ways:
1. It publishes releases every year
2. Those releases are published openly at its [download area](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/)
3. The CDC provides its own easy-to-use [API](https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional

import untangle
import requests
from tqdm import tqdm

from ._config import DATA_DIR
from .rev10 import (
    ICD10Entry, ICD10Root, ICD10Chapter, ICD10Block, ICD10Category
)


@dataclass
class ICD10CMEntry(ICD10Entry):
    """
    Class representing an entry in the ICD-10-CM system.
    """
    revision: str = "10-CM"
    
    def request(self):
        """
        Return information on an entry of the ICD-10-CM from the CDC's API.
        
        No authentication is needed to access this API.
        """
        uri = (
            "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?"
            f"sf=code,name&terms={self.code}"
        )
        
        response = requests.get(uri)
        if response.status_code != requests.codes.ok:
            raise requests.HTTPError(
                f"Request failed with code {response.status_code}"
            )
        
        # a bit hacky (and potentially dangerous) way to get the array from 
        # the returned string...
        null = None
        code_list = eval(response.content.decode())[3]
        return code_list


@dataclass
class ICD10CMRoot(ICD10Root, ICD10CMEntry):
    """
    This subclass of `ICD10Root` implements its own `from_xml` method, because 
    the way the CDC and the WHO make their XML data available differs.
    """
    title: str = field(init=False)
    
    def __post_init__(self):
        tmp = super().__post_init__()
        self.title = (
            "International Classification of Diseases, Tenth Revision, "
            f"Clinical Modification, {self.release} release")
        return tmp
    
    @classmethod
    def from_xml(cls, xml_root: untangle.Element) -> ICD10CMRoot:
        """
        Create root and entire ICD-10-CM tree from the root entry in the 
        CDC's XML files.
        """
        root = cls(_release=xml_root.version.cdata)        
        for xml_chapter in xml_root.chapter:
            root.add_child(ICD10CMChapter.from_xml(xml_chapter))
        return root

@dataclass
class ICD10CMChapter(ICD10Chapter, ICD10CMEntry):
    """"""    
    @classmethod
    def from_xml(cls, xml_chapter: untangle.Element) -> ICD10CMChapter:
        """Create chapter from respective XML chapter entry."""
        chapter = cls(
            code=xml_chapter.name.cdata,
            title=xml_chapter.desc.cdata,
        )
        for xml_section in xml_chapter.section:
            chapter.add_child(ICD10CMBlock.from_xml(xml_section))
        
        return chapter

@dataclass
class ICD10CMBlock(ICD10Block, ICD10CMEntry):
    """"""
    @classmethod
    def from_xml(cls, xml_section: untangle.Element) -> ICD10Block:
        """Create block of ICD-10-CM categories from XML section"""
        block = cls(
            code=xml_section["id"],
            title=xml_section.desc.cdata,
        )
        if hasattr(xml_section, "diag"):
            for xml_diag in xml_section.diag:
                block.add_child(ICD10CMCategory.from_xml(xml_diag))
        
        return block


@dataclass
class ICD10CMCategory(ICD10Category, ICD10CMEntry):
    """"""
    @classmethod
    def from_xml(cls, xml_diag: untangle.Element) -> ICD10CMCategory:
        """Recursively create tree of categories and subcategories from XML."""
        category = cls(
            code=xml_diag.name.cdata,
            title=xml_diag.desc.cdata,
        )
        if hasattr(xml_diag, "diag"):
            for xml_subdiag in xml_diag.diag:
                category.add_child(ICD10CMCategory.from_xml(xml_subdiag))
        
        return category


def get_codex(
    release: int, 
    download: bool = True, 
    verbose: bool = False
) -> ICD10CMRoot:
    """
    Parse ICD-10-CM codex of given release. Download respective data if 
    necessary.
    
    The `release` argument refers to the fiscal year the data was released and 
    determines which data is used. If the data is not available at the 
    directory, but `download` is set to `True`, then the file is downloaded 
    from the CDC.
    
    Set `vebose` to `True` if you want to track the progress of the download.
    """
    verboseprint = print if verbose else lambda *a, **k: None
    
    xml_path = os.path.join(
        DATA_DIR, "icd-10-cm/",f"icd10cm_tabular_{release}.xml"
    )
    
    verboseprint(f"Looking for XML file at {xml_path}...", end="")
    if not os.path.exists(xml_path) and download:
        verboseprint("FAILED, attempting download:")
        download_from_CDC(release, verbose=verbose)
    elif not os.path.exists(xml_path):
        raise IOError(
            f"File {xml_path} does not exist. Try setting `download` to `True` "
            "to automatically download the file from the CDC."
        )
    else:
        verboseprint("FOUND")
    
    verboseprint("Parsing...", end="")
    xml_root = untangle.parse(xml_path).ICD10CM_tabular
    codex = ICD10CMRoot.from_xml(xml_root)
    verboseprint("SUCCESS")
    return codex


def download_from_CDC(
    release: int = 2022, 
    custom_url: Optional[str] = None, 
    save_path: Optional[str] = None,
    verbose: bool = False,
):
    """Download ICD XML file from the CDC's website.
    
    The `release` refers to the fiscal year the data was released in. With 
    `custom_url` one can overwrite the default download url from the CDC 
    https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICDCM/<release>/icd10cm_tabular_<release>.xml. 
    Note that the CDC provides files with the name `icd10cm_tabular_<release>.xml` 
    only since 2019. So, if you need earlier data, you might want to check out 
    how the files were named before that youself.
    
    `save_path` overwrites the default path to save the downloaded file in.
    """
    verboseprint = print if verbose else lambda *a, **k: None
    
    if custom_url is not None:
        url = custom_url
    else:
        url = (
            "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/"
            f"ICDCM/{release}/icd10cm_tabular_{release}.xml"
        )
    
    verboseprint("Requesting file from URL...", end="")
    response = requests.get(url, stream=True)
    
    if response.status_code != requests.codes.ok:
        raise requests.RequestException(
            f"Downloading failed with status code {response.status_code}"
        )
    verboseprint("SUCCESS")
    
    verboseprint("Preparing save directory...", end="")
    if save_path is not None and not os.path.exists(save_path):
        raise IOError(f"No such directory: {save_path}")
    else:
        save_path = os.path.join(
            DATA_DIR, "icd-10-cm/", f"icd10cm_tabular_{release}.xml"
        )
    verboseprint("SUCCESS")
    
    total_size = int(response.headers.get("content-length", 0))
    block_size = 1024
    progress_bar = tqdm(
        total=total_size, 
        unit="iB", 
        unit_scale=True,
        desc="Downloading XML file",
        disable=not verbose
    )
    
    with open(save_path, 'wb') as xml_file:
        for binary_data in response.iter_content(block_size):
            xml_file.write(binary_data)
            progress_bar.update(len(binary_data))
    
    progress_bar.close()
    
    if verbose and total_size != 0 and total_size != progress_bar.n:
        raise RuntimeError(
            f"Downloaded file seems incomplete. Check file at {save_path}"
        )