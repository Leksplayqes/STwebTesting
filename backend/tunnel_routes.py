"""Endpoints exposing tunnel manager diagnostics."""
from __future__ import annotations

from fastapi import APIRouter

from .config import get_tunnel_ports
from .models import TunnelStatusResponse
from .snmp_proxy import describe_tunnels, tunnel_alive

router = APIRouter(prefix="/tunnels", tags=["tunnels"])


@router.get("", summary="List active SNMP tunnels", response_model=TunnelStatusResponse)
def list_tunnels() -> TunnelStatusResponse:
    return TunnelStatusResponse(
        alive=tunnel_alive(),
        configured_ports=get_tunnel_ports(),
        leases=describe_tunnels(),
    )


__all__ = ["router"]

