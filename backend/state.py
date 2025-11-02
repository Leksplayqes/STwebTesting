"""Shared mutable state containers used across backend modules."""
from __future__ import annotations

from subprocess import Popen
from typing import Any, Dict

RUNNING_UTIL_PROCS: Dict[str, Any] = {}
RUNNING_PROCS: Dict[str, Popen] = {}

__all__ = [
    "RUNNING_UTIL_PROCS",
    "RUNNING_PROCS",
]
