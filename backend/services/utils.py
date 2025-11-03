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

from ..models import (
    CheckConfParameters,
    CheckHashParameters,
    FpgaReloadParameters,
    UtilityRunRequest,
)
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
            "summary": {"status": "queued"},
        }
        self._results.create(
            record_id=job_id,
            type=util_type,
            status="queued",
            payload=payload,
            started_at=started,
        )
        return job_id, payload

    def _mark_running(self, job_id: str, payload: Dict[str, Any]) -> None:
        payload.setdefault("summary", {})["status"] = "running"
        self._results.update(job_id, status="running", payload=payload)

    def _finalize(self, job_id: str, payload: Dict[str, Any], status: str) -> Dict[str, Any]:
        finished = time.time()
        payload["finished"] = finished
        started = payload.get("started") or finished
        payload["duration"] = max(finished - started, 0.0)
        payload.setdefault("summary", {})
        payload["summary"]["status"] = status
        payload["summary"]["duration"] = payload.get("duration")
        record = self._results.update(
            job_id,
            status=status,
            payload=payload,
            finished_at=finished,
        )
        return record.to_dict()

    # Public utility operations ---------------------------------------
    def check_conf(self, params: CheckConfParameters) -> Dict[str, Any]:
        if not params.ip:
            raise HTTPException(status_code=400, detail="ip is required")

        job_id, payload = self._create_record(
            "check_conf",
            {
                "ip": params.ip,
                "iterations": params.iterations,
                "delay": params.delay,
                "password_provided": bool(params.password),
            },
        )
        lease_key = f"utils:{job_id}"
        try:
            with self._tunnel_service.reserve(
                lease_key,
                "utils",
                ip=params.ip,
                username="admin",
                password=params.password or "",
                ttl=1800.0,
            ):
                self._mark_running(job_id, payload)
                result = check_conf(
                    ip=params.ip,
                    password=params.password or "",
                    iterations=params.iterations,
                    delay_between=params.delay,
                )
            payload["result"] = result
            record = self._finalize(job_id, payload, "completed")
            return {"success": True, "record": record}
        except (TunnelPortsBusyError, TunnelConfigurationError, TunnelManagerError) as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "failed")
            return {"success": False, "record": record, "error": str(exc)}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "failed")
            return {"success": False, "record": record, "error": str(exc)}

    def check_hash(self, params: CheckHashParameters) -> Dict[str, Any]:
        if not params.dir1 or not params.dir2:
            raise HTTPException(status_code=400, detail="dir1 and dir2 are required")

        job_id, payload = self._create_record(
            "check_hash", {"dir1": params.dir1, "dir2": params.dir2}
        )
        try:
            self._mark_running(job_id, payload)
            result = compare_directories_by_hash(params.dir1, params.dir2)
            payload["result"] = result
            record = self._finalize(job_id, payload, "completed")
            return {"success": True, "record": record}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "failed")
            return {"success": False, "record": record, "error": str(exc)}

    def fpga_reload(self, params: FpgaReloadParameters) -> Dict[str, Any]:
        if not params.ip:
            raise HTTPException(status_code=400, detail="ip is required")

        job_id, payload = self._create_record(
            "fpga_reload",
            {
                "ip": params.ip,
                "slot": params.slot,
                "max_attempts": params.max_attempts,
                "password_provided": bool(params.password),
            },
        )
        lease_key = f"utils:{job_id}"
        try:
            with self._tunnel_service.reserve(
                lease_key,
                "utils",
                ip=params.ip,
                username="admin",
                password=params.password or "",
                ttl=1800.0,
            ):
                self._mark_running(job_id, payload)
                result = fpga_reload(
                    ip=params.ip,
                    password=params.password or "",
                    slot=params.slot,
                    max_attempts=params.max_attempts,
                )
            payload["result"] = result
            record = self._finalize(job_id, payload, "completed")
            return {"success": True, "record": record}
        except (TunnelPortsBusyError, TunnelConfigurationError, TunnelManagerError) as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "failed")
            return {"success": False, "record": record, "error": str(exc)}
        except Exception as exc:
            payload["error"] = str(exc)
            record = self._finalize(job_id, payload, "failed")
            return {"success": False, "record": record, "error": str(exc)}

    def run(self, request: UtilityRunRequest) -> Dict[str, Any]:
        if request.utility == "check_conf":
            return self.check_conf(CheckConfParameters.model_validate(request.parameters))
        if request.utility == "check_hash":
            return self.check_hash(CheckHashParameters.model_validate(request.parameters))
        if request.utility == "fpga_reload":
            return self.fpga_reload(FpgaReloadParameters.model_validate(request.parameters))
        raise HTTPException(status_code=400, detail=f"Unsupported utility {request.utility}")

    @property
    def results(self) -> ResultRepository:
        return self._results


@lru_cache()
def get_utility_service() -> UtilityService:
    return UtilityService(get_tunnel_service())


__all__ = ["UtilityService", "get_utility_service"]
