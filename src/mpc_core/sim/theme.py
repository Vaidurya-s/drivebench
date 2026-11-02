"""DriveBench design tokens: dark graphite instrumentation theme.

No Streamlit or Plotly imports, so charts, CSS and scripts share one palette.
Hex values are mirrored in ``.streamlit/config.toml`` and ``DESIGN.md``.
"""

from __future__ import annotations

# Surfaces
CANVAS = "#0D1722"
SIDEBAR = "#101E2A"
PANEL = "#172633"
RAISED = "#263A49"
BORDER = "#304656"
GRID = "#243747"

# Text
TEXT_PRIMARY = "#EAF1F5"
TEXT_SECONDARY = "#B3C2CB"
TEXT_MUTED = "#8FA2B0"  # lifted from #8093A1 so it clears 4.5:1 on PANEL

# Accent and status
ACCENT = "#36C4D8"
SUCCESS = "#55C68E"
WARNING = "#F2994A"  # distinct from the LQR amber
CRITICAL = "#F06C72"

# Controllers (id -> colour, label, line dash). Dash makes them separable without colour.
CONTROLLER_COLORS = {
    "pid": "#78A8D5",
    "optimized_pid": "#43C5A2",
    "lqr": "#F0B35A",
    "mpc": "#B49AF7",
}
CONTROLLER_LABELS = {
    "pid": "PID",
    "optimized_pid": "Optimised PID",
    "lqr": "LQR",
    "mpc": "MPC",
}
CONTROLLER_DASH = {"pid": "solid", "optimized_pid": "dash", "lqr": "dashdot", "mpc": "solid"}
CONTROLLER_WIDTH = {"pid": 1.8, "optimized_pid": 1.8, "lqr": 2.0, "mpc": 2.6}
CONTROLLER_NOTES = {
    "pid": "Hand-tuned PID: fixed gains, speed feedback only.",
    "optimized_pid": "PID gains tuned once by optimisation, then frozen.",
    "lqr": "LQR with integral action (LQI): the integral state gives zero steady-state speed error.",
    "mpc": "Model predictive control: plans voltage over a horizon within voltage and current limits.",
}

FONT_SANS = "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
FONT_MONO = "'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, 'Courier New', monospace"
FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)

# Quantity colours for single-controller views
SETPOINT = "#EAF1F5"
LOAD = "#9DB3C2"
LIMIT = "#F06C72"
