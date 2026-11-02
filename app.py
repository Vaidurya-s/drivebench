"""DriveBench: PMDC motor control and analysis studio (Streamlit entrypoint).

Community Cloud runs ``streamlit run app.py`` from the repo root and installs only
requirements.txt. ``path_setup`` puts ``src/`` on sys.path so pages can import ``mpc_core``.
"""

from __future__ import annotations

import path_setup  # noqa: F401 — src/ on sys.path before page imports

import streamlit as st

st.set_page_config(
    page_title="DriveBench · PMDC Motor Control & Analysis Studio",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("ui_pages/overview.py", title="System Overview", default=True),
    st.Page("ui_pages/bench.py", title="Experiment Bench"),
    st.Page("ui_pages/lqr_studio.py", title="LQR Design Studio"),
    st.Page("ui_pages/mpc_explorer.py", title="MPC Prediction Explorer"),
    st.Page("ui_pages/performance.py", title="Performance Review"),
    st.Page("ui_pages/plant_model.py", title="Plant Model"),
]
st.navigation(pages).run()
