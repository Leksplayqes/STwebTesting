"""Sidebar widgets for quick actions and exports."""
from __future__ import annotations

import streamlit as st

from frontend.api import api_get


def sidebar_ui() -> None:
    st.markdown("")
    st.subheader("Быстрые действия")

    api_base = st.session_state.get("api_base_url")
    records = api_get(api_base, "/tests/jobs") or []
    if not records:
        st.info("Пока нет сохранённых тестов.")
        st.button("📊 Экспорт результатов", disabled=True, width='stretch')
    else:
        job_ids = [record.get("id") for record in records if record.get("id")]
        if not job_ids:
            st.warning("Нет корректных записей для экспорта.")
            st.button("📊 Экспорт результатов", disabled=True, width='stretch')
            st.button("🧾 Экспорт JUnit XML", disabled=True, width='stretch')
        else:
            selected = st.selectbox(
                "Выберите тест (job_id) для экспорта:",
                job_ids,
                key="sidebar_export_job_id",
            )
            job_url = f"{api_base}/tests/jobfile?job_id={selected}"
            st.markdown(
                f'<a href="{job_url}" download>'
                f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">📊 Экспорт результатов (JSON)</button>'
                f'</a>',
                unsafe_allow_html=True,
            )
            xml_url = f"{api_base}/tests/report?job_id={selected}"
            st.markdown(
                f'<a href="{xml_url}" download>'
                f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">🧾 Экспорт JUnit XML</button>'
                f'</a>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.subheader("Инструкция:")
    st.markdown(
        "\n".join(
            [
                "1. Настройте устройство во вкладке конфигурации",
                "2. Запустите тесты",
                "3. Просмотрите результаты",
                "4. Экспортируйте JSON при необходимости",
            ]
        )
    )
