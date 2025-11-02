"""Tunnel management service that encapsulates proxy state."""
from __future__ import annotations

import threading
from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from snmpsubsystem import ProxyController

from ..config import DEFAULT_TUNNEL_PORTS, get_tunnel_ports
from ..tunnel_manager import (
    TunnelConfigurationError,
    TunnelLease,
    TunnelManager,
    TunnelManagerError,
    TunnelPortsBusyError,
)


def _configured_ports() -> List[int]:
    try:
        return get_tunnel_ports()
    except Exception:
        return DEFAULT_TUNNEL_PORTS.copy()


class TunnelService:
    """Encapsulates the SNMP tunnel manager and active leases."""

    def __init__(
        self,
        *,
        controller: Optional[ProxyController] = None,
        ports: Optional[Iterable[int]] = None,
    ) -> None:
        self._controller = controller or ProxyController()
        self._manager = TunnelManager(self._controller, ports=ports or _configured_ports())
        self._lock = threading.RLock()
        self._tracked: Dict[str, TunnelLease] = {}

    # Lease management -------------------------------------------------
    def reserve(
        self,
        owner_id: str,
        owner_kind: str,
        *,
        ip: str,
        username: str,
        password: str,
        ttl: Optional[float] = None,
        track: bool = False,
    ) -> TunnelLease:
        lease = self._manager.lease(
            owner_id,
            owner_kind,
            ip=ip,
            username=username,
            password=password,
            ttl=ttl,
        )
        if track:
            with self._lock:
                previous = self._tracked.pop(owner_id, None)
                if previous is not None:
                    previous.release()
                self._tracked[owner_id] = lease
        return lease

    def release(self, owner_id: str) -> None:
        with self._lock:
            lease = self._tracked.pop(owner_id, None)
        if lease is not None:
            lease.release()
        else:
            # Fallback for leases not tracked through this service
            try:
                self._manager.release(owner_id)
            except TunnelManagerError:
                pass

    def heartbeat(self, owner_id: str, ttl: Optional[float] = None) -> None:
        self._manager.heartbeat(owner_id, ttl=ttl)

    # Diagnostics ------------------------------------------------------
    def tunnel_alive(self) -> bool:
        return self._manager.tunnel_alive()

    def describe(self) -> List[Dict[str, object]]:
        return self._manager.active_leases()

    # Accessors --------------------------------------------------------
    @property
    def manager(self) -> TunnelManager:
        return self._manager


@lru_cache()
def get_tunnel_service() -> TunnelService:
    """Dependency provider returning a shared tunnel service instance."""

    return TunnelService()


__all__ = [
    "TunnelService",
    "get_tunnel_service",
    "TunnelManagerError",
    "TunnelPortsBusyError",
    "TunnelConfigurationError",
    "TunnelLease",
]
