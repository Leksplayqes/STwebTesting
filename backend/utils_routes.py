"""Utility endpoints that wrap helper scripts from checkFunctions."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from checkFunctions.check_KSequal import fpga_reload
from checkFunctions.check_conf import check_conf
from checkFunctions.check_hash import compare_directories_by_hash

from .result_repository import UTIL_RESULTS

router = APIRouter(prefix="/utils")


def _create_util_record(util_type: str, params: Dict[str, Any]):
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
    UTIL_RESULTS.create(
        record_id=job_id,
        type=util_type,
        status="running",
        payload=payload,
        started_at=started,
    )
    return job_id, payload


def _finalize_util(job_id: str, payload: Dict[str, Any], status: str):
    finished = time.time()
    payload["finished"] = finished
    started = payload.get("started") or finished
    payload["duration"] = max(finished - started, 0.0)
    record = UTIL_RESULTS.update(
        job_id,
        status=status,
        payload=payload,
        finished_at=finished,
    )
    return record.to_dict()


@router.get("/jobs")
def util_jobs():
    return [record.to_dict() for record in UTIL_RESULTS.list()]


@router.get("/status")
def util_status(job_id: str):
    record = UTIL_RESULTS.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="util job not found")
    return record.to_dict()


@router.post("/check_conf")
def util_check_conf(req: Dict[str, Any]):
    ip = (req or {}).get("ip") or ""
    password = (req or {}).get("password") or ""
    iterations = int((req or {}).get("iterations", 3))
    delay = int((req or {}).get("delay", 30))
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    job_id, payload = _create_util_record(
        "check_conf",
        {"ip": ip, "iterations": iterations, "delay": delay, "password_provided": bool(password)},
    )
    try:
        result = check_conf(ip=ip, password=password, iterations=iterations, delay_between=delay)
        payload["result"] = result
        record = _finalize_util(job_id, payload, "success")
        return {"success": True, "record": record}
    except Exception as exc:
        payload["error"] = str(exc)
        record = _finalize_util(job_id, payload, "error")
        return {"success": False, "record": record, "error": str(exc)}


@router.post("/check_hash")
def util_check_hash(req: Dict[str, Any]):
    dir1 = (req or {}).get("dir1")
    dir2 = (req or {}).get("dir2")
    if not dir1 or not dir2:
        raise HTTPException(status_code=400, detail="dir1 and dir2 are required")
    job_id, payload = _create_util_record("check_hash", {"dir1": dir1, "dir2": dir2})
    try:
        result = compare_directories_by_hash(dir1, dir2)
        payload["result"] = result
        record = _finalize_util(job_id, payload, "success")
        return {"success": True, "record": record}
    except Exception as exc:
        payload["error"] = str(exc)
        record = _finalize_util(job_id, payload, "error")
        return {"success": False, "record": record, "error": str(exc)}


@router.post("/fpga_reload")
def util_fpga_reload(req: Dict[str, Any]):
    ip = (req or {}).get("ip") or ""
    password = (req or {}).get("password") or ""
    slot = int((req or {}).get("slot", 9))
    max_attempts = int((req or {}).get("max_attempts", 1000))
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    job_id, payload = _create_util_record(
        "fpga_reload",
        {"ip": ip, "slot": slot, "max_attempts": max_attempts, "password_provided": bool(password)},
    )
    try:
        result = fpga_reload(ip=ip, password=password, slot=slot, max_attempts=max_attempts)
        payload["result"] = result
        record = _finalize_util(job_id, payload, "success")
        return {"success": True, "record": record}
    except Exception as exc:
        payload["error"] = str(exc)
        record = _finalize_util(job_id, payload, "error")
        return {"success": False, "record": record, "error": str(exc)}


__all__ = ["router"]
