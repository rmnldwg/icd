"""
Test the implementation of `icd.rev11`.
"""
import pandas as pd

from icd.rev11 import ICD11Root
from icd._config import DATA_DIR

def test_codex_creation():
    """Check if the codex gets generated correclty."""
    data_table = pd.read_csv(DATA_DIR / "icd-11" / "simpletabulation.csv")
    root = ICD11Root.from_table(data_table)

    assert root.is_root
    assert root.code == "ICD-11 root"
    assert root.title == (
        "International Statistical Classification of Diseases and "
        "Related Health Problems, 11th Revision"
    )
    assert len(root.children) == 26

    scc_of_pharyngeal_tonsil = root.get("2B6B.20")
    assert scc_of_pharyngeal_tonsil.code == "2B6B.20"
    assert scc_of_pharyngeal_tonsil.is_leaf
    assert scc_of_pharyngeal_tonsil.parent == root.get("2B6B.2")
