"""Performance Review: four-controller scorecard across scenarios."""

from __future__ import annotations

import path_setup  # noqa: F401
import pandas as pd
import streamlit as st

from mpc_core.sim import theme as T
from mpc_core.sim.copy_text import PERF_LEDE, PERF_TITLE
from mpc_core.sim.plotly_charts import grouped_metrics_figure
from mpc_core.sim.ui import page_header, status_bar
from mpc_core.sim.ui_cache import load_scorecard_rows
from mpc_core.sim.ui_state import chrome

chrome()
page_header(title=PERF_TITLE, look_for=PERF_LEDE, eyebrow="Page 5")

rows = load_scorecard_rows()
if rows is None:
    st.error("Missing data/ui/scorecard.json. Run: python scripts/precompute_ui_data.py")
    st.stop()
df = pd.DataFrame(rows)
label_to_id = {v: k for k, v in T.CONTROLLER_LABELS.items()}
label_to_id["Optimized PID"] = "optimized_pid"
df["cid"] = df["Controller"].map(label_to_id)

scenario = st.selectbox("Scenario", df["Scenario"].unique())
status_bar(plant="PMDC motor", model="3-state, RK4 1 ms", ts_ms=10, scenario=scenario)
sub = df[df["Scenario"] == scenario].set_index("cid")
order = [c for c in T.CONTROLLER_LABELS if c in sub.index]

CHARTS = [
    ("Rise [s]", "Rise time", "s"),
    ("Settling [s]", "Settling time", "s"),
    ("Overshoot [%]", "Overshoot", "%"),
    ("IAE [RPM·s]", "IAE", "RPM·s"),
    ("ISE [RPM²·s]", "ISE", "RPM²·s"),
    ("ITAE [RPM·s²]", "ITAE", "RPM·s²"),
    ("Max current [A]", "Peak current", "A"),
    ("Current limit [s]", "Time current-limited", "s"),
    ("Voltage saturation [s]", "Time voltage-saturated", "s"),
    ("Energy [J]", "Electrical energy", "J"),
    ("Mechanical energy [J]", "Mechanical energy", "J"),
    ("Mean exec [ms]", "Mean execution time", "ms"),
]
groups = {
    "Response time": CHARTS[0:2],
    "Overshoot and error": CHARTS[2:6],
    "Current and voltage limits": CHARTS[6:9],
    "Energy": CHARTS[9:11],
    "Execution time": CHARTS[11:12],
}
tabs = st.tabs(list(groups))
for tab, (_, charts) in zip(tabs, groups.items()):
    with tab:
        cols = st.columns(2)
        for i, (col_name, title, unit) in enumerate(charts):
            with cols[i % 2]:
                vals = {c: [float(sub.loc[c, col_name]) if pd.notna(sub.loc[c, col_name]) else 0.0] for c in order}
                st.plotly_chart(
                    grouped_metrics_figure(vals, [title], title=f"{title} [{unit}]", y_title=unit, height=300),
                    use_container_width=True,
                )
st.caption("A missing settling time means the speed never stayed inside the 2 % band (drawn as 0).")

st.markdown("##### All metrics for this scenario")
detail = sub.loc[order].drop(columns=["Scenario", "Controller"]).T
detail.columns = [T.CONTROLLER_LABELS[c] for c in order]
st.dataframe(detail.style.format("{:.3g}", na_rep="—"), use_container_width=True)

st.markdown("##### One metric across scenarios")
metric = st.selectbox("Metric", [c for c in df.columns if c not in ("Scenario", "Controller", "cid")])
pivot = df.pivot(index="Scenario", columns="Controller", values=metric)
st.dataframe(pivot.style.format("{:.3g}", na_rep="—"), use_container_width=True)
