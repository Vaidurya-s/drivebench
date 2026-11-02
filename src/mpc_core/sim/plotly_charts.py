"""DriveBench Plotly chart system: graphite plot area, one physical quantity per axis.

Every figure comes from :func:`chart_layout` so fonts, grid, legend rail and hover are
identical. Controllers keep one colour *and* one dash style everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mpc_core.sim import theme as T

if TYPE_CHECKING:
    from mpc_core.sim.simulate import SimulationResult

TICK_FONT = dict(family=T.FONT_MONO, size=12, color=T.TEXT_SECONDARY)

QUANTITIES: dict[str, tuple[str, str]] = {
    "speed": ("Speed", "Speed [RPM]"),
    "current": ("Armature current", "Armature current [A]"),
    "voltage": ("Drive voltage", "Voltage [V]"),
    "torque": ("Torque", "Torque [N·m]"),
    "power": ("Power and energy", "Power [W]"),
}


def chart_layout(title: str = "", *, height: int = 420, **kwargs) -> dict:
    layout = dict(
        title=dict(text=title, x=0.0, xanchor="left", font=dict(size=16, color=T.TEXT_PRIMARY)),
        paper_bgcolor=T.PANEL,
        plot_bgcolor=T.CANVAS,
        font=dict(family=T.FONT_SANS, size=13, color=T.TEXT_PRIMARY),
        legend=dict(
            orientation="v", x=1.01, xanchor="left", y=1.0, yanchor="top",
            bgcolor="rgba(0,0,0,0)", font=dict(size=13, color=T.TEXT_PRIMARY),
        ),
        margin=dict(l=64, r=150, t=52, b=52),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=T.RAISED, font=dict(family=T.FONT_MONO, size=12, color=T.TEXT_PRIMARY)),
        height=height,
    )
    layout.update(kwargs)
    return layout


def style_axes(fig: go.Figure) -> None:
    for update in (fig.update_xaxes, fig.update_yaxes):
        update(
            showgrid=True, gridcolor=T.GRID, gridwidth=1, zeroline=False,
            linecolor=T.BORDER, tickfont=TICK_FONT,
            title_font=dict(size=13, color=T.TEXT_SECONDARY),
        )


def _line(cid: str) -> dict:
    return dict(
        color=T.CONTROLLER_COLORS[cid], width=T.CONTROLLER_WIDTH[cid], dash=T.CONTROLLER_DASH[cid]
    )


def _add_events(fig: go.Figure, events: Iterable[tuple[float, str]], rows: list[int] | None = None) -> None:
    for t, label in events:
        fig.add_vline(
            x=t, line=dict(color=T.TEXT_MUTED, width=1, dash="dot"),
            annotation_text=label, annotation_font=dict(size=11, color=T.TEXT_SECONDARY),
            annotation_position="top left", row="all" if rows is None else rows[0], col="all" if rows is None else 1,
        )


def _band(fig: go.Figure, lo: float, hi: float, name: str, row: int | None = None) -> None:
    kw = {} if row is None else dict(row=row, col=1)
    fig.add_hrect(y0=hi, y1=hi * 1.6 if hi > 0 else hi, fillcolor=T.CRITICAL, opacity=0.08, line_width=0, **kw)
    fig.add_hrect(y0=lo * 1.6 if lo < 0 else lo, y1=lo, fillcolor=T.CRITICAL, opacity=0.08, line_width=0, **kw)
    for y in (lo, hi):
        fig.add_hline(y=y, line=dict(color=T.LIMIT, width=1, dash="dash"), **kw)


def cumulative_energy(run: SimulationResult, ts_s: float) -> np.ndarray:
    return np.cumsum(run.p_elec_w) * ts_s


def quantity_figure(
    runs: Mapping[str, SimulationResult],
    quantity: str,
    *,
    events: Iterable[tuple[float, str]] = (),
    ts_s: float = 0.02,
) -> go.Figure:
    """One tab of the bench: every controller on a single quantity."""
    first = next(iter(runs.values()))
    title, ylabel = QUANTITIES[quantity]
    if quantity == "power":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                            row_heights=[0.55, 0.45])
        for cid, run in runs.items():
            fig.add_trace(go.Scatter(x=run.time_s, y=run.p_elec_w, name=T.CONTROLLER_LABELS[cid],
                                     legendgroup=cid, line=_line(cid)), row=1, col=1)
            fig.add_trace(go.Scatter(x=run.time_s, y=cumulative_energy(run, ts_s),
                                     name=T.CONTROLLER_LABELS[cid], legendgroup=cid,
                                     showlegend=False, line=_line(cid)), row=2, col=1)
        fig.update_yaxes(title_text="Electrical power [W]", row=1, col=1)
        fig.update_yaxes(title_text="Net electrical energy [J]", row=2, col=1)
        fig.update_xaxes(title_text="Time [s]", row=2, col=1)
        fig.update_layout(**chart_layout("Power and energy", height=560))
        _add_events(fig, events)
        style_axes(fig)
        return fig

    fig = go.Figure()
    if quantity == "speed":
        fig.add_trace(go.Scatter(x=first.time_s, y=first.ref_rpm, name="Reference",
                                 line=dict(color=T.SETPOINT, width=1.5, dash="dash")))
    for cid, run in runs.items():
        y = {
            "speed": run.speed_rpm, "current": run.i_a, "voltage": run.v_applied,
            "torque": run.torque_nm,
        }[quantity]
        fig.add_trace(go.Scatter(x=run.time_s, y=y, name=T.CONTROLLER_LABELS[cid], line=_line(cid)))
    if quantity == "voltage":
        fig.add_trace(go.Scatter(x=first.time_s, y=next(iter(runs.values())).v_cmd * np.nan,
                                 showlegend=False, hoverinfo="skip"))
    if quantity == "torque":
        fig.add_trace(go.Scatter(x=first.time_s, y=first.load_nm, name="Load torque",
                                 line=dict(color=T.LOAD, width=1.5, dash="dot")))
    if quantity == "current":
        _band(fig, -first.i_max, first.i_max, "I_max")
    if quantity == "voltage":
        _band(fig, -first.v_max, first.v_max, "V_max")
    fig.update_yaxes(title_text=ylabel)
    fig.update_xaxes(title_text="Time [s]")
    height = 460 if quantity == "speed" else 380
    fig.update_layout(**chart_layout(title, height=height))
    _add_events(fig, events)
    style_axes(fig)
    return fig


def requested_vs_applied_figure(run: SimulationResult, label: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=run.time_s, y=run.v_cmd, name="Requested",
                             line=dict(color=T.CONTROLLER_COLORS.get(run.controller_id, T.ACCENT), width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=run.time_s, y=run.v_applied, name="Applied (after drive)",
                             line=dict(color=T.TEXT_PRIMARY, width=1.8)))
    _band(fig, -run.v_max, run.v_max, "V_max")
    fig.update_yaxes(title_text="Voltage [V]")
    fig.update_xaxes(title_text="Time [s]")
    fig.update_layout(**chart_layout(f"{label}: requested vs applied voltage", height=320))
    style_axes(fig)
    return fig


def mpc_explorer_figure(snapshot, *, ts_s: float, i_max: float, v_max: float, max_dv: float | None = None) -> go.Figure:
    """Predicted speed, armature current and planned voltage over the horizon for one step."""
    h = len(snapshot.predicted_y)
    t_future = [snapshot.time_s + (i + 1) * ts_s for i in range(h)]
    c = T.CONTROLLER_COLORS["mpc"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        row_heights=[0.4, 0.3, 0.3])
    fig.add_trace(go.Scatter(x=[snapshot.time_s], y=[snapshot.y_meas], mode="markers",
                             name="Measured now",
                             marker=dict(size=12, color=T.ACCENT, line=dict(width=2, color=T.TEXT_PRIMARY))),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=t_future, y=snapshot.predicted_y, name="Predicted speed",
                             line=dict(color=c, width=2.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=[snapshot.time_s, t_future[-1]] if h else [], y=[snapshot.y_ref] * 2,
                             name="Reference", line=dict(color=T.SETPOINT, width=1.5, dash="dash")),
                  row=1, col=1)
    if snapshot.predicted_i:
        fig.add_trace(go.Scatter(x=t_future, y=snapshot.predicted_i, name="Predicted current",
                                 line=dict(color=c, width=2.2)), row=2, col=1)
        _band(fig, -i_max, i_max, "I_max", row=2)
    plan = getattr(snapshot, "planned_u_traj", None) or []
    if plan:
        fig.add_trace(go.Scatter(x=t_future[: len(plan)], y=plan, name="Planned voltage",
                                 line=dict(color=c, width=2.2, shape="hv")), row=3, col=1)
        _band(fig, -v_max, v_max, "V_max", row=3)
    fig.update_yaxes(title_text="Speed [RPM]", row=1, col=1)
    fig.update_yaxes(title_text="Current [A]", row=2, col=1)
    fig.update_yaxes(title_text="Voltage [V]", row=3, col=1)
    fig.update_xaxes(title_text="Time [s]", row=3, col=1)
    fig.update_layout(**chart_layout("Prediction over the horizon", height=620))
    style_axes(fig)
    return fig


def pole_figure(eigenvalues: np.ndarray) -> go.Figure:
    th = np.linspace(0, 2 * np.pi, 200)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.cos(th), y=np.sin(th), mode="lines", name="Unit circle",
                             line=dict(color=T.BORDER, width=1.5), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=eigenvalues.real, y=eigenvalues.imag, mode="markers",
                             name="Closed-loop poles",
                             marker=dict(size=11, symbol="x", color=T.CONTROLLER_COLORS["lqr"], line=dict(width=2))))
    fig.update_xaxes(title_text="Real", range=[-1.1, 1.1])
    fig.update_yaxes(title_text="Imaginary", range=[-1.1, 1.1], scaleanchor="x", scaleratio=1)
    fig.update_layout(**chart_layout("Closed-loop poles (z-plane)", height=360, hovermode="closest"))
    style_axes(fig)
    return fig


def grouped_metrics_figure(
    series: Mapping[str, list[float]],
    categories: list[str],
    *,
    title: str,
    y_title: str,
    height: int = 360,
) -> go.Figure:
    """Grouped bars: ``series`` maps controller id -> one value per category."""
    fig = go.Figure()
    for cid, ys in series.items():
        fig.add_trace(go.Bar(
            name=T.CONTROLLER_LABELS[cid], x=categories, y=ys, marker_color=T.CONTROLLER_COLORS[cid],
            text=[f"{v:.3g}" for v in ys], textposition="outside", cliponaxis=False,
            textfont=dict(family=T.FONT_MONO, size=11, color=T.TEXT_SECONDARY),
        ))
    fig.update_yaxes(title_text=y_title)
    fig.update_layout(**chart_layout(title, height=height, barmode="group", hovermode="closest"))
    style_axes(fig)
    return fig


def controller_color(cid: str) -> str:
    return T.CONTROLLER_COLORS[cid]
