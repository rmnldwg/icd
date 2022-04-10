import pytest

from icd.base import ICDChapter, ICDEntry
from icd.rev10 import (ICD10Block, ICD10Category, ICD10Chapter, ICD10Root,
                       get_codex)


@pytest.mark.parametrize(
    ["number", "roman_numeral"],
    [
        (1, 'I'),
        (3, 'III'),
        (4, 'IV'),
        (13, 'XIII'),
        (45, 'XLV'),
        (78, 'LXXVIII'),
        (173, 'CLXXIII'),
        (2821, 'MMDCCCXXI'),
    ]
)
def test_romanization(number, roman_numeral):
    """Check that the romanization of chapter numbers works."""
    assert ICD10Chapter.romanize(number) == roman_numeral, "Romanization wrong"
