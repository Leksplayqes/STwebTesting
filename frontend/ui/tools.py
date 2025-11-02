"""Widgets exposing auxiliary backend utilities."""
from __future__ import annotations

import streamlit as st

from frontend.api import BackendApiClient, BackendApiError
from frontend.models import UtilityJobRecord, UtilityJobResponse
from frontend.ui.components import render_runs_list


def _show_util_response(res: UtilityJobResponse) -> None:
    if not res:
        st.error("Ошибка запроса")
        return
    payload = res.record.payload.model_dump() if res.record else {}
    if res.success:
        st.success("Готово")
        result = payload.get("result")
        if result is not None:
            st.json(result)
    else:
        st.error(res.error or "Запуск завершился с ошибкой")
        if payload.get("error"):
            st.write(payload.get("error"))


def render_utils(client: BackendApiClient) -> None:
    st.header("Утилиты (из checkFunctions)")

    with st.expander("📄 Проверка конфигурации (check_conf)", expanded=True):
        ip = st.text_input(
            "IP устройства (для check_conf)",
            key="util_cc_ip",
            value=(st.session_state.get("device_info") or {}).get("ipaddr", ""),
        )
        pw = st.text_input(
            "Пароль (для check_conf)",
            type="password",
            key="util_cc_pw",
            value=st.session_state.get("password_input", ""),
        )
        iterations = st.number_input("Количество повторов", min_value=1, max_value=50, value=3, step=1)
        delay = st.number_input("Задержка между повторами, с", min_value=1, max_value=600, value=30, step=1)
        if st.button("Запустить check_conf"):
            try:
                res = client.run_check_conf(ip=ip, password=pw, iterations=int(iterations), delay=int(delay))
            except BackendApiError as exc:
                st.error(f"Ошибка запуска check_conf: {exc}")
            else:
                _show_util_response(res)

    with st.expander("🧮 Сравнение директорий по MD5 (check_hash)"):
        d1 = st.text_input("Директория A (на сервере)", key="util_h_a")
        d2 = st.text_input("Директория B (на сервере)", key="util_h_b")
        if st.button("Сравнить"):
            if not d1 or not d2:
                st.warning("Укажите обе директории")
            else:
                try:
                    res = client.run_check_hash(dir1=d1, dir2=d2)
                except BackendApiError as exc:
                    st.error(f"Ошибка запуска check_hash: {exc}")
                else:
                    _show_util_response(res)

    with st.expander("🔁 FPGA reload (check_KSequal.fpga_reload)"):
        ip2 = st.text_input(
            "IP устройства (для fpga_reload)",
            key="util_fpga_ip",
            value=(st.session_state.get("device_info") or {}).get("ipaddr", ""),
        )
        pw2 = st.text_input(
            "Пароль (для fpga_reload)",
            type="password",
            key="util_fpga_pw",
            value=st.session_state.get("password_input", ""),
        )
        slot = st.number_input("Слот", min_value=1, max_value=16, value=9, step=1, key="util_fpga_slot")
        max_attempts = st.number_input("Число попыток", min_value=1, max_value=5000, value=1000, step=10)
        if st.button("Запустить fpga_reload"):
            try:
                res = client.run_fpga_reload(
                    ip=ip2,
                    password=pw2,
                    slot=int(slot),
                    max_attempts=int(max_attempts),
                )
            except BackendApiError as exc:
                st.error(f"Ошибка запуска fpga_reload: {exc}")
            else:
                _show_util_response(res)

    st.markdown("---")
    st.subheader("История запусков утилит")
    try:
        records = client.list_util_jobs()
    except BackendApiError as exc:
        st.error(f"Не удалось загрузить историю утилит: {exc}")
        records = []
    selected = render_runs_list(
        records,
        key_prefix="utils",
        empty_message="Пока не было запусков утилит.",
    )
    if selected:
        st.markdown("**Детали выбранного запуска:**")
        if isinstance(selected, UtilityJobRecord):
            st.json(selected.payload.model_dump())
        else:
            st.json((selected or {}).get("payload") or {})
