"""Service layer for long-running utility jobs."""
from __future__ import annotations

import time
import uuid
from functools import lru_cache
from typing import Any, Dict

from fastapi import HTTPException

from checkFunctions.check_KSequal import fpga_reload
from checkFunctions.check_conf import check_conf
from checkFunctions.check_hash import compare_directories_by_hash

from ..result_repository import ResultRepository
from .tunnels import (
    TunnelConfigurationError,
    TunnelManagerError,
    TunnelPortsBusyError,
    TunnelService,
    get_tunnel_service,
)


class UtilityService:
    """Executes diagnostic utilities and tracks their progress."""

    def __init__(self, tunnel_service: TunnelService) -> None:
        self._tunnel_service = tunnel_service
        self._results = ResultRepository(limit=50)

    # Basic CRUD -------------------------------------------------------
    def list_jobs(self) -> list[Dict[str, Any]]:
        return [record.to_dict() for record in self._results.list()]

    def get_job(self, job_id: str) -> Dict[str, Any]:
        record = self._results.get(job_id)
        if not record:
            raise HTTPException(status_code=404, detail="util job not found")
        return record.to_dict()

    # Job execution helpers -------------------------------------------
    def _create_record(self, util_type: str, params: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        job_id = uuid.uuid4().hex[:12]
        started = time.time()
        payload: Dict[str, Any] = {
            "id": job_id,
            "type": util_type,
            "params": params,
            "result": None,
            "error": None,
            "started": started,
            "finished": None,
        }
        self._results.create(
            record_id=job_id,
            type=util_type,
            status="running",
            payload=payload,
            started_at=started,
        )
        return job_id, payload

    def _finalize(self, job_id: str, payload: Dict[str, Any], status: str) -> Dict[str, Any]:
        finished = time.time()
        payload["finished"] = finished
        started = payload.get("started") or finished
        payload["duration"] = max(finished - started, 0.0)
        record = self._results.update(
            job_id,
            status=status,
            payload=payload,
            finished_at=finished,
        )
        return record.to_dict()

    # Public utility operations ---------------------------------------
    def check_conf(self, req: Dict[str, Any]) -> Dict[str, Any]:
        ip = (req or {}).get("ip") or ""
        password = (req or {}).get("password") or ""
        iterations = int((req or {}).get("iterations", 3))
        delay = int((req or {}).get("delay", 30))
        if not ip:
            raise HTTPException(status_code=400, detail="ip is required")

        job_id, payload = self._create_record(
            "check_conf",
            {"ip": ip, "iterations": iterations, "delay": delay, "password_provided": bool(password)},
        )
        lease_key = f"utils:{job_id}"
        try:
            with self._tunnel_service.reserve(
                lease_key,
                "utils",
                ip=ip,
                username="admin",
                password=password,
                ttl=1800.0,
            ):
                result = check_conf(ip=ip, password=password, iterations=iterations, delay_between=delay)
            payload["result"] = result
            record = self._finalize(job_id, payload, "success")
            return {"success": True, "record": record}
        except (TunnelPortsBusyError, TunnelConfigurationError, TunnelManagerError) as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "error")
            return {"success": False, "record": record, "error": str(exc)}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "error")
            return {"success": False, "record": record, "error": str(exc)}

    def check_hash(self, req: Dict[str, Any]) -> Dict[str, Any]:
        dir1 = (req or {}).get("dir1")
        dir2 = (req or {}).get("dir2")
        if not dir1 or not dir2:
            raise HTTPException(status_code=400, detail="dir1 and dir2 are required")

        job_id, payload = self._create_record("check_hash", {"dir1": dir1, "dir2": dir2})
        try:
            result = compare_directories_by_hash(dir1, dir2)
            payload["result"] = result
            record = self._finalize(job_id, payload, "success")
            return {"success": True, "record": record}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "error")
            return {"success": False, "record": record, "error": str(exc)}

    def fpga_reload(self, req: Dict[str, Any]) -> Dict[str, Any]:
        ip = (req or {}).get("ip") or ""
        password = (req or {}).get("password") or ""
        slot = int((req or {}).get("slot", 9))
        max_attempts = int((req or {}).get("max_attempts", 1000))
        if not ip:
            raise HTTPException(status_code=400, detail="ip is required")

        job_id, payload = self._create_record(
            "fpga_reload",
            {"ip": ip, "slot": slot, "max_attempts": max_attempts, "password_provided": bool(password)},
        )
        lease_key = f"utils:{job_id}"
        try:
            with self._tunnel_service.reserve(
                lease_key,
                "utils",
                ip=ip,
                username="admin",
                password=password,
                ttl=1800.0,
            ):
                result = fpga_reload(ip=ip, password=password, slot=slot, max_attempts=max_attempts)
            payload["result"] = result
            record = self._finalize(job_id, payload, "success")
            return {"success": True, "record": record}
        except (TunnelPortsBusyError, TunnelConfigurationError, TunnelManagerError) as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "error")
            return {"success": False, "record": record, "error": str(exc)}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "error")
            return {"success": False, "record": record, "error": str(exc)}

    @property
    def results(self) -> ResultRepository:
        return self._results


@lru_cache()
def get_utility_service() -> UtilityService:
    return UtilityService(get_tunnel_service())


__all__ = ["UtilityService", "get_utility_service"]
