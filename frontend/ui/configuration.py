"""Widgets responsible for configuring test runs."""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

from api import BackendApiClient, BackendApiError, normalise_nodeids
from state import on_change, save_state, viavi_sync_from_widgets

PORT_OPTIONS = ["", "STM-1", "STM-4", "STM-16"]


def _safe_index(options: List[str], value: str, default: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return default


def render_configuration(client: BackendApiClient) -> None:
    st.header("Конфигурация тестирования")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.subheader("Основные настройки")
        device = st.session_state.get("device_info") or {}
        ip = st.text_input(
            "**IP адрес устройства**",
            value=device.get("ipaddr", st.session_state.get("ip_address_input", "")),
            key="ip_address_input",
            on_change=on_change,
        )
        pw = st.text_input("**Пароль (для v7)**", type="password", key="password_input", on_change=on_change)
        snmp = st.selectbox(
            "**Тип SNMP**",
            ["SnmpV2", "SnmpV3"],
            key="snmp_type_select",
            on_change=on_change,
        )
        if st.button("Проверить подключение"):
            if client.ping_device(ip):
                try:
                    viavi_sync_from_widgets()
                    loopback = {
                        "slot": st.session_state.get("slot_loopback"),
                        "port": st.session_state.get("port_loopback"),
                    }
                    viavi_cfg = st.session_state.get("viavi_config", {})
                    info = client.fetch_device_info(
                        ip=ip,
                        password=pw,
                        snmp_type=snmp,
                        viavi={k: v for k, v in viavi_cfg.items() if v},
                        loopback={k: v for k, v in loopback.items() if v},
                    )
                except BackendApiError as exc:
                    st.error(f"Не удалось получить информацию об устройстве: {exc}")
                else:
                    st.session_state["device_info"] = info.model_dump()
                    if info.viavi:
                        st.session_state["viavi_config"] = info.viavi
                    if info.loopback:
                        st.session_state["saved_loopback"] = info.loopback
                    save_state()

    with col2:
        st.subheader("Конфигурация тестов")
        catalogs = client.get_test_catalogs()
        test_type = st.radio(
            "**Тип тестов**",
            ["alarm", "sync"],
            format_func=lambda x: "Alarm Tests" if x == "alarm" else "Sync Tests",
            horizontal=True,
            key="test_type_radio",
            on_change=on_change,
        )
        tests_by_type = st.session_state.setdefault(
            "selected_tests_by_type", {"alarm": [], "sync": []}
        )
        labels_by_type = st.session_state.setdefault(
            "selected_test_labels_by_type", {"alarm": [], "sync": []}
        )
        st.session_state["selected_tests"] = tests_by_type.get(test_type, [])
        st.session_state["selected_test_labels"] = labels_by_type.get(test_type, [])
        session_labels = labels_by_type.get(test_type, [])
        if test_type == "alarm":
            test_map: Dict[str, str] = catalogs.alarm_tests
            multiselect_key = "tests_ms_alarm"
        else:
            test_map = catalogs.sync_tests
            multiselect_key = "tests_ms_sync"

        available_labels = list(test_map.keys())
        default_labels = [label for label in session_labels if label in available_labels]
        selected_labels = st.multiselect(
            "Выберите тесты:",
            options=available_labels,
            default=default_labels,
            on_change=on_change,
            key=multiselect_key,
        )
        selected_nodeids = [test_map[label] for label in selected_labels]
        labels_by_type[test_type] = selected_labels
        tests_by_type[test_type] = selected_nodeids
        st.session_state["selected_test_labels"] = selected_labels
        st.session_state["selected_tests"] = selected_nodeids
        save_state()

    with col3:
        st.subheader("Статус устройства")
        dev = st.session_state.get("device_info")
        if dev:
            st.write(f"**Имя:** {dev.get('name') or '—'}")
            st.write(f"**IP:** {dev.get('ipaddr') or '—'}")
            slots = dev.get("slots_dict") or {}
            if slots:
                with st.expander("Слоты устройства", expanded=True):
                    st.json(slots)
            st.success("✅ Устройство доступно")
        else:
            st.warning("⚠️ Устройство не проверено")

    st.markdown("---")
    st.subheader("Дополнительная кофигурация")
    tab1, tab2, tab3 = st.tabs(["**Viavi №1**", "**Viavi №2**", "**Loopback**"])

    st.session_state.setdefault(
        "viavi_config",
        {
            "NumOne": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
            "NumTwo": {"ipaddr": "", "typeofport": {"Port1": "", "Port2": ""}},
        },
    )

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "**IP Viavi №1**",
                value=st.session_state.get("viavi1_ip", ""),
                key="viavi1_ip",
                on_change=viavi_sync_from_widgets,
            )
            d1, d2 = st.columns(2)
            with d1:
                st.selectbox(
                    "Port 1",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi1_port1", "")),
                    key="viavi1_port1",
                    on_change=viavi_sync_from_widgets,
                )
            with d2:
                st.selectbox(
                    "Port 2",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi1_port2", "")),
                    key="viavi1_port2",
                    on_change=viavi_sync_from_widgets,
                )
    with tab2:
        c3, c4 = st.columns(2)
        with c3:
            st.text_input(
                "**IP Viavi №2**",
                value=st.session_state.get("viavi2_ip", ""),
                key="viavi2_ip",
                on_change=viavi_sync_from_widgets,
            )
            d3, d4 = st.columns(2)
            with d3:
                st.selectbox(
                    "Port 1",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi2_port1", "")),
                    key="viavi2_port1",
                    on_change=viavi_sync_from_widgets,
                )
            with d4:
                st.selectbox(
                    "Port 2",
                    PORT_OPTIONS,
                    index=_safe_index(PORT_OPTIONS, st.session_state.get("viavi2_port2", "")),
                    key="viavi2_port2",
                    on_change=viavi_sync_from_widgets,
                )
    with tab3:
        c5, c6 = st.columns(2)
        with c5:
            st.selectbox(
                "**Слот с loopback**",
                [3, 4, 5, 6, 7, 8, 11, 12, 13, 14],
                key="slot_loopback",
                on_change=on_change,
            )
        with c6:
            st.selectbox(
                "**Порт с loopback**",
                [1, 2, 3, 4, 5, 6, 7, 8],
                key="port_loopback",
                on_change=on_change,
            )

    st.markdown("---")
    center = st.columns([1, 1, 1])[1]
    nodeids = normalise_nodeids(st.session_state.get("selected_tests") or [])
    with center:
        if st.button("🚀 Запустить тесты"):
            if not nodeids:
                st.warning("Не выбраны тесты.")
            else:
                payload = {
                    "test_type": st.session_state.get("test_type_radio", "manual"),
                    "selected_tests": nodeids,
                }
                try:
                    resp = client.run_tests(payload)
                except BackendApiError as exc:
                    st.error(f"Не удалось запустить тесты: {exc}")
                else:
                    if resp.success and resp.job_id:
                        st.session_state["current_job_id"] = resp.job_id
                        st.success(f"Тесты запущены. job_id = {resp.job_id}")
                    else:
                        st.error(resp.error or "Не удалось запустить тесты.")
