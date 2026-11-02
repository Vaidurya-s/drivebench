"""Industrial DC Motor Control Lab — Streamlit entrypoint (st.Page + st.navigation).

Community Cloud runs ``streamlit run app.py`` from the repo root and installs only
requirements.txt (Streamlit app-dependencies docs). Local package code lives under
src/; ``path_setup`` adds that directory so pages can ``import mpc_core``.
"""

from __future__ import annotations

import path_setup  # noqa: F401 — src/ on sys.path before page imports

import streamlit as st

st.set_page_config(
    page_title="DC Motor Control Lab",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

overview = st.Page("ui_pages/overview.py", title="Overview", default=True)
playground = st.Page("ui_pages/playground.py", title="Playground")
step_through = st.Page("ui_pages/step_through.py", title="Step-through")
scorecard = st.Page("ui_pages/scorecard.py", title="Scorecard")

pg = st.navigation([overview, playground, step_through, scorecard])
pg.run()
