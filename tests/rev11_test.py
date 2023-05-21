"""
Test the implementation of `icd.rev11`.
"""
from icd.rev11 import get_codex


def test_codex_creation():
    """Check if the codex gets generated correclty."""
    root = get_codex()

    assert root.is_root
    assert root.code == "ICD-11 root"
    assert root.title == (
        "International Statistical Classification of Diseases and "
        "Related Health Problems, 11th Revision"
    )
    assert len(root.children) == 28

    scc_of_pharyngeal_tonsil = root.get("2B6B.20")
    assert scc_of_pharyngeal_tonsil.code == "2B6B.20"
    assert scc_of_pharyngeal_tonsil.title == "Squamous cell carcinoma of pharyngeal tonsil"
    assert scc_of_pharyngeal_tonsil.is_leaf
    assert scc_of_pharyngeal_tonsil.parent == root.get("2B6B.2")
    assert scc_of_pharyngeal_tonsil.root == root
