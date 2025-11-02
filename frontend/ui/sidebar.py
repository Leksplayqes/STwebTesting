"""Sidebar widgets for quick actions and exports."""
from __future__ import annotations

import streamlit as st

from frontend.api import BackendApiClient, BackendApiError

from frontend.api import BackendApiClient, BackendApiError

def sidebar_ui(client: BackendApiClient, api_base: str) -> None:
    st.markdown("")
    st.subheader("Быстрые действия")

    try:
        records = client.list_test_jobs()
    except BackendApiError as exc:
        st.warning(f"Не удалось загрузить список тестов: {exc}")
        records = []
    if not records:
        st.info("Пока нет сохранённых тестов.")
        st.button("📊 Экспорт результатов", disabled=True, width='stretch')
    else:
        job_ids = []
        for record in records:
            job_id = None
            if isinstance(record, BaseModel):
                job_id = record.id
            elif isinstance(record, dict):
                job_id = record.get("id")
            else:
                job_id = getattr(record, "id", None)
            if job_id:
                job_ids.append(job_id)
        if not job_ids:
            st.warning("Нет корректных записей для экспорта.")
            st.button("📊 Экспорт результатов", disabled=True, width='stretch')
        else:
            selected = st.selectbox(
                "Выберите тест (job_id) для экспорта:",
                job_ids,
                key="sidebar_export_job_id",
            )
            job_url = f"{api_base.rstrip('/')}/tests/jobfile?job_id={selected}"
            st.markdown(
                f'<a href="{job_url}" download>'
                f'<button class="st-emotion-cache-1vt4y43 ef3psqc12" style="width:100%;">📊 Экспорт результатов (JSON)</button>'
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
