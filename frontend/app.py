"""Entry point assembling the modular Streamlit frontend."""
from __future__ import annotations

import os
import sys

import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from frontend.api import BackendApiClient
from frontend.constants import BUTTON_STYLE, DEFAULT_API_BASE_URL, PAGE_CONFIG
from frontend.state import apply_state, initialize_session_state
from frontend.ui import render_configuration, render_results, render_utils, sidebar_ui


st.set_page_config(**PAGE_CONFIG)
st.markdown(BUTTON_STYLE, unsafe_allow_html=True)


def main() -> None:
    st.markdown(
        "<h1 style='display:flex;align-items:center;gap:12px;'>🛠️ OSM-K Tester System</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    apply_state()
    initialize_session_state()

    api_base = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL)
    client = BackendApiClient(api_base)

    with st.sidebar:
        sidebar_ui(client, api_base)

    tab1, tab2, tab3 = st.tabs(["⚙️ Конфигурация тестирования", "📊 Результаты тестирования", "🔧 Утилиты"])
    with tab1:
        render_configuration(client)
    with tab2:
        render_results(client)
    with tab3:
        render_utils(client)


if __name__ == "__main__":  # pragma: no cover - executed by Streamlit
    main()
