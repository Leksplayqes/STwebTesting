"""Thread-safe tunnel manager with port pooling and lease tracking."""
from __future__ import annotations

import contextlib
import socket
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from snmpsubsystem import ProxyController


class TunnelManagerError(RuntimeError):
    """Base error for tunnel manager failures."""


class TunnelPortsBusyError(TunnelManagerError):
    """Raised when all configured ports are already in use."""


class TunnelConfigurationError(TunnelManagerError):
    """Raised when the requested tunnel conflicts with the active configuration."""


@dataclass
class LeaseInfo:
    owner_id: str
    owner_kind: str
    port: int
    created_at: float
    expires_at: float
    ttl: float
    device_ip: str
    username: str
    last_heartbeat: float

    def as_dict(self) -> Dict[str, object]:
        return {
            "owner_id": self.owner_id,
            "owner_kind": self.owner_kind,
            "port": self.port,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "ttl": self.ttl,
            "device_ip": self.device_ip,
            "username": self.username,
            "last_heartbeat": self.last_heartbeat,
        }


class TunnelLease(contextlib.AbstractContextManager[Tuple[str, int]]):
    """Context manager returned for each reservation."""

    def __init__(self, manager: "TunnelManager", owner_id: str):
        self._manager = manager
        self.owner_id = owner_id
        self._released = False

    @property
    def info(self) -> LeaseInfo:
        info = self._manager._leases.get(self.owner_id)
        if not info:
            raise TunnelManagerError(f"lease {self.owner_id} is not active")
        return info

    @property
    def port(self) -> int:
        return self.info.port

    @property
    def host(self) -> str:
        return self._manager.listen_host

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._manager.release(self.owner_id)

    def renew(self, ttl: Optional[float] = None) -> None:
        self._manager.heartbeat(self.owner_id, ttl=ttl)

    def __enter__(self) -> Tuple[str, int]:
        return self.host, self.port

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - thin wrapper
        self.release()


class TunnelManager:
    """Manage lifecycle of ProxyController with port pooling and lease tracking."""

    def __init__(
        self,
        controller: ProxyController,
        *,
        listen_host: str = "127.0.0.1",
        ports: Optional[Iterable[int]] = None,
        default_ttl: float = 600.0,
        cleanup_interval: float = 30.0,
    ) -> None:
        self._controller = controller
        self.listen_host = listen_host
        self._ports = self._normalise_ports(ports)
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._lock = threading.RLock()
        self._leases: Dict[str, LeaseInfo] = {}
        self._active_port: Optional[int] = None
        self._current_target: Optional[Tuple[str, str, str]] = None
        self._stop_event = threading.Event()
        self._janitor = threading.Thread(target=self._janitor_loop, daemon=True)
        self._janitor.start()

    @staticmethod
    def _normalise_ports(ports: Optional[Iterable[int]]) -> List[int]:
        if ports is None:
            return [1161]
        result: List[int] = []
        for port in ports:
            if port not in result:
                result.append(port)
        if not result:
            raise TunnelManagerError("no ports configured for TunnelManager")
        return result

    def _janitor_loop(self) -> None:  # pragma: no cover - background maintenance
        while not self._stop_event.wait(self._cleanup_interval):
            try:
                self._cleanup_expired()
            except Exception:
                # Defensive: avoid killing the janitor thread on unexpected errors
                pass

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._janitor.is_alive():
            self._janitor.join(timeout=1.0)

    # Port helpers -----------------------------------------------------
    def _port_available(self, port: int) -> bool:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.listen_host, port))
            except OSError:
                return False
        return True

    def _select_port(self) -> int:
        for port in self._ports:
            if self._active_port == port:
                return port
            if self._port_available(port):
                return port
        raise TunnelPortsBusyError(
            "все локальные порты для SNMP-туннеля заняты"
        )

    def _ensure_controller(self, ip: str, username: str, password: str) -> int:
        if self._controller.proxy and self._controller.proxy._proc_alive():
            port = self._controller.proxy.listen_addr[1]
            self._active_port = port
            if self._current_target and self._current_target != (ip, username, password):
                raise TunnelConfigurationError(
                    "SNMP-туннель уже активен для другого устройства"
                )
            self._current_target = (ip, username, password)
            return port

        port = self._select_port()
        self._controller.start(
            ip=ip,
            username=username,
            password=password,
            listen_host=self.listen_host,
            listen_port=port,
        )
        self._active_port = port
        self._current_target = (ip, username, password)
        return port

    # Lease helpers ----------------------------------------------------
    def lease(
        self,
        owner_id: str,
        owner_kind: str,
        *,
        ip: str,
        username: str,
        password: str,
        ttl: Optional[float] = None,
    ) -> TunnelLease:
        if not owner_id:
            raise TunnelManagerError("owner_id is required")
        ttl = float(ttl) if ttl else self._default_ttl
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(now)
            info = self._leases.get(owner_id)
            if info:
                info.expires_at = now + ttl
                info.ttl = ttl
                info.last_heartbeat = now
                info.device_ip = ip
                info.username = username
                return TunnelLease(self, owner_id)

            port = self._ensure_controller(ip, username, password)
            info = LeaseInfo(
                owner_id=owner_id,
                owner_kind=owner_kind,
                port=port,
                created_at=now,
                expires_at=now + ttl,
                ttl=ttl,
                device_ip=ip,
                username=username,
                last_heartbeat=now,
            )
            self._leases[owner_id] = info
        return TunnelLease(self, owner_id)

    def heartbeat(self, owner_id: str, ttl: Optional[float] = None) -> None:
        ttl_value = float(ttl) if ttl else None
        now = time.time()
        with self._lock:
            info = self._leases.get(owner_id)
            if not info:
                return
            if ttl_value:
                info.ttl = ttl_value
            info.expires_at = now + (info.ttl if info.ttl else self._default_ttl)
            info.last_heartbeat = now

    def release(self, owner_id: str) -> None:
        with self._lock:
            info = self._leases.pop(owner_id, None)
            if not info:
                return
            if not self._leases:
                self._controller.close()
                self._active_port = None
                self._current_target = None

    def active_leases(self) -> List[Dict[str, object]]:
        with self._lock:
            self._cleanup_expired_locked(time.time())
            return [info.as_dict() for info in self._leases.values()]

    def tunnel_alive(self) -> bool:
        return bool(self._controller.proxy and self._controller.proxy._proc_alive())

    # Internal helpers -------------------------------------------------
    def _cleanup_expired(self) -> None:
        self._cleanup_expired_locked(time.time())

    def _cleanup_expired_locked(self, now: float) -> None:
        expired = [owner_id for owner_id, info in self._leases.items() if info.expires_at <= now]
        for owner_id in expired:
            self._leases.pop(owner_id, None)
        if expired and not self._leases:
            self._controller.close()
            self._active_port = None
            self._current_target = None


__all__ = [
    "TunnelManager",
    "TunnelLease",
    "TunnelManagerError",
    "TunnelPortsBusyError",
    "TunnelConfigurationError",
    "LeaseInfo",
]

