"""
.. include:: ../README.md
"""
import logging
import os
logging.basicConfig(
    format='[%(levelname)8s]: %(message)s',
    level=os.environ.get("ICD_LOG_LEVEL", "WARNING"),
)

from . import rev10, rev10cm, rev11
from ._version import version

__version__ = version
__all__ = ["rev10", "rev10cm", "rev11"]
