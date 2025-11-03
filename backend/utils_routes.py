"""FastAPI routes for auxiliary utility executions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .models import (
    HistoryLimit,
    ResultDetailResponse,
    ResultListData,
    ResultListResponse,
    ResultRecordModel,
    UtilityRunRequest,
)
from .services import UtilityService, get_utility_service

router = APIRouter(prefix="/utilities", tags=["utilities"])


def _to_record(data: dict) -> ResultRecordModel:
    return ResultRecordModel.model_validate(data)


@router.get("/jobs", response_model=ResultListResponse, summary="История запусков утилит")
def util_jobs(service: UtilityService = Depends(get_utility_service)) -> ResultListResponse:
    repo = service.results
    items = [_to_record(record.to_dict()) for record in repo.list()]
    data = ResultListData(
        items=items,
        history=[HistoryLimit(type="utilities", limit=repo.limit, total=repo.count())],
    )
    return ResultListResponse(status="success", data=data)


@router.get("/{job_id}", response_model=ResultDetailResponse, summary="Получить запись утилиты")
def util_status(job_id: str, service: UtilityService = Depends(get_utility_service)) -> ResultDetailResponse:
    record = service.results.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="util job not found")
    return ResultDetailResponse(status="success", data=_to_record(record.to_dict()))


@router.post("/run", response_model=ResultDetailResponse, summary="Запустить утилиту")
def util_run(req: UtilityRunRequest, service: UtilityService = Depends(get_utility_service)) -> ResultDetailResponse:
    result = service.run(req)
    record_data = result.get("record") or {}
    record = _to_record(record_data)
    meta = {"success": bool(result.get("success", False))}
    if result.get("error"):
        meta["error"] = result["error"]
    return ResultDetailResponse(status="success", data=record, meta=meta)


__all__ = ["router"]
