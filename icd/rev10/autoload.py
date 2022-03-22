"""
Loads the stored XML data using the dataclass `ICD10Root`.
"""

import os
import untangle

from .classes import ICD10Root
from ..config import DATA_DIR


xml_file_path = os.path.join(DATA_DIR, "icd10cm_tabular_2022.xml")
xml_data = untangle.parse(xml_file_path).ICD10CM_tabular
codex = ICD10Root.from_xml(xml_data)