import pytest
import hypothesis.strategies as st

import icd
from icd.base import ICDChapter, ICDEntry


@pytest.mark.parametrize("release", ["2019", "2020", "2021", "2022"])
def test_codex(release):
    codex = icd.rev10cm.get_codex(release=release)
    
    assert isinstance(codex, icd.rev10cm.ICD10CMRoot), (
        "`get_codex()` did not return root object"
    )
    assert all([isinstance(child, ICDChapter) for child in codex.children]), (
        "Children of root must be chapters"
    )
    len_codex = len(codex)
    assert len_codex > 1, (
        "Codex contains only root entry"
    )
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