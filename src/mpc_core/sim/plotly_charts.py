"""Plotly figures for the Streamlit teaching UI (DESIGN.md chart tokens)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mpc_core.sim.theme import (
    ACCENT,
    BORDER,
    COBALT,
    COPPER,
    MPC_COLOR,
    OPT_PID_COLOR,
    PID_COLOR,
    SURFACE_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

if TYPE_CHECKING:
    from mpc_core.sim.simulate import SimulationResult


def _base_layout(**kwargs) -> dict:
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=SURFACE_SUBTLE,
        font=dict(family="Inter, system-ui, sans-serif", size=14, color=TEXT_PRIMARY),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            x=0,
            font=dict(size=13),
        ),
        margin=dict(l=48, r=24, t=72, b=48),
        hovermode="x unified",
    )
    layout.update(kwargs)
    return layout


def _style_axes(fig: go.Figure) -> None:
    fig.update_xaxes(
        showgrid=True,
        gridcolor=BORDER,
        zeroline=False,
        title_font=dict(size=13, color=TEXT_SECONDARY),
        tickfont=dict(size=12, color=TEXT_MUTED),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=BORDER,
        zeroline=False,
        title_font=dict(size=13, color=TEXT_SECONDARY),
        tickfont=dict(size=12, color=TEXT_MUTED),
    )


def triple_control_figure(
    *,
    mpc: SimulationResult,
    pid: SimulationResult,
    opt_pid: SimulationResult,
    step_at_s: float | None = None,
    load_change_at_s: float | None = None,
) -> go.Figure:
    """Speed, armature current, voltage and torque for all three controllers.

    One shared time axis; the current and voltage panels show the drive limits
    as dashed lines.
    """
    mpc_w, other_w = 2.6, 1.9
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "Motor speed",
            "Armature current",
            "Applied armature voltage",
            "Electromagnetic and load torque",
        ),
    )
    t = mpc.time_s
    fig.add_trace(
        go.Scatter(
            x=t,
            y=mpc.ref_rpm,
            name="Reference",
            line=dict(dash="dash", color=TEXT_PRIMARY, width=1.5),
        ),
        row=1,
        col=1,
    )
    # PID / Opt first, MPC last so it sits on top of the stack.
    for name, run, color, w in (
        ("PID", pid, PID_COLOR, other_w),
        ("Optimized PID", opt_pid, OPT_PID_COLOR, other_w),
        ("MPC", mpc, MPC_COLOR, mpc_w),
    ):
        fig.add_trace(
            go.Scatter(x=t, y=run.speed_rpm, name=name, line=dict(color=color, width=w)),
            row=1,
            col=1,
        )
        for row, y in ((2, run.i_a), (3, run.v_applied), (4, run.torque_nm)):
            fig.add_trace(
                go.Scatter(
                    x=t,
                    y=y,
                    name=name,
                    line=dict(color=color, width=w),
                    showlegend=False,
                ),
                row=row,
                col=1,
            )
    fig.add_trace(
        go.Scatter(
            x=t,
            y=mpc.load_nm,
            name="Load torque",
            line=dict(color=COPPER, width=1.6, dash="dot"),
        ),
        row=4,
        col=1,
    )
    for sign in (-1, 1):
        fig.add_hline(
            y=sign * mpc.i_max, line_dash="dash", line_color=TEXT_MUTED, line_width=1, row=2, col=1
        )
        fig.add_hline(
            y=sign * mpc.v_max, line_dash="dash", line_color=TEXT_MUTED, line_width=1, row=3, col=1
        )

    for x, color, label, ypos in (
        (step_at_s, TEXT_MUTED, "Reference step", 1.02),
        (load_change_at_s, COPPER, "Load change", 0.98),
    ):
        if x is None or x <= 0:
            continue
        for row in (1, 2, 3, 4):
            fig.add_vline(x=x, line_dash="dot", line_color=color, line_width=1.2, row=row, col=1)
        fig.add_annotation(
            x=x,
            y=ypos,
            yref="paper",
            text=label,
            showarrow=False,
            font=dict(size=11, color=color),
            xanchor="left",
        )

    fig.update_yaxes(title_text="RPM", row=1, col=1)
    fig.update_yaxes(title_text="A", row=2, col=1)
    fig.update_yaxes(title_text="V", row=3, col=1)
    fig.update_yaxes(title_text="N m", row=4, col=1)
    fig.update_xaxes(title_text="Time [s]", row=4, col=1)
    fig.update_layout(**_base_layout(height=860))
    fig.update_annotations(font=dict(size=14, color=TEXT_SECONDARY))
    _style_axes(fig)
    return fig


def mpc_horizon_figure(snapshot, ts_s: float = 0.01) -> go.Figure:
    """Predicted speed and armature current over the horizon for one MPC step."""
    h = len(snapshot.predicted_y)
    future_t = [snapshot.time_s + (i + 1) * ts_s for i in range(h)]
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.65, 0.35],
        subplot_titles=("Predicted speed", "Predicted armature current"),
    )
    fig.add_trace(
        go.Scatter(
            x=[snapshot.time_s],
            y=[snapshot.y_meas],
            mode="markers",
            name="Measured now",
            marker=dict(size=14, color=ACCENT, line=dict(width=2, color=TEXT_PRIMARY)),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=future_t,
            y=snapshot.predicted_y,
            mode="lines",
            name="Predicted speed",
            line=dict(color=ACCENT, width=2.5),
        ),
        row=1,
        col=1,
    )
    fig.add_hline(
        y=snapshot.y_ref,
        line_dash="dash",
        line_color=TEXT_PRIMARY,
        line_width=1.5,
        annotation_text="Reference",
        annotation_position="top right",
        annotation_font=dict(size=12, color=TEXT_PRIMARY),
        row=1,
        col=1,
    )
    if snapshot.predicted_i:
        fig.add_trace(
            go.Scatter(
                x=future_t,
                y=snapshot.predicted_i,
                mode="lines",
                name="Predicted current",
                line=dict(color=COPPER, width=2.2),
            ),
            row=2,
            col=1,
        )
    fig.update_yaxes(title_text="RPM", row=1, col=1)
    fig.update_yaxes(title_text="A", row=2, col=1)
    fig.update_xaxes(title_text="Time [s]", row=2, col=1)
    fig.update_layout(**_base_layout(height=560, margin=dict(l=56, r=24, t=72, b=48)))
    fig.update_annotations(font=dict(size=13, color=TEXT_SECONDARY))
    _style_axes(fig)
    return fig


def metrics_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    *,
    y_title: str | None = None,
) -> go.Figure:
    colors = [controller_color(label) for label in labels]
    text = [f"{v:.0f}" if abs(v) >= 10 else f"{v:.2g}" for v in values]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=text,
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=15, color=TEXT_PRIMARY)),
            height=300,
            margin=dict(l=40, r=20, t=56, b=40),
            showlegend=False,
            yaxis_title=y_title,
        )
    )
    _style_axes(fig)
    return fig


def controller_color(label: str) -> str:
    key = label.strip().lower()
    if key == "mpc":
        return MPC_COLOR
    if key in ("optimized pid", "opt. pid", "opt pid"):
        return OPT_PID_COLOR
    return PID_COLOR


def grouped_metrics_figure(
    controllers: list[str],
    metrics: dict[str, list[float]],
    *,
    title: str,
) -> go.Figure:
    """Side-by-side controller bars for several metrics on one figure."""
    fig = go.Figure()
    metric_names = list(metrics.keys())
    for idx, ctrl in enumerate(controllers):
        ys = [metrics[m][idx] for m in metric_names]
        fig.add_trace(
            go.Bar(
                name=ctrl,
                x=metric_names,
                y=ys,
                marker_color=controller_color(ctrl),
                text=[f"{v:.0f}" if abs(v) >= 10 else f"{v:.2g}" for v in ys],
                textposition="outside",
                cliponaxis=False,
            )
        )
    layout_kwargs: dict = dict(
        barmode="group",
        height=380,
        margin=dict(l=40, r=20, t=56, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left"),
    )
    if title:
        layout_kwargs["title"] = dict(text=title, font=dict(size=16, color=TEXT_PRIMARY), y=0.98)
    fig.update_layout(**_base_layout(**layout_kwargs))
    _style_axes(fig)
    return fig
