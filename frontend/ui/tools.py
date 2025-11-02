"""Widgets exposing auxiliary backend utilities."""
from __future__ import annotations

import streamlit as st

from frontend.api import util_check_conf, util_check_hash, util_fpga_reload, util_jobs
from frontend.ui.components import render_runs_list


def _show_util_response(res) -> None:
    if not res:
        st.error("Ошибка запроса")
        return
    payload = (res.get("record") or {}).get("payload") or {}
    if res.get("success"):
        st.success("Готово")
        if payload.get("result") is not None:
            st.json(payload.get("result"))
    else:
        st.error(res.get("error") or "Запуск завершился с ошибкой")
        if payload.get("error"):
            st.write(payload.get("error"))


def render_utils(api_base: str) -> None:
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
            res = util_check_conf(api_base, ip, pw, iterations=int(iterations), delay=int(delay))
            _show_util_response(res)

    with st.expander("🧮 Сравнение директорий по MD5 (check_hash)"):
        d1 = st.text_input("Директория A (на сервере)", key="util_h_a")
        d2 = st.text_input("Директория B (на сервере)", key="util_h_b")
        if st.button("Сравнить"):
            if not d1 or not d2:
                st.warning("Укажите обе директории")
            else:
                res = util_check_hash(api_base, d1, d2)
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
            res = util_fpga_reload(api_base, ip2, pw2, int(slot), int(max_attempts))
            _show_util_response(res)

    st.markdown("---")
    st.subheader("История запусков утилит")
    records = util_jobs(api_base)
    selected = render_runs_list(
        records,
        key_prefix="utils",
        empty_message="Пока не было запусков утилит.",
    )
    if selected:
        st.markdown("**Детали выбранного запуска:**")
        st.json(selected.get("payload") or {})
