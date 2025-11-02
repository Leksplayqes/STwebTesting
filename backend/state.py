"""Shared mutable state containers used across backend modules."""
from __future__ import annotations

import threading
from subprocess import Popen
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .tunnel_manager import TunnelLease

RUNNING_UTIL_PROCS: Dict[str, Any] = {}
RUNNING_PROCS: Dict[str, Popen] = {}
ACTIVE_TUNNEL_LOCK = threading.RLock()
ACTIVE_TUNNEL_LEASES: Dict[str, "TunnelLease"] = {}

__all__ = [
    "RUNNING_UTIL_PROCS",
    "RUNNING_PROCS",
    "ACTIVE_TUNNEL_LOCK",
    "ACTIVE_TUNNEL_LEASES",
]
