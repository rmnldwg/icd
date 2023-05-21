"""
.. include:: ../README.md
"""
import logging
import os

from . import rev10, rev10cm, rev11
from ._version import version

__version__ = version
__all__ = ["rev10", "rev10cm", "rev11"]

logger = logging.getLogger("icd")
logger.setLevel(os.getenv("ICD_LOG_LEVEL", "WARNING"))

console_handler = logging.StreamHandler()
console_handler.setLevel(os.getenv("ICD_LOG_LEVEL", "WARNING"))

formatter = logging.Formatter("[%(levelname)8s] %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)
