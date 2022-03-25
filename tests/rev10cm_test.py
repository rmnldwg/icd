import os
import random
import pytest
import hypothesis
from hypothesis import given, assume, settings
import hypothesis.strategies as st
import untangle
import requests

import icd
from icd.base import ICDChapter, ICDEntry
from icd.rev10cm import (
    ICD10CMRoot, 
    ICD10CMChapter, 
    ICD10CMBlock, 
    ICD10CMCategory,
    download_from_CDC,
    get_codex
)


@pytest.fixture(params=["2019", "2020", "2021", "2022"], scope="session")
def codex(request):
    return icd.rev10cm.get_codex(release=request.param)


@given(
    chapter_num=st.integers(1,3000),
    start_code=st.characters(min_codepoint=65, max_codepoint=90),
    mid_code=st.characters(min_codepoint=65, max_codepoint=90),
    end_code=st.characters(min_codepoint=65, max_codepoint=90)
)
@settings(suppress_health_check=hypothesis.HealthCheck.all())
def test_entry(chapter_num, start_code, mid_code, end_code):
    """
    Test basic functionalities of the individual ICD-10-CM entries.
    """
    assume(start_code <= mid_code < end_code)
    release = "testrelease"
    root = ICD10CMRoot(_release=release)
    chapter = ICD10CMChapter(chapter_num, "Test Chapter")
    block = ICD10CMBlock(code=f"{start_code}-{end_code}", title="Test Block")
    sub_block1 = ICD10CMBlock(code=mid_code, title="Test Subblock 1")
    sub_block2 = ICD10CMBlock(
        code=chr(ord(mid_code) + 1), 
        title="Test Subblock 2"
    )
    category = ICD10CMCategory(f"{mid_code}.1", "Test category")
    
    root.add_child(chapter)
    chapter.add_child(block)
    assert block.should_contain(sub_block1), "Block should contain sub block 1"
    block.add_child(sub_block1)
    assert root.tree() == sub_block1.ancestry(), (
        "For linear tree, `tree()` and `ancestry()` must be same"
    )
    assert block.should_contain(sub_block2), "Block should contain sub block 2"
    block.add_child(sub_block2)
    sub_block1.add_child(category)
    
    assert root.exists(chapter.code), "chapter doesn't seem to exist"
    assert chapter in root.search(chapter.code), "Didn't find chapter"
    assert root.exists(block.code), "block doesn't seem to exist"
    assert block in root.search(block.code), "Didn't find block"
    assert root.exists(sub_block1.code), "sub block 1 doesn't seem to exist"
    assert sub_block1 in root.search(sub_block1.code), "Didn't find sub_block1"
    assert root.exists(sub_block2.code), "sub block 2 doesn't seem to exist"
    assert sub_block2 in root.search(sub_block2.code), "Didn't find sub_block2"
    assert root.exists(category.code), "category doesn't seem to exist"
    assert category in root.search(category.code), "Didn't find category"
    
    assert chapter in root.children, "Chapter isn't child of root"
    assert block in chapter.children, "Block isn't child of chapter"
    assert sub_block1 in block.children, "Sub block 1 isn't child of block"
    assert sub_block2 in block.children, "Sub block 2 isn't child of block"
    
    assert chapter.parent == root, "Root isn't parent of chapter"
    assert block.parent == chapter, "Chapter isn't parent of block"
    assert sub_block1.parent == block, "Block isn't parent of sub block 1"
    assert sub_block2.parent == block, "Block isn't parent of sub block 2"
    
    block.remove_child(sub_block2)
    
    assert sub_block2.parent is None, "Removed child still has parent"
    assert sub_block2 not in block.children, "Removed child is still child"
    
    chapter.add_child(sub_block2)
    
    assert sub_block2 not in chapter.children, (
        "sub block 2 should have been added to the block, not the chapter"
    )
    assert sub_block2 in block.children, "sub block 2 schould be block's child"
    assert sub_block2.parent == block, "Sub block 2 parent is not block"
    
    
def test_entries(codex):
    entries = list(codex.entries)
    entry_subset = random.sample(entries, k=100)
    revision = "10-CM"
    release = codex.release
    
    for entry in entry_subset:
        assert codex.exists(entry.code), "entry does not seem to exist"
        assert entry in codex.search(entry.code), "entry not in search results"
        assert entry.revision == revision, "Not all entries have same revision"
        assert entry.release == release, "Not all entries have the same release"
        assert entry.get_root() == codex, "Root of entries must be codex root"
        assert all([child.parent == entry for child in entry.children]), (
            "All entrie's children must have entry as parent."
        )
        sum_len_children = sum([len(child) for child in entry.children])
        assert len(entry) == sum_len_children + 1, (
            "Length of entry must match sum of length of children + 1"
        )
        if entry.depth_in_kind > 1:
            assert type(entry.parent) == type(entry), (
                "If `depth_in_kind` is larger than 1, parent and child must be "
                "same type."
            )
        tree_str = entry.tree()
        num_lines = tree_str.count("\n")
        assert num_lines == len(list(entry.entries)), (
            "Tree must list all entries under current"
        )


def test_request(codex):
    """Test whether the ICD API request works."""
    leaves = list(codex.leaves)
    leaf_subset = random.sample(leaves, k=10)
    
    for leaf in leaf_subset:
        response_list = leaf.request()
        for response in response_list:
            assert leaf.code in response[0], (
                "Responded code not same as leaf code"
            )
            assert leaf.title in response[1], (
                "Responded title not same as leaf title"
            )


def test_root(codex):
    root = codex
    assert isinstance(root, ICD10CMRoot), "Root must be `ICD10CMRoot` object."
    assert root.code == "ICD-10-CM", "Root has wrong code"
    exp_title = (
        "International Classification of Diseases, Tenth Revision, Clinical "
        f"Modification, {root.release} release"
    )
    assert root.title == exp_title, "Root has wrong title"
    assert all([isinstance(child, ICD10CMChapter) for child in root.children]), (
        "All children of root entry must be chapters"
    )
    assert root.kind == "root"
    assert root.parent is None, "Root cannot have parents."
    assert root.is_root, "Root must have `is_root == True`."
    assert not root.is_leaf, "Root cannot be leaf."
    assert root.get_root() == root, "Root of root must be root."
    assert hasattr(root, "chapter")
    for code, chapter in root.chapter.items():
        assert chapter.code == code, "Chapter dict of root incorrect"


def test_chapter(codex):
    chapters = codex.children
    for chapter in chapters:
        assert isinstance(chapter, ICD10CMChapter), (
            "Chapter must be instance of `ICD10CMChapter`"
        )
        assert chapter.kind == "chapter", "Chapter must be of kind 'chapter'"
        assert all([isinstance(child, ICD10CMBlock) for child in chapter.children]), (
            "Children of chapters must be blocks"
        )
        assert isinstance(chapter.parent, ICD10CMRoot), (
            "Parent of chapter must be root"
        )
        assert hasattr(chapter, "block")
        for code, block in chapter.block.items():
            assert block.code == code, "Block dict of chapter incorrect"


def test_codex(codex):
    """
    Test some core functionalities of a loaded codex.
    """
    assert isinstance(codex, ICD10CMRoot), (
        "`get_codex()` did not return root object"
    )
    assert all([isinstance(child, ICDChapter) for child in codex.children]), (
        "Children of root must be chapters"
    )
    len_codex = len(codex)
    assert len_codex > 1, "Codex contains only root entry"
    assert len_codex == len(list(codex.entries)), (
        "`len` does not seem to report number of entries"
    )
    assert len_codex >= len(list(codex.leaves)), (
        "Codex must have more entries than leaves"
    )
    assert all([leaf.is_leaf for leaf in codex.leaves]), (
        "Iterator over leaves returned objects that aren't leaves"
    )
    assert all([isinstance(entry, ICDEntry) for entry in codex.entries]), (
        "Not all entries are ICD objects"
    )


@pytest.mark.parametrize("release", ["2019", "2020", "2021", "2022"])
def test_download_from_CDC(tmpdir, release):
    """
    Make sure downloading from the CDC website works.
    """
    with pytest.raises(requests.RequestException):
        download_from_CDC(custom_url="https://made.up/file.xml")
    
    with pytest.raises(IOError):
        download_from_CDC(save_path="/made/up/path")
    
    download_from_CDC(release=release, save_path=tmpdir)
    tmp_file_path = tmpdir / f"icd10cm_tabular_{release}.xml"
    assert os.path.exists(str(tmp_file_path)), (
        f"Temporary directory {tmp_file_path} does not exist"
    )
    xml_root = untangle.parse(tmp_file_path).ICD10CM_tabular
    codex = ICD10CMRoot.from_xml(xml_root)
    assert isinstance(codex, ICD10CMRoot), (
        "Codex was not created"
    )