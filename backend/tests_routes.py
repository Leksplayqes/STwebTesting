"""FastAPI routes for managing pytest executions."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from .models import TestsRunRequest
from .services import TestExecutionService, get_test_service

router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("/types")
def get_types(service: TestExecutionService = Depends(get_test_service)):
    return service.list_catalogs()


@router.get("/jobs")
def list_jobs(service: TestExecutionService = Depends(get_test_service)):
    return service.list_jobs()


@router.get("/status")
def tests_status(job_id: str, service: TestExecutionService = Depends(get_test_service)):
    record = service.get_job(job_id)
    return record.to_dict()


@router.post("/run")
def tests_run(
    req: TestsRunRequest,
    background_tasks: BackgroundTasks,
    service: TestExecutionService = Depends(get_test_service),
):
    return service.run(req, background_tasks)


@router.post("/stop")
def tests_stop(job_id: str, service: TestExecutionService = Depends(get_test_service)):
    return service.stop(job_id)


@router.get("/jobfile")
def download_jobfile(job_id: str, service: TestExecutionService = Depends(get_test_service)):
    path = service.job_file(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="job file not found")
    return FileResponse(str(path), media_type="application/json", filename=f"{job_id}.json")


__all__ = ["router"]
