"""Widgets showing test run progress and results."""
from __future__ import annotations

import time
from typing import Any, List

import pandas as pd
import streamlit as st

from frontend.api import BackendApiClient, BackendApiError
from frontend.models import HistoryLimit, JobSummary, TestRunRecord
from frontend.ui.components import render_runs_list


def _extract_job_id(selected: Any) -> str | None:
    """Best-effort extraction of a job identifier from various record types."""

    if selected is None:
        return None
    if isinstance(selected, TestRunRecord):
        return selected.id
    if hasattr(selected, "model_dump"):
        try:
            data = selected.model_dump()  # type: ignore[no-any-unimported]
        except Exception:  # pragma: no cover - defensive
            data = {}
        else:
            return str(data.get("id")) if data.get("id") is not None else None
    if hasattr(selected, "id"):
        job_id = getattr(selected, "id", None)
        return str(job_id) if job_id is not None else None
    if isinstance(selected, dict):
        job_id = selected.get("id")
        return str(job_id) if job_id is not None else None
    try:
        data = dict(selected)
    except Exception:  # pragma: no cover - defensive
        return None
    job_id = data.get("id")
    return str(job_id) if job_id is not None else None


def _render_cases_table(cases: Any, container: st.delta_generator.DeltaGenerator) -> None:
    if not cases:
        container.info("Идёт сбор результатов…")
        return
    rows = []
    for case in cases:
        if hasattr(case, "model_dump"):
            data = case.model_dump()
        else:
            data = dict(case)
        rows.append(
            {
                "Тест": data.get("nodeid") or data.get("name"),
                "Статус": data.get("status"),
                "Время, c": data.get("duration"),
                "Сообщение": (data.get("message") or "")[:300],
            }
        )
    df = pd.DataFrame(rows)
    container.dataframe(df, use_container_width=True, hide_index=True)


STATUS_LABELS = {
    "queued": "в очереди",
    "running": "выполняется",
    "completed": "завершено",
    "failed": "завершено с ошибкой",
    "stopped": "остановлено",
}


def _format_history(history: List[HistoryLimit]) -> str:
    if not history:
        return ""
    limit = history[0]
    return f"История хранит не более {limit.limit} записей (сейчас {limit.total})."


def render_results(client: BackendApiClient) -> None:
    st.header("Результаты тестирования")

    list_placeholder = st.container()
    caption_box = st.empty()
    history_box = st.empty()
    stop_placeholder = st.empty()
    status_box = st.empty()
    table_box = st.empty()
    progress_box = st.empty()

    job_id = None

    for _ in range(900):  # до 30 минут
        try:
            records, history = client.list_test_jobs()
        except BackendApiError as exc:
            st.error(f"Не удалось загрузить историю прогонов: {exc}")
            return
        history_box.info(_format_history(history)) if history else history_box.empty()
        with list_placeholder:
            selected = render_runs_list(
                records,
                key_prefix="tests",
                title="История прогонов",
                empty_message="Пока нет ни одного прогона.",
            )
        if not selected:
            return

        if isinstance(selected, TestRunRecord):
            selected_id = selected.id
        else:
            selected_id = (selected or {}).get("id")
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
            try:
                response = client.stop_test(job_id)
            except BackendApiError as exc:
                st.error(f"Ошибка остановки теста: {exc}")
            else:
                if response.success:
                    st.success(response.message or f"Тест {job_id} остановлен.")
                else:
                    st.warning(response.error or "Не удалось остановить тест")

        try:
            record = client.get_test_status(job_id)
        except BackendApiError as exc:
            status_box.error(f"Не удалось получить состояние прогона: {exc}")
            break

        payload = record.payload

        summary: JobSummary = payload.summary or record.summary or JobSummary(status=record.status)
        cases = payload.cases or []
        expected_total = payload.expected_total
        passed = int(summary.passed or 0)
        failed = int(summary.failed or 0)
        skipped = int(summary.skipped or 0)
        done = int(passed) + int(failed) + int(skipped)

        status_label = STATUS_LABELS.get(record.status, record.status)
        status_text = f"Статус: {status_label}"
        if summary.status and summary.status != record.status:
            status_text += f" (результат: {summary.status})"
        status_text += f" — {passed}✅ / {failed}❌ / {skipped}⏭"
        if expected_total:
            status_text += f" (готово {done} из {expected_total})"
        status_box.write(status_text)

        _render_cases_table(cases, table_box)

        if expected_total:
            progress_box.progress(min(done / max(expected_total, 1), 1.0))
        else:
            progress_box.progress(0.0 if done == 0 else min(done / max(len(cases), 1), 1.0))

        if record.status in {"completed", "failed", "stopped"}:
            break
        time.sleep(2)
