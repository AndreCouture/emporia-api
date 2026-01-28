"""Emporia API - Python wrapper for Emporia Energy devices."""

from .__version__ import __version__, __version_info__
from .api import EmporiaAPI

__all__ = ["EmporiaAPI", "__version__", "__version_info__"]
