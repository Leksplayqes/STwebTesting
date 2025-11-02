"""Typed representations of backend API responses."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TestCatalogs(BaseModel):
    alarm_tests: Dict[str, str] = Field(default_factory=dict)
    sync_tests: Dict[str, str] = Field(default_factory=dict)


class TestCase(BaseModel):
    name: Optional[str] = None
    nodeid: Optional[str] = None
    status: Optional[str] = None
    duration: Optional[float] = None
    message: Optional[str] = None


class TestRunSummary(BaseModel):
    status: str = "running"
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    message: Optional[str] = None


class TestRunPayload(BaseModel):
    id: str
    summary: TestRunSummary = Field(default_factory=TestRunSummary)
    cases: List[TestCase] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    expected_total: Optional[int] = None
    returncode: Optional[int] = None
    finished: Optional[float] = None
    started: Optional[float] = None


class TestRunRecord(BaseModel):
    id: str
    type: str
    status: str
    payload: TestRunPayload = Field(default_factory=TestRunPayload)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class DeviceInfo(BaseModel):
    name: str = ""
    ipaddr: str = ""
    slots_dict: Dict[str, Any] = Field(default_factory=dict)
    viavi: Dict[str, Any] = Field(default_factory=dict)
    loopback: Dict[str, Any] = Field(default_factory=dict)


class UtilityJobPayload(BaseModel):
    id: str
    type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    started: Optional[float] = None
    finished: Optional[float] = None
    duration: Optional[float] = None


class UtilityJobRecord(BaseModel):
    id: str
    type: str
    status: str
    payload: UtilityJobPayload = Field(default_factory=UtilityJobPayload)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class TestRunResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    record: Optional[TestRunRecord] = None
    error: Optional[str] = None


class UtilityJobResponse(BaseModel):
    success: bool
    record: Optional[UtilityJobRecord] = None
    error: Optional[str] = None


class StopTestResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


__all__ = [
    "DeviceInfo",
    "TestCatalogs",
    "TestCase",
    "TestRunPayload",
    "TestRunRecord",
    "TestRunResponse",
    "TestRunSummary",
    "UtilityJobPayload",
    "UtilityJobRecord",
    "UtilityJobResponse",
    "StopTestResponse",
]
