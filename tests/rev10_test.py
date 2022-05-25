from numpy import isin
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st
import requests

from icd.rev10 import (
    ICD10Block, ICD10Category, ICD10Chapter, ICD10Root, get_codex
)


ICD10_CODEX = get_codex()

@st.composite
def st_entry_from_codex(draw, icd10_codex = ICD10_CODEX):
    """Strategy for drawing entries from the codex."""
    return draw(st.sampled_from(list(icd10_codex.entries)))


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
    """"""


class TestICD10Chapter:
    """"""


class TestICD10Block:
    """"""


class TestICD10Category:
    """"""
