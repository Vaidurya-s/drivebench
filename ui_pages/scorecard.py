"""Scorecard across named scenarios."""

from __future__ import annotations

import path_setup  # noqa: F401
import pandas as pd
import streamlit as st

from mpc_core.sim.copy_text import SCORECARD_LEDE, SCORECARD_TITLE
from mpc_core.sim.plotly_charts import metrics_bar_chart
from mpc_core.sim.ui import inject_styles, page_header
from mpc_core.sim.ui_cache import load_scorecard_rows

inject_styles()

page_header(title=SCORECARD_TITLE, look_for=SCORECARD_LEDE)

rows = load_scorecard_rows()
if rows is None:
    st.error("Missing data/ui/scorecard.json. Run: python scripts/precompute_ui_data.py")
    st.stop()
df = pd.DataFrame(rows)

# (column, chart title, y-axis label)
CHARTS = [
    ("Settling [s]", "Settling time", "s"),
    ("Overshoot [%]", "Overshoot", "%"),
    ("IAE [RPM·s]", "Integral absolute error", "RPM·s"),
    ("Max current [A]", "Peak armature current", "A"),
    ("Current limit [s]", "Time current-limited", "s"),
    ("Energy [J]", "Electrical energy", "J"),
]

scenario_pick = st.selectbox("Scenario", df["Scenario"].unique())
subset = df[df["Scenario"] == scenario_pick].copy()
controllers = subset["Controller"].tolist()

st.markdown(f"##### {scenario_pick}")
cols = st.columns(3)
for i, (col_name, title, unit) in enumerate(CHARTS):
    with cols[i % 3]:
        st.plotly_chart(
            metrics_bar_chart(
                controllers,
                subset[col_name].fillna(0).tolist(),
                title,
                y_title=unit,
            ),
            use_container_width=True,
        )
st.caption(
    "A missing settling time means the speed never stayed inside the 2 % band "
    "(shown as 0 in the bar chart)."
)

st.markdown("##### All metrics for this scenario")
detail = subset.drop(columns=["Scenario"]).set_index("Controller").T
st.dataframe(detail.style.format("{:.3g}", na_rep="—"), use_container_width=True)

st.markdown("##### Compare one metric across scenarios")
metric = st.selectbox("Metric", [c for c in df.columns if c not in ("Scenario", "Controller")])
pivot = df.pivot(index="Scenario", columns="Controller", values=metric)
st.dataframe(pivot.style.format("{:.3g}", na_rep="—"), use_container_width=True)
