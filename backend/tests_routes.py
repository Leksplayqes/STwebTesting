"""Endpoints for orchestrating pytest runs and managing their artefacts."""
from __future__ import annotations

import os
import re
import sys
import time
import threading
import uuid
from subprocess import PIPE, STDOUT, Popen
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from .config import PROJECT_ROOT, REPORT_DIR, ensure_config
from .jobs import job_path, load_jobs_on_startup, save_job
from .logs import add_log
from .models import TestsRunRequest
from .result_repository import TEST_RESULTS
from .snmp_proxy import ensure_tunnel, register_tunnel_user, release_tunnel_user, tunnel_alive
from .state import RUNNING_PROCS
from .test_catalogs import ALARM_TESTS_CATALOG, SYNC_TESTS_CATALOG

router = APIRouter(prefix="/tests")


@router.get("/types")
async def get_types() -> Dict[str, Dict[str, str]]:
    return {"alarm_tests": ALARM_TESTS_CATALOG, "sync_tests": SYNC_TESTS_CATALOG}


@router.get("/jobs")
def list_jobs() -> List[Dict[str, object]]:
    return [record.to_dict() for record in TEST_RESULTS.list()]


@router.get("/status")
def tests_status(job_id: str):
    record = TEST_RESULTS.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job not found")
    return record.to_dict()


@router.post("/run")
def tests_run(req: TestsRunRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    nodeids = [_norm_nodeid(x) for x in (req.selected_tests or []) if x.strip()]
    if not nodeids:
        raise HTTPException(status_code=400, detail="Не выбраны тесты для запуска")

    register_tunnel_user(job_id)

    try:
        cfg = ensure_config()
        ip = (cfg.get("CurrentEQ") or {}).get("ipaddr") or ""
        password = (cfg.get("CurrentEQ") or {}).get("pass") or ""
        if ip and not tunnel_alive():
            threading.Thread(target=ensure_tunnel, args=(ip, "admin", password), daemon=True).start()
    except Exception as exc:
        add_log(f"ensure_tunnel pre-start failed: {exc}", "ERROR")

    started = time.time()
    job_payload: Dict[str, object] = {
        "id": job_id,
        "config": req.model_dump(),
        "started": started,
        "finished": None,
        "summary": {
            "status": "running",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0.0,
        },
        "cases": [],
        "stdout": "",
        "stderr": "",
        "returncode": None,
        "report": str((REPORT_DIR / f"{job_id}.xml").resolve()),
        "expected_total": None,
    }
    record = TEST_RESULTS.create(
        record_id=job_id,
        type="tests",
        status="running",
        payload=job_payload,
        started_at=started,
    )
    save_job(job_id)

    background_tasks.add_task(_execute_tests, job_id, nodeids)
    return {"success": True, "job_id": job_id, "record": record.to_dict()}


@router.post("/stop")
def tests_stop(job_id: str = Query(...)):
    record = TEST_RESULTS.get(job_id)
    proc = RUNNING_PROCS.get(job_id)
    if not record:
        return {"success": False, "error": "job not found"}
    job = record.payload
    if not proc:
        if (job.get("summary") or {}).get("status") == "running":
            job["summary"]["status"] = "stopped"
            job["finished"] = time.time()
            TEST_RESULTS.update(
                job_id,
                status="stopped",
                payload=job,
                finished_at=job["finished"],
            )
            save_job(job_id)
        return {"success": True, "message": "job is not running"}

    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        code = proc.returncode
    except Exception as exc:
        return {"success": False, "error": f"terminate failed: {exc}"}
    finally:
        RUNNING_PROCS.pop(job_id, None)

    cases = job.get("cases") or []
    job["returncode"] = code
    job["finished"] = time.time()
    job["summary"] = {
        "status": "stopped",
        "total": len(cases),
        "passed": sum(1 for c in cases if c.get("status") == "PASSED"),
        "failed": sum(1 for c in cases if c.get("status") in ("FAILED", "ERROR")),
        "skipped": sum(1 for c in cases if c.get("status") == "SKIPPED"),
        "duration": sum(float(c.get("duration") or 0.0) for c in cases),
    }
    TEST_RESULTS.update(
        job_id,
        status="stopped",
        payload=job,
        finished_at=job["finished"],
    )
    save_job(job_id)
    try:
        release_tunnel_user(job_id)
    except Exception:
        pass
    return {"success": True, "message": "job stopped"}


@router.get("/jobfile")
def download_jobfile(job_id: str):
    path = job_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="job file not found")
    return FileResponse(str(path), media_type="application/json", filename=f"{job_id}.json")


@router.get("/report")
def download_junit_xml(job_id: str):
    record = TEST_RESULTS.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job not found")
    payload = record.payload
    report_path = payload.get("report") if isinstance(payload, dict) else None
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(report_path, media_type="application/xml", filename=f"{job_id}.xml")


def _norm_nodeid(node_id: str) -> str:
    return node_id.replace(" ::", "::").replace(":: ", "::").replace(" / ", "/").strip()


def _recalc_summary(cases: List[Dict[str, object]], finished: bool) -> Dict[str, object]:
    total = len(cases)
    passed = sum(1 for case in cases if case["status"] == "PASSED")
    failed = sum(1 for case in cases if case["status"] in ("FAILED", "ERROR"))
    skipped = sum(1 for case in cases if case["status"] == "SKIPPED")
    duration = sum(float(case.get("duration") or 0.0) for case in cases)
    status = "running" if not finished else ("passed" if failed == 0 else "failed")
    return {
        "status": status,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration": duration,
    }


def _parse_junit_report(xml_path: str):
    import xml.etree.ElementTree as ET

    cases: List[Dict[str, object]] = []
    passed = failed = skipped = errors = 0
    total_time = 0.0

    root = ET.parse(xml_path).getroot()
    for testsuite in root.findall(".//testsuite"):
        for testcase in testsuite.findall("testcase"):
            name = testcase.get("name") or ""
            classname = testcase.get("classname") or ""
            duration = float(testcase.get("time") or 0.0)
            nodeid = f"{classname}::{name}" if classname else name

            status = "PASSED"
            message = None
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped_el = testcase.find("skipped")
            if failure is not None:
                status, message, failed = "FAILED", (failure.get("message") or "").strip(), failed + 1
            elif error is not None:
                status, message, errors = "ERROR", (error.get("message") or "").strip(), errors + 1
            elif skipped_el is not None:
                status, message, skipped = "SKIPPED", (skipped_el.get("message") or "").strip(), skipped + 1
            else:
                passed += 1

            total_time += duration
            cases.append({
                "name": name,
                "nodeid": nodeid,
                "status": status,
                "duration": duration,
                "message": message,
            })

    summary = {
        "status": ("failed" if (failed or errors) else "passed"),
        "total": len(cases),
        "passed": passed,
        "failed": failed + errors,
        "skipped": skipped,
        "duration": total_time,
    }
    return cases, summary


def _execute_tests(job_id: str, nodeids: List[str]) -> None:
    record = TEST_RESULTS.get(job_id)
    if not record:
        return

    collect_re = re.compile(r"collected\s+(\d+)\s+items?")
    payload = record.payload
    payload["expected_total"] = None
    report_path = str(REPORT_DIR / f"{job_id}.xml")
    payload["report"] = report_path
    TEST_RESULTS.update(job_id, payload=payload)
    save_job(job_id)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-vv",
        "-rA",
        "--tb=short",
        "--color=no",
        f"--junitxml={report_path}",
        *nodeids,
    ]
    proc = Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=PIPE,
        stderr=STDOUT,
        bufsize=1,
        universal_newlines=True,
    )
    RUNNING_PROCS[job_id] = proc

    try:
        cases_map: Dict[str, Dict[str, object]] = {}
        payload.update(
            {
                "stdout": "",
                "stderr": "",
                "cases": [],
                "summary": {
                    "status": "running",
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "duration": 0.0,
                },
            }
        )
        TEST_RESULTS.update(job_id, status="running", payload=payload)
        save_job(job_id)
        if proc.stdout is not None:
            for line in proc.stdout:
                mcol = collect_re.search(line)
                if mcol:
                    try:
                        payload["expected_total"] = int(mcol.group(1))
                    except Exception:
                        payload["expected_total"] = None
                payload["stdout"] += line
                match = _VERBOSE_LINE.match(line.strip())
                if match:
                    nodeid = _norm_nodeid(match.group("nodeid").strip())
                    status = match.group("status")
                    case = cases_map.get(nodeid) or {
                        "name": nodeid.split("::")[-1],
                        "nodeid": nodeid,
                        "status": status,
                        "duration": None,
                        "message": None,
                    }
                    case["status"] = status
                    cases_map[nodeid] = case
                    payload["cases"] = list(cases_map.values())
                    payload["summary"] = _recalc_summary(payload["cases"], finished=False)
                    TEST_RESULTS.update(
                        job_id,
                        status=payload["summary"].get("status", "running"),
                        payload=payload,
                    )
                    save_job(job_id)
        proc.wait()
        payload["returncode"] = proc.returncode
        payload["finished"] = time.time()
        TEST_RESULTS.update(job_id, payload=payload)
        save_job(job_id)

        try:
            if os.path.exists(report_path):
                final_cases, _ = _parse_junit_report(report_path)
                final_map = {case["nodeid"]: case for case in final_cases}
                for nodeid, live in list(cases_map.items()):
                    if nodeid in final_map:
                        merged = final_map[nodeid]
                        merged["status"] = live.get("status", merged["status"])
                        merged["duration"] = merged.get("duration") or live.get("duration")
                        merged["message"] = merged.get("message") or live.get("message")
                        final_map[nodeid] = merged
                payload["cases"] = list(final_map.values())
                payload["summary"] = _recalc_summary(payload["cases"], finished=True)
                TEST_RESULTS.update(
                    job_id,
                    status=payload["summary"].get("status", "finished"),
                    payload=payload,
                    finished_at=payload.get("finished"),
                )
                save_job(job_id)
            elif not payload.get("cases"):
                payload["summary"] = {
                    "status": "error",
                    "total": 0,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "duration": 0.0,
                    "message": "pytest did not produce junit xml; check stdout/stderr",
                }
                TEST_RESULTS.update(
                    job_id,
                    status="error",
                    payload=payload,
                    finished_at=payload.get("finished"),
                )
                save_job(job_id)
        except Exception as exc:
            payload["summary"] = {
                "status": "error",
                "total": len(payload.get("cases") or []),
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration": 0.0,
                "message": f"junit merge failed: {exc}",
            }
            TEST_RESULTS.update(
                job_id,
                status="error",
                payload=payload,
                finished_at=payload.get("finished"),
            )
            save_job(job_id)
    finally:
        RUNNING_PROCS.pop(job_id, None)
        try:
            release_tunnel_user(job_id)
        except Exception:
            pass
        if payload.get("finished") is None:
            payload["finished"] = time.time()
            TEST_RESULTS.update(
                job_id,
                payload=payload,
                finished_at=payload["finished"],
            )
        save_job(job_id)


_VERBOSE_LINE = re.compile(r"^(?P<nodeid>[^ ]+::[^\s]+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)")

__all__ = ["router", "load_jobs_on_startup"]
