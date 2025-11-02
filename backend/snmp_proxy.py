"""Helpers to manage the SNMP-over-SSH proxy process."""
from __future__ import annotations

from typing import Dict, List, Optional

from snmpsubsystem import ProxyController

from .config import DEFAULT_TUNNEL_PORTS, get_tunnel_ports
from .tunnel_manager import (
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


SNMP_PROXY = ProxyController()
TUNNEL_MANAGER = TunnelManager(SNMP_PROXY, ports=_configured_ports())


def reserve_tunnel(
    owner_id: str,
    owner_kind: str,
    *,
    ip: str,
    username: str,
    password: str,
    ttl: Optional[float] = None,
) -> TunnelLease:
    return TUNNEL_MANAGER.lease(
        owner_id,
        owner_kind,
        ip=ip,
        username=username,
        password=password,
        ttl=ttl,
    )


def release_tunnel(owner_id: str) -> None:
    TUNNEL_MANAGER.release(owner_id)


def heartbeat_tunnel(owner_id: str, ttl: Optional[float] = None) -> None:
    TUNNEL_MANAGER.heartbeat(owner_id, ttl=ttl)


def tunnel_alive() -> bool:
    return TUNNEL_MANAGER.tunnel_alive()


def describe_tunnels() -> List[Dict[str, object]]:
    return TUNNEL_MANAGER.active_leases()


__all__ = [
    "SNMP_PROXY",
    "TUNNEL_MANAGER",
    "TunnelManagerError",
    "TunnelPortsBusyError",
    "TunnelConfigurationError",
    "TunnelLease",
    "reserve_tunnel",
    "release_tunnel",
    "heartbeat_tunnel",
    "tunnel_alive",
    "describe_tunnels",
]
