"""Widgets showing test run progress and results."""
from __future__ import annotations

import time
from typing import Any, Dict

import pandas as pd
import streamlit as st

from frontend.api import api_get, stop_test_job
from frontend.ui.components import render_runs_list


def _render_cases_table(cases: Any, container: st.delta_generator.DeltaGenerator) -> None:
    if not cases:
        container.info("Идёт сбор результатов…")
        return
    df = pd.DataFrame(
        [
            {
                "Тест": case.get("nodeid") or case.get("name"),
                "Статус": case.get("status"),
                "Время, c": case.get("duration"),
                "Сообщение": (case.get("message") or "")[:300],
            }
            for case in cases
        ]
    )
    container.dataframe(df, use_container_width=True, hide_index=True)


def render_results(api_base_url: str) -> None:
    st.header("Результаты тестирования")

    list_placeholder = st.container()
    caption_box = st.empty()
    stop_placeholder = st.empty()
    status_box = st.empty()
    table_box = st.empty()
    progress_box = st.empty()

    job_id = None

    for _ in range(900):  # до 30 минут
        records = api_get(api_base_url, "/tests/jobs", timeout=20) or []
        with list_placeholder:
            selected = render_runs_list(
                records,
                key_prefix="tests",
                title="История прогонов",
                empty_message="Пока нет ни одного прогона.",
            )
        if not selected:
            return

        selected_id = selected.get("id")
        if not selected_id:
            status_box.warning("Выберите прогон для отображения.")
            return

        if job_id != selected_id:
            job_id = selected_id
            caption_box.caption(f"Выбран прогон: {job_id}")
            status_box.empty()
            table_box.empty()
            progress_box.empty()

        if stop_placeholder.button(
            "🛑 Остановить тест",
            type="secondary",
            key="stop_test_button",
        ):
            stop_test_job(api_base_url, job_id)

        record = api_get(api_base_url, f"/tests/status?job_id={job_id}", timeout=20) or {}
        if not record:
            status_box.error("Не удалось получить состояние прогона.")
            break
        payload: Dict[str, Any] = record.get("payload") or {}

        summary = payload.get("summary") or {}
        cases = payload.get("cases") or []
        expected_total = payload.get("expected_total")
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        done = int(passed) + int(failed) + int(skipped)

        status_text = (
            f"Статус: {summary.get('status', 'running')} — {passed}✅ / {failed}❌ / {skipped}⏭"
        )
        if expected_total:
            status_text += f" (готово {done} из {expected_total})"
        status_box.write(status_text)

        _render_cases_table(cases, table_box)

        if expected_total:
            progress_box.progress(min(done / max(expected_total, 1), 1.0))
        else:
            progress_box.progress(0.0 if done == 0 else min(done / max(len(cases), 1), 1.0))

        if summary.get("status") in {"passed", "failed", "error", "stopped"}:
            break
        time.sleep(2)
