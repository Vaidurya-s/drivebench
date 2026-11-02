---
name: DriveBench
description: PMDC motor control and analysis studio comparing PID, optimised PID, LQR and MPC; a dark graphite instrumentation interface built on Streamlit.
colors:
  canvas: "#0D1722"
  sidebar: "#101E2A"
  panel: "#172633"
  raised: "#263A49"
  border: "#304656"
  grid: "#243747"
  text-primary: "#EAF1F5"
  text-secondary: "#B3C2CB"
  text-muted: "#8FA2B0"
  accent: "#36C4D8"
  pid: "#78A8D5"
  optimized-pid: "#43C5A2"
  lqr: "#F0B35A"
  mpc: "#B49AF7"
  success: "#55C68E"
  warning: "#F2994A"
  critical: "#F06C72"
typography:
  sans: "IBM Plex Sans, system-ui, sans-serif"
  mono: "IBM Plex Mono, ui-monospace, Consolas, monospace"
rounded:
  sm: "3px"
---

# DriveBench design notes

The single source of truth for colours in code is `src/mpc_core/sim/theme.py`; `.streamlit/config.toml`
mirrors the base theme. Update all three together.

## Principles

- An engineering workstation, not a marketing page: flat panels, 1 px slate borders, 3 px corners.
- No gradients, glow, blur or glassmorphism.
- Numbers (RPM, A, V, gains, matrices, chart ticks) are set in IBM Plex Mono; interface text in IBM Plex Sans.
  Fonts load from Google Fonts with system fallbacks, so the app still works offline.
- Every value shows its unit. One physical quantity per chart axis.

## Controller identity

| Controller | Colour | Line |
| --- | --- | --- |
| PID | `#78A8D5` | solid 1.8 |
| Optimised PID | `#43C5A2` | dashed 1.8 |
| LQR (LQI) | `#F0B35A` | dash-dot 2.0 |
| MPC | `#B49AF7` | solid 2.6 |

Colour is never the only cue: each controller also has its own dash/width. The LQR amber is close
to the warning colour, so warnings use the separate orange `#F2994A` plus text or an icon.

## Contrast

`tests/test_theme_ui.py` checks WCAG contrast: body, muted and status text at least 4.5:1 against
canvas and panel; controller lines at least 3:1 against the plot background.

## Charts (`sim/plotly_charts.py`)

Graphite plot area on a panel surface, slate grid, left-aligned titles, a vertical legend rail on
the right, unified hover, dashed setpoint, red shaded limit bands (`I_max`, `V_max`), dotted event
markers for speed steps, load steps and bus sag.

## Layout

Six pages: System Overview, Experiment Bench (left configuration rail, dominant speed chart,
tabbed secondary quantities, controller readout tiles), LQR Design Studio, MPC Prediction
Explorer, Performance Review, Plant Model. Every page starts with a status bar (plant, model,
controller period, scenario). Below 640 px the readout tiles collapse to two columns.

## Diagrams (`sim/diagrams.py`)

Inline SVG using the same tokens: drive architecture, four-controller architecture, LQR design
process. No external image assets.
