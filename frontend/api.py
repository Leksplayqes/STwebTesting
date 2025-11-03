"""HTTP API client used by the Streamlit frontend."""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

import requests

from shared.catalogs import ALARM_TESTS_CATALOG, SYNC_TESTS_CATALOG

from .models import (
    DeviceInfo,
    HistoryLimit,
    StopTestResponse,
    TestCatalogs,
    TestRunRecord,
    TestRunResponse,
    UtilityJobRecord,
    UtilityJobResponse,
)


class BackendApiError(RuntimeError):
    """Raised when the backend API request fails."""


class BackendApiClient:
    """Typed client wrapper around backend REST endpoints."""

    def __init__(self, base_url: str, *, default_timeout: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._default_timeout = default_timeout
        self._catalog_cache: Optional[tuple[float, TestCatalogs]] = None
        self._catalog_ttl = 30

    # Low level helpers ------------------------------------------------
    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self._build_url(path)
        try:
            response = self._session.request(
                method,
                url,
                timeout=timeout or self._default_timeout,
                params=params,
                json=json,
            )
        except requests.RequestException as exc:  # pragma: no cover - thin wrapper
            raise BackendApiError(f"{method} {path}: {exc}") from exc
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - thin wrapper
            body = (response.text or "")[:400]
            raise BackendApiError(f"{method} {path}: {exc} | body: {body}") from exc
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise BackendApiError(f"{method} {path}: invalid JSON response") from exc

    def _ensure_envelope(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise BackendApiError("unexpected response type")
        status = payload.get("status")
        if status != "success":
            error = payload.get("error") or {}
            message = error.get("message") or "Backend error"
            raise BackendApiError(message)
        return payload

    def _unwrap(self, payload: Dict[str, Any]) -> tuple[Any, Dict[str, Any]]:
        envelope = self._ensure_envelope(payload)
        data = envelope.get("data")
        meta = envelope.get("meta") or {}
        return data, meta

    def _get(self, path: str, *, timeout: Optional[int] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", path, timeout=timeout, params=params)

    def _post(
        self,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._request("POST", path, timeout=timeout, params=params, json=payload or {})

    # Tests ------------------------------------------------------------
    def get_test_catalogs(self) -> TestCatalogs:
        now = time.time()
        if self._catalog_cache and now - self._catalog_cache[0] < self._catalog_ttl:
            return self._catalog_cache[1]
        try:
            data, _ = self._unwrap(self._get("/tests/types"))
        except BackendApiError:
            data = {
                "alarm_tests": ALARM_TESTS_CATALOG,
                "sync_tests": SYNC_TESTS_CATALOG,
            }
        catalogs = TestCatalogs.model_validate(data or {})
        self._catalog_cache = (now, catalogs)
        return catalogs

    def list_test_jobs(self) -> tuple[List[TestRunRecord], List[HistoryLimit]]:
        data, _ = self._unwrap(self._get("/tests/jobs"))
        items = [TestRunRecord.model_validate(item) for item in (data or {}).get("items", [])]
        history = [HistoryLimit.model_validate(item) for item in (data or {}).get("history", [])]
        return items, history

    def get_test_status(self, job_id: str) -> TestRunRecord:
        data, _ = self._unwrap(self._get("/tests/status", params={"job_id": job_id}))
        return TestRunRecord.model_validate(data)

    def run_tests(self, payload: Dict[str, Any]) -> TestRunResponse:
        data = self._ensure_envelope(self._post("/tests/run", payload, timeout=120))
        return TestRunResponse.model_validate(data)

    def stop_test(self, job_id: str) -> StopTestResponse:
        data = self._ensure_envelope(self._post("/tests/stop", params={"job_id": job_id}))
        return StopTestResponse.model_validate(data)

    def download_jobfile(self, job_id: str) -> bytes:
        response = self._session.get(self._build_url("/tests/jobfile"), params={"job_id": job_id})
        response.raise_for_status()
        return response.content

    # Utilities --------------------------------------------------------
    def list_util_jobs(self) -> tuple[List[UtilityJobRecord], List[HistoryLimit]]:
        data, _ = self._unwrap(self._get("/utilities/jobs"))
        items = [UtilityJobRecord.model_validate(item) for item in (data or {}).get("items", [])]
        history = [HistoryLimit.model_validate(item) for item in (data or {}).get("history", [])]
        return items, history

    def get_util_status(self, job_id: str) -> UtilityJobRecord:
        data, _ = self._unwrap(self._get(f"/utilities/{job_id}"))
        return UtilityJobRecord.model_validate(data)

    def run_check_conf(
        self,
        *,
        ip: str,
        password: str,
        iterations: int = 3,
        delay: int = 30,
    ) -> UtilityJobResponse:
        payload = {
            "utility": "check_conf",
            "parameters": {
                "ip": ip,
                "password": password,
                "iterations": iterations,
                "delay": delay,
            },
        }
        data = self._ensure_envelope(self._post("/utilities/run", payload))
        return UtilityJobResponse.model_validate(data)

    def run_check_hash(self, *, dir1: str, dir2: str) -> UtilityJobResponse:
        payload = {
            "utility": "check_hash",
            "parameters": {"dir1": dir1, "dir2": dir2},
        }
        data = self._ensure_envelope(self._post("/utilities/run", payload))
        return UtilityJobResponse.model_validate(data)

    def run_fpga_reload(
        self,
        *,
        ip: str,
        password: str,
        slot: int = 9,
        max_attempts: int = 1000,
    ) -> UtilityJobResponse:
        payload = {
            "utility": "fpga_reload",
            "parameters": {
                "ip": ip,
                "password": password,
                "slot": slot,
                "max_attempts": max_attempts,
            },
        }
        data = self._ensure_envelope(self._post("/utilities/run", payload))
        return UtilityJobResponse.model_validate(data)

    # Device -----------------------------------------------------------
    def ping_device(self, ip: str) -> bool:
        try:
            data = self._post("/ping", {"ip_address": ip})
        except BackendApiError:
            return False
        return bool(data.get("success")) if data else False

    def fetch_device_info(
        self,
        *,
        ip: str,
        password: str,
        snmp_type: str,
        viavi: Optional[Dict[str, Any]] = None,
        loopback: Optional[Dict[str, Any]] = None,
    ) -> DeviceInfo:
        payload = {
            "ip_address": ip,
            "password": password,
            "snmp_type": snmp_type,
            "viavi": viavi or {},
            "loopback": loopback or {},
        }
        data = self._post("/device/info", payload, timeout=500)
        return DeviceInfo.model_validate(data or {})


def normalise_nodeids(nodeids: Iterable[str]) -> List[str]:
    return [node.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/").strip() for node in nodeids]


__all__ = [
    "BackendApiClient",
    "BackendApiError",
    "normalise_nodeids",
]
