import pkg_resources
from pathlib import Path

DATA_DIR = Path(pkg_resources.resource_filename("icd", "_data"))
