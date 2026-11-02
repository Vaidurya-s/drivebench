"""Streamlit helpers for DriveBench: CSS, headers, readout tiles, legend."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from mpc_core.sim import theme as T
from mpc_core.sim.copy_text import APP_NAME, APP_SUBTITLE


@dataclass(frozen=True)
class InsightItem:
    label: str
    value: str
    hint: str | None = None
    tone: str | None = None  # success | warning | critical | None


def css() -> str:
    """The full stylesheet (also used by tests and the contrast script)."""
    return f"""
@import url('{T.FONT_IMPORT}');

html, body, [class*="css"], .stApp {{ font-family: {T.FONT_SANS}; color: {T.TEXT_PRIMARY}; }}
.stApp {{ background-color: {T.CANVAS}; }}
header[data-testid="stHeader"] {{ background: {T.CANVAS}; }}
section[data-testid="stSidebar"] {{ background-color: {T.SIDEBAR}; border-right: 1px solid {T.BORDER}; }}
section[data-testid="stSidebar"] * {{ color: {T.TEXT_SECONDARY}; }}
div[data-testid="stSidebarNav"] li a {{ border-radius: 3px; }}
div[data-testid="stSidebarNav"] li a[aria-current="page"] {{ background-color: {T.RAISED}; color: {T.TEXT_PRIMARY}; }}

h1, h2, h3, h4 {{ color: {T.TEXT_PRIMARY}; letter-spacing: -0.01em; }}
code, pre, .mono, div[data-testid="stMetricValue"], input[type="number"] {{ font-family: {T.FONT_MONO} !important; }}

.db-brand {{ margin: 0 0 14px 0; padding: 0 0 12px 0; border-bottom: 1px solid {T.BORDER}; }}
.db-brand b {{ display:block; font-size: 18px; font-weight: 600; color: {T.TEXT_PRIMARY}; letter-spacing: 0.02em; }}
.db-brand span {{ font-size: 10px; letter-spacing: 0.12em; color: {T.TEXT_MUTED}; text-transform: uppercase; }}

.db-statusbar {{ display:flex; flex-wrap:wrap; gap: 6px 22px; padding: 8px 12px; margin: 0 0 18px 0;
  background: {T.PANEL}; border: 1px solid {T.BORDER}; border-left: 3px solid {T.ACCENT}; border-radius: 3px; }}
.db-status-item {{ font-size: 12px; color: {T.TEXT_SECONDARY}; }}
.db-status-item b {{ font-family: {T.FONT_MONO}; font-weight: 500; color: {T.TEXT_PRIMARY}; }}

.db-eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: {T.ACCENT}; margin: 0 0 4px 0; }}
.db-title {{ font-size: 26px; font-weight: 600; line-height: 1.25; color: {T.TEXT_PRIMARY}; margin: 0 0 6px 0; }}
.db-lede {{ font-size: 15px; line-height: 1.55; color: {T.TEXT_SECONDARY}; max-width: 78ch; margin: 0 0 16px 0; }}

.db-panel {{ background: {T.PANEL}; border: 1px solid {T.BORDER}; border-radius: 3px; padding: 14px 16px; margin: 0 0 12px 0; }}
.db-panel h4 {{ margin: 0 0 6px 0; font-size: 14px; }}
.db-panel p {{ margin: 0; font-size: 14px; line-height: 1.5; color: {T.TEXT_SECONDARY}; }}

.db-readouts {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 0 0 14px 0; }}
.db-readout {{ background: {T.PANEL}; border: 1px solid {T.BORDER}; border-top-width: 3px; border-radius: 3px; padding: 10px 12px; }}
.db-readout-name {{ font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; margin: 0 0 6px 0; }}
.db-readout-row {{ display:flex; justify-content: space-between; font-size: 12px; color: {T.TEXT_SECONDARY}; margin: 2px 0; }}
.db-readout-row b {{ font-family: {T.FONT_MONO}; font-weight: 500; color: {T.TEXT_PRIMARY}; }}

.db-legend {{ display:flex; flex-wrap:wrap; gap: 8px 20px; padding: 8px 12px; margin: 0 0 12px 0;
  background: {T.PANEL}; border: 1px solid {T.BORDER}; border-radius: 3px; }}
.db-legend-item {{ display:inline-flex; align-items:center; gap: 8px; font-size: 13px; color: {T.TEXT_PRIMARY}; }}
.db-swatch {{ width: 22px; height: 0; border-top-width: 3px; border-top-color: currentColor; flex-shrink:0; }}

.db-insights {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 8px 0; }}
.db-insight {{ background: {T.PANEL}; border: 1px solid {T.BORDER}; border-radius: 3px; padding: 10px 12px; }}
.db-insight-label {{ font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {T.TEXT_MUTED}; margin: 0 0 4px 0; }}
.db-insight-value {{ font-family: {T.FONT_MONO}; font-size: 17px; color: {T.TEXT_PRIMARY}; margin: 0; }}
.db-insight-hint {{ font-size: 12px; color: {T.TEXT_SECONDARY}; margin: 4px 0 0 0; }}
.db-insight-hint.tone-success {{ color: {T.SUCCESS}; }}
.db-insight-hint.tone-warning {{ color: {T.WARNING}; }}
.db-insight-hint.tone-critical {{ color: {T.CRITICAL}; }}

.db-badge {{ display:inline-block; padding: 2px 8px; border-radius: 2px; font-size: 12px; font-weight: 600; font-family: {T.FONT_MONO}; }}
.db-badge.ok {{ background: rgba(85,198,142,0.15); color: {T.SUCCESS}; border: 1px solid {T.SUCCESS}; }}
.db-badge.bad {{ background: rgba(240,108,114,0.15); color: {T.CRITICAL}; border: 1px solid {T.CRITICAL}; }}
.db-chip {{ display:inline-block; padding: 1px 8px; margin: 0 6px 4px 0; border: 1px solid {T.WARNING}; color: {T.WARNING};
  border-radius: 2px; font-size: 12px; font-family: {T.FONT_MONO}; }}

.db-footer {{ margin-top: 28px; padding-top: 12px; border-top: 1px solid {T.BORDER}; font-size: 12px; color: {T.TEXT_MUTED}; }}

div[data-testid="stMetric"] {{ background: {T.PANEL}; border: 1px solid {T.BORDER}; border-radius: 3px; padding: 10px 12px; }}
div[data-testid="stExpander"] {{ background: {T.PANEL}; border: 1px solid {T.BORDER}; border-radius: 3px; }}
div[data-testid="stTabs"] button[aria-selected="true"] {{ color: {T.ACCENT}; }}

@media (max-width: 640px) {{
  .db-title {{ font-size: 21px; }}
  .db-readouts {{ grid-template-columns: 1fr 1fr; }}
  .db-statusbar {{ gap: 4px 12px; }}
}}
"""


def inject_styles() -> None:
    st.markdown(f"<style>{css()}</style>", unsafe_allow_html=True)


def sidebar_brand() -> None:
    st.sidebar.markdown(
        f'<div class="db-brand"><b>{escape(APP_NAME)}</b><span>{escape(APP_SUBTITLE)}</span></div>',
        unsafe_allow_html=True,
    )


def page_header(*, title: str, look_for: str, eyebrow: str | None = None) -> None:
    eyebrow_html = f'<p class="db-eyebrow">{escape(eyebrow)}</p>' if eyebrow else ""
    st.markdown(
        f'{eyebrow_html}<h1 class="db-title">{escape(title)}</h1><p class="db-lede">{look_for}</p>',
        unsafe_allow_html=True,
    )


def status_bar(*, plant: str, model: str, ts_ms: float, scenario: str) -> None:
    items = (
        ("Plant", plant),
        ("Model", model),
        ("Controller Ts", f"{ts_ms:g} ms"),
        ("Scenario", scenario),
    )
    cells = "".join(
        f'<span class="db-status-item">{escape(k)}: <b>{escape(v)}</b></span>' for k, v in items
    )
    st.markdown(f'<div class="db-statusbar">{cells}</div>', unsafe_allow_html=True)


def controller_legend(ids: tuple[str, ...] = tuple(T.CONTROLLER_LABELS)) -> None:
    chips = "".join(
        f'<span class="db-legend-item" style="color:{T.CONTROLLER_COLORS[c]}">'
        f'<span class="db-swatch" style="border-top-style:{_css_dash(c)}"></span>'
        f'<span style="color:{T.TEXT_PRIMARY}">{T.CONTROLLER_LABELS[c]}</span></span>'
        for c in ids
    )
    st.markdown(f'<div class="db-legend">{chips}</div>', unsafe_allow_html=True)
    if "lqr" in ids:
        st.caption(
            "LQR here is the integral-augmented design (LQI): the integral state gives "
            "zero steady-state speed error."
        )


def _css_dash(cid: str) -> str:
    return {"solid": "solid", "dash": "dashed", "dashdot": "dotted"}[T.CONTROLLER_DASH[cid]]


def readout_tiles(rows: dict[str, list[tuple[str, str]]]) -> None:
    """Compact per-controller summaries: ``{controller_id: [(label, value), ...]}``."""
    tiles = []
    for cid, items in rows.items():
        color = T.CONTROLLER_COLORS[cid]
        body = "".join(
            f'<div class="db-readout-row"><span>{escape(k)}</span><b>{escape(v)}</b></div>'
            for k, v in items
        )
        tiles.append(
            f'<div class="db-readout" style="border-top-color:{color}">'
            f'<p class="db-readout-name" style="color:{color}">{T.CONTROLLER_LABELS[cid]}</p>{body}</div>'
        )
    st.markdown(f'<div class="db-readouts">{"".join(tiles)}</div>', unsafe_allow_html=True)


def panel(title: str, body: str) -> None:
    st.markdown(
        f'<div class="db-panel"><h4>{escape(title)}</h4><p>{body}</p></div>',
        unsafe_allow_html=True,
    )


def badge(ok: bool, text: str) -> str:
    return f'<span class="db-badge {"ok" if ok else "bad"}">{escape(text)}</span>'


def constraint_chips(names: list[str]) -> None:
    if not names:
        st.markdown('<span class="db-badge ok">no active constraints</span>', unsafe_allow_html=True)
        return
    st.markdown("".join(f'<span class="db-chip">{escape(n)}</span>' for n in names), unsafe_allow_html=True)


def insight_strip(items: list[InsightItem]) -> None:
    cells = []
    for item in items:
        hint_html = ""
        if item.hint:
            tone_cls = f" tone-{item.tone}" if item.tone else ""
            hint_html = f'<p class="db-insight-hint{tone_cls}">{escape(item.hint)}</p>'
        cells.append(
            f'<div class="db-insight"><p class="db-insight-label">{escape(item.label)}</p>'
            f'<p class="db-insight-value">{escape(item.value)}</p>{hint_html}</div>'
        )
    st.markdown(f'<div class="db-insights">{"".join(cells)}</div>', unsafe_allow_html=True)


def footer_note(text: str) -> None:
    st.markdown(f'<p class="db-footer">{text}</p>', unsafe_allow_html=True)


def violation_tone(steps: int) -> tuple[str, str]:
    if steps <= 0:
        return "feasible", "success"
    if steps <= 2:
        return "violated", "warning"
    return "violated", "critical"
