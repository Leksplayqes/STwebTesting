"""Reusable UI pieces shared across multiple pages."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import streamlit as st

from pydantic import BaseModel


def _format_ts(ts: Optional[float]) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _to_dict(record: Any) -> Dict[str, Any]:
    if isinstance(record, BaseModel):
        return record.model_dump()
    if hasattr(record, "to_dict") and callable(getattr(record, "to_dict")):
        try:
            return record.to_dict()  # type: ignore[return-value]
        except Exception:  # pragma: no cover - defensive
            return dict(record)
    return dict(record)


def _describe_record(record: Dict[str, Any]) -> str:
    payload = record.get("payload") or {}
    summary = record.get("summary") or payload.get("summary") or {}
    if summary:
        return (
            f"{summary.get('total', 0)} тестов: "
            f"✅ {summary.get('passed', 0)} / ❌ {summary.get('failed', 0)} / ⏭ {summary.get('skipped', 0)}"
        )
    if payload.get("error"):
        text = str(payload.get("error") or "")
        return text[:140]
    if payload.get("result") is not None:
        result = payload.get("result")
        if isinstance(result, (str, int, float)):
            return str(result)[:140]
        if isinstance(result, Iterable):
            return "Результат содержит несколько элементов"
        return "Результат готов"
    return ""


def render_runs_list(
    records: Iterable[Any],
    *,
    key_prefix: str,
    title: Optional[str] = None,
    empty_message: str = "Нет запусков",
) -> Optional[Any]:
    """Render a table of execution records and return the selected entry."""

    prepared = []
    for rec in records:
        data = _to_dict(rec)
        if not data.get("id"):
            continue
        prepared.append((data, rec))
    if title:
        st.subheader(title)
    if not prepared:
        st.info(empty_message)
        return None

    data = []
    for raw, _ in prepared:
        payload = raw.get("payload") or {}
        summary = raw.get("summary") or payload.get("summary") or {}
        duration = payload.get("duration") or summary.get("duration")
        if duration is None:
            duration = summary.get("duration")
        data.append(
            {
                "ID": raw.get("id"),
                "Тип": raw.get("type"),
                "Статус": raw.get("status"),
                "Начало": _format_ts(raw.get("started_at") or payload.get("started")),
                "Конец": _format_ts(raw.get("finished_at") or payload.get("finished")),
                "Длительность, c": round(float(duration or 0.0), 2)
                if duration is not None
                else "",
                "Описание": _describe_record(raw),
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    options = [raw.get("id") for raw, _ in prepared]
    default_index = 0
    default_key = f"{key_prefix}_selected"
    if default_key in st.session_state:
        try:
            default_index = options.index(st.session_state[default_key])
        except ValueError:
            default_index = 0
    selected_id = st.selectbox(
        "Выберите запуск",
        options,
        index=default_index,
        key=default_key,
    )
    for raw, original in prepared:
        if raw.get("id") == selected_id:
            return original
    return None


__all__ = ["render_runs_list"]
