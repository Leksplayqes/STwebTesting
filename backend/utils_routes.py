"""FastAPI routes for auxiliary utility executions."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from .services import UtilityService, get_utility_service

router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/jobs")
def util_jobs(service: UtilityService = Depends(get_utility_service)):
    return service.list_jobs()


@router.get("/status")
def util_status(job_id: str, service: UtilityService = Depends(get_utility_service)):
    return service.get_job(job_id)


@router.post("/check_conf")
def util_check_conf(req: Dict[str, Any], service: UtilityService = Depends(get_utility_service)):
    return service.check_conf(req)


@router.post("/check_hash")
def util_check_hash(req: Dict[str, Any], service: UtilityService = Depends(get_utility_service)):
    return service.check_hash(req)


@router.post("/fpga_reload")
def util_fpga_reload(req: Dict[str, Any], service: UtilityService = Depends(get_utility_service)):
    return service.fpga_reload(req)


__all__ = ["router"]
