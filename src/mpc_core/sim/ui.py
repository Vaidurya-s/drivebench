"""Streamlit UI helpers mapped from DESIGN.md (DC Motor Control Lab)."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from mpc_core.sim.theme import (  # noqa: F401 — re-export tokens for pages
    BORDER,
    BORDER_STRONG,
    CANVAS,
    COBALT,
    COBALT_50,
    COBALT_100,
    COBALT_700,
    COBALT_HOVER,
    CONTROLLER_COLORS,
    COPPER,
    CRITICAL,
    MPC_COLOR,
    OPT_PID,
    OPT_PID_COLOR,
    PID,
    PID_COLOR,
    SUCCESS,
    SURFACE,
    SURFACE_SUBTLE,
    SURFACE_SUNKEN,
    TEXT_INVERSE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)


@dataclass(frozen=True)
class InsightItem:
    label: str
    value: str
    hint: str | None = None
    tone: str | None = None  # success | warning | critical | None


def sidebar_brand() -> None:
    """Product name in the sidebar."""
    from mpc_core.sim.copy_text import SIDEBAR_BRAND

    st.sidebar.markdown(
        f'<p style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY};'
        f'margin:0 0 12px 0;">{SIDEBAR_BRAND}</p>',
        unsafe_allow_html=True,
    )


def inject_styles() -> None:
    """Inject DESIGN.md typography and flat-section chrome once per page."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
  font-family: Inter, system-ui, sans-serif;
}}

.stApp {{
  background-color: {CANVAS};
}}

section[data-testid="stSidebar"] {{
  background-color: {SURFACE_SUBTLE};
  border-right: 1px solid {BORDER};
}}

div[data-testid="stSidebarNav"] li a {{
  border-radius: 4px;
}}

div[data-testid="stSidebarNav"] li a[aria-current="page"] {{
  background-color: {COBALT_50};
  color: {COBALT_700};
}}

.lab-eyebrow {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {TEXT_MUTED};
  margin: 0 0 4px 0;
}}

.lab-title {{
  font-size: 28px;
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.29;
  color: {TEXT_PRIMARY};
  margin: 0 0 8px 0;
}}

.lab-lookfor {{
  font-size: 16px;
  line-height: 1.5;
  color: {TEXT_SECONDARY};
  max-width: 72ch;
  margin: 0 0 20px 0;
}}

.lab-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  align-items: center;
  margin: 0 0 16px 0;
  padding: 10px 14px;
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 6px;
}}

.lab-legend-item {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: {TEXT_PRIMARY};
}}

.lab-swatch {{
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}}

.lab-insights {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 12px 0 8px 0;
}}

.lab-insight {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 6px;
  padding: 12px 14px;
}}

.lab-insight-label {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {TEXT_MUTED};
  margin: 0 0 4px 0;
}}

.lab-insight-value {{
  font-size: 18px;
  font-weight: 600;
  color: {TEXT_PRIMARY};
  margin: 0;
  line-height: 1.3;
}}

.lab-insight-hint {{
  font-size: 13px;
  color: {TEXT_SECONDARY};
  margin: 4px 0 0 0;
}}

.lab-insight-hint.tone-success {{ color: {SUCCESS}; }}
.lab-insight-hint.tone-warning {{ color: {WARNING}; }}
.lab-insight-hint.tone-critical {{ color: {CRITICAL}; }}

.lab-path {{
  display: grid;
  gap: 12px;
  margin: 8px 0 24px 0;
}}

.lab-path-item {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 6px;
  padding: 16px 18px;
}}

.lab-path-step {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {COBALT_700};
  margin: 0 0 4px 0;
}}

.lab-path-title {{
  font-size: 18px;
  font-weight: 600;
  color: {TEXT_PRIMARY};
  margin: 0 0 4px 0;
}}

.lab-path-body {{
  font-size: 15px;
  color: {TEXT_SECONDARY};
  margin: 0;
  line-height: 1.5;
}}

.lab-footer {{
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid {BORDER};
  font-size: 13px;
  color: {TEXT_MUTED};
}}

.lab-takeaway {{
  background: {COBALT_50};
  border: 1px solid {COBALT_100};
  border-radius: 6px;
  padding: 16px 18px;
  margin: 0 0 20px 0;
}}

.lab-takeaway-label {{
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {COBALT_700};
  margin: 0 0 6px 0;
}}

.lab-takeaway-body {{
  font-size: 16px;
  line-height: 1.5;
  color: {TEXT_PRIMARY};
  margin: 0;
}}

div[data-testid="stMetric"] {{
  background: {SURFACE};
  border: 1px solid {BORDER};
  border-radius: 6px;
  padding: 12px 14px;
}}

/* Diagram sits on canvas without a card edge */
div[data-testid="stImage"],
div[data-testid="stImageContainer"] {{
  background: {CANVAS} !important;
  box-shadow: none !important;
  border: none !important;
}}
div[data-testid="stImage"] img,
div[data-testid="stImageContainer"] img {{
  background: {CANVAS} !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def page_header(*, title: str, look_for: str, eyebrow: str | None = None) -> None:
    eyebrow_html = (
        f'<p class="lab-eyebrow">{eyebrow}</p>' if eyebrow else ""
    )
    st.markdown(
        f"{eyebrow_html}"
        f'<h1 class="lab-title">{title}</h1>'
        f'<p class="lab-lookfor">{look_for}</p>',
        unsafe_allow_html=True,
    )


def controller_legend() -> None:
    items = [
        ("MPC", MPC_COLOR),
        ("PID", PID_COLOR),
        ("Optimized PID", OPT_PID_COLOR),
    ]
    chips = "".join(
        f'<span class="lab-legend-item">'
        f'<span class="lab-swatch" style="background:{color}"></span>{name}</span>'
        for name, color in items
    )
    st.markdown(f'<div class="lab-legend">{chips}</div>', unsafe_allow_html=True)


def insight_strip(items: list[InsightItem]) -> None:
    cells = []
    for item in items:
        hint_html = ""
        if item.hint:
            tone_cls = f" tone-{item.tone}" if item.tone else ""
            hint_html = f'<p class="lab-insight-hint{tone_cls}">{item.hint}</p>'
        cells.append(
            f'<div class="lab-insight">'
            f'<p class="lab-insight-label">{item.label}</p>'
            f'<p class="lab-insight-value">{item.value}</p>'
            f"{hint_html}</div>"
        )
    st.markdown(f'<div class="lab-insights">{"".join(cells)}</div>', unsafe_allow_html=True)


def takeaway(*, label: str, body: str) -> None:
    st.markdown(
        f'<div class="lab-takeaway">'
        f'<p class="lab-takeaway-label">{label}</p>'
        f'<p class="lab-takeaway-body">{body}</p></div>',
        unsafe_allow_html=True,
    )


def demo_path(steps: list[tuple[str, str, str]]) -> None:
    blocks = []
    for step_label, title, body in steps:
        blocks.append(
            f'<div class="lab-path-item">'
            f'<p class="lab-path-step">{step_label}</p>'
            f'<p class="lab-path-title">{title}</p>'
            f'<p class="lab-path-body">{body}</p></div>'
        )
    st.markdown(f'<div class="lab-path">{"".join(blocks)}</div>', unsafe_allow_html=True)


def footer_note(text: str) -> None:
    st.markdown(f'<p class="lab-footer">{text}</p>', unsafe_allow_html=True)


def violation_tone(steps: int) -> tuple[str, str]:
    """Return (word, tone) for constraint violation count."""
    if steps <= 0:
        return "feasible", "success"
    if steps <= 2:
        return "violated", "warning"
    return "violated", "critical"
