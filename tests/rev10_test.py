import pytest
import requests
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from icd.rev10 import (
    ICD10Block,
    ICD10Chapter,
    ICD10Root,
    get_codex,
)

ICD10_CODEX = get_codex()

# pylint: disable=no-method-argument
# pylint: disable=no-self-argument

@st.composite
def st_entry_from_codex(draw, icd10_codex = ICD10_CODEX):
    """Strategy for drawing entries from the codex."""
    return draw(st.sampled_from(list(icd10_codex.entries)))

@st.composite
def st_block(draw):
    """
    Strategy for generating `ICD10Block` instances.
    """
    st_tmp_text = st.text(
        alphabet=st.characters(whitelist_categories=['L', 'N']),
        min_size=1,
        max_size=5,
    )
    start_code = draw(st_tmp_text)
    if (end_code := draw(st_tmp_text)) is not None and end_code > start_code:
        code = f"{start_code}-{end_code}"
    else:
        code = start_code

    title = draw(st.text())

    return ICD10Block(code, title)


class TestICD10Entry:
    """Mainly test the `request` method that interfaces with WHO's API."""
    @given(
        entry=st_entry_from_codex()
    )
    @settings(max_examples=5, deadline=10000)
    def test_request(self, entry):
        """Testing the `request` method for accessing info from the WHO API."""
        assume(entry.kind != "root")
        with pytest.raises(ValueError):
            entry.request(auth_method="args")

        with pytest.raises(requests.HTTPError):
            entry.request(
                auth_method="args",
                icd_api_id="foo",
                icd_api_secret="bar"
            )

        response = entry.request(auth_method="env")
        assert response["code"] == entry.code
        assert response["title"]["@value"] == entry.title
        assert response["classKind"] == entry.kind


class TestICD10Root:
    """Tests regarding the root class of ICD-10."""
    @given(
        title=st.text(),
        release=st.text(),
    )
    def test___init__(self, title, release):
        """Test the constructor."""
        root = ICD10Root(title, release)
        assert root.code == "ICD-10 root"
        assert root.title == title
        assert root.release == release


class TestICD10Chapter:
    """Test the base implementation `icd.base.ICD10Chapter`."""
    @given(
        code=st.integers(min_value=1, max_value=3400),
        title=st.text(),
    )
    def test___init__(self, code, title):
        """Test constructor"""
        chapter = ICD10Chapter(code, title)

        assert all(c in "IVXLCDM" for c in chapter.code)
        assert chapter.title == title
        assert chapter.kind == "chapter"


class TestICD10Block:
    """Test the `icd.rev10.ICD10Chapter` implementation."""
    @given(block=st_block())
    def test_start_code(self, block):
        """Make sure that the start code is extracted correctly."""
        assert '-' not in block.start_code
        if '-' not in block.code:
            assert block.code == block.start_code

    @given(block=st_block())
    def test_end_code(self, block):
        """Check that the end code is extracted correctly."""
        assert '-' not in block.end_code
        if '-' not in block.code:
            assert block.end_code == block.start_code
        else:
            assert block.end_code > block.start_code

    @given(block=st_block(), inside_block=st_block())
    def test_should_contain(self, block, inside_block):
        """Test the `should_contain` method."""
        assert not block.should_contain("foo")
        assert not block.should_contain(block)
        if block.should_contain(inside_block):
            assert block.start_code <= inside_block.start_code
            assert block.end_code >= inside_block.end_code
        else:
            assert (
                block.start_code > inside_block.start_code or
                block.end_code < inside_block.end_code
            )


class TestICD10Category:
    """TODO"""
