---
name: DC Motor Control Lab
description: Offset-free MPC vs hand-tuned PID vs optimized PID on a permanent-magnet DC motor drive — a Streamlit teaching lab for classroom demos.
colors:
  canvas: "#FAFAF9"
  surface: "#FFFFFF"
  surface-subtle: "#F5F5F4"
  surface-sunken: "#EFEFED"
  border: "#E4E4E2"
  border-strong: "#D4D4D1"
  text-primary: "#202020"
  text-secondary: "#5F5F5C"
  text-muted: "#8A8A86"
  text-inverse: "#FFFFFF"
  cobalt: "#2F6FEB"
  cobalt-50: "#EEF3FE"
  cobalt-100: "#DCE6FD"
  cobalt-700: "#1D47A3"
  cobalt-800: "#173879"
  copper: "#E07A3F"
  pid: "#71717A"
  opt-pid: "#0D9488"
  success: "#2F9E6A"
  warning: "#E0A526"
  critical: "#D0312D"
typography:
  display:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 500
    lineHeight: 1.29
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.625
    letterSpacing: "normal"
  label:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.06em"
rounded:
  sm: "4px"
  md: "6px"
  full: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "24px"
  "6": "32px"
  "7": "48px"
  "8": "64px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.text-inverse}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "#2459C9"
    textColor: "{colors.text-inverse}"
  chip-selected:
    backgroundColor: "{colors.cobalt-50}"
    textColor: "{colors.cobalt-700}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "28px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "36px"
---

# Design System: DC Motor Control Lab

## 1. Overview

**Creative North Star: "The lab instrument"**

A calm technical surface for comparing controllers under a classroom projector. Warm-gray canvas, thin structure lines, cobalt where you are and what to click next. Charts carry the argument; chrome stays quiet so temperature and power traces read from the back row.

This is coursework simulation UI, not a consumer LMS and not an ops dashboard. Three controllers share one plant: **MPC** (cobalt), **plain PID** (zinc), **optimized PID** (teal). Copper tags secondary data. Status hues mark constraint outcomes with a word beside every color.

**Key surfaces:** Home briefing → Playground → Step-through → Scorecard.

**Key Characteristics:**

- Quiet neutrals, one cobalt accent (Trace Rule)
- Chart-first density; sections, not floating card grids
- One filled primary button in a region (One Action Rule)
- Controller colors reused in legend, Plotly, and scorecard bars
- A word beside every colored status (feasible / violated)

## 2. Streamlit mapping

Tokens do not load themselves into Streamlit. Map them as follows:

| Token role | Implementation |
| --- | --- |
| Canvas, surface-subtle, text-primary, cobalt | `.streamlit/config.toml` theme |
| Spacing, chips, headers, legend | `src/mpc_core/sim/ui.py` via injected CSS |
| Chart series colors | `src/mpc_core/sim/plotly_charts.py` (same hex as YAML) |
| Fonts | Inject Geist (or Inter) with `system-ui` fallback in `ui.inject_styles()` |

Keep hex values identical across DESIGN.md, `ui.py` constants, and Plotly. Prefer token names in code comments (`colors.cobalt`) over inventing new accents.

## 3. Colors

Warm gray structure, cobalt for intent, controller hues for traces, status hues only for outcome.

### Primary

- **Cobalt** (`#2F6FEB`): filled primary button, MPC traces, focus, active nav mark.
- **Cobalt tint** (`#EEF3FE`): selected preset / chip, soft insight tint.
- **Cobalt ink** (`#1D47A3`): accent text and links.

### Controllers

- **MPC** = cobalt (`#2F6FEB`)
- **PID** (`#71717A`): plain hand-tuned PID traces and bars
- **Optimized PID** (`#0D9488`): SciPy-tuned PID traces and bars

### Secondary

- **Copper** (`#E07A3F`): secondary data tags (e.g. disturbance markers). Not a second action color.

### Tertiary

- **Success, warning, critical** (`#2F9E6A`, `#E0A526`, `#D0312D`): outcome tags only (constraint feasible / warn / violated), each with a word.

### Neutral

- **Canvas** (`#FAFAF9`): page behind the workspace.
- **Surface** (`#FFFFFF`): sections and inputs.
- **Subtle surface** (`#F5F5F4`): rails, table headers, insets.
- **Ink** (`#202020`): primary text.
- **Secondary ink** (`#5F5F5C`) and **muted ink** (`#8A8A86`): support and metadata.
- **Line** (`#E4E4E2`): structure.

**The Trace Rule.** Cobalt is on every screen as a trace: current page sense, focus, a selected control. Solid fill is only the primary button, brand mark, and a small badge.

**The One Action Rule.** At most one filled primary button in a region (e.g. Update simulation).

## 4. Typography

**Display / Body / Label:** Geist (Inter, then system sans). Geist Mono for figures and code when available.

**Character:** One technical sans. Weight and size carry hierarchy. No display face in a button or a label.

### Hierarchy

- **Display** (500, 28px): page title.
- **Title** (600, 20px): section titles.
- **Body** (400, 16px): teaching prose; keep a reading measure near 65–75 characters where prose runs.
- **Label** (600, 11px, uppercase, 0.06em tracking): eyebrows, table headers, legend captions. 11px is the floor, and only labels use it.

**The Weight Rule.** A key figure inside a sentence is weight 600, not a second color.

**Projector note.** Plotly axis and legend text should stay at least ~14px so traces read from the back row.

## 5. Elevation

Depth is tonal. Surfaces step from canvas to white to subtle gray. Sections have no shadow.

### Shadow Vocabulary

- **Menu** (`0 1px 2px rgba(32, 32, 32, 0.04), 0 4px 12px rgba(32, 32, 32, 0.05)`): Streamlit popovers only.

**The Flat Section Rule.** A content block does not lift. If it needs a shadow, it is a menu, not content.

## 6. Components

### Buttons

- **Shape:** 4px corners.
- **Primary:** cobalt fill, inverse text, ~32px tall. One per region.
- **Hover / Focus:** fill deepens to `#2459C9`. Focus is a 2px cobalt ring.
- **Secondary:** white, 1px line, ink text (Reset, Previous).

### Chips / presets

- **Style:** subtle gray fill, 4px corners, ~28px.
- **State:** pressed / active presets use cobalt tint, cobalt-100 line, cobalt ink.

### Sections / containers

- **Corner Style:** 6px for a section, 4px for an inset.
- **Background:** white section on the canvas, or subtle surface for control rails.
- **Shadow Strategy:** none.
- **Border:** 1px line.
- **Internal Padding:** 24px desk; tighter in Streamlit side columns.

### Inputs / fields

- **Style:** ~36px, 1px line, 4px corners, white fill (Streamlit defaults, restyled where CSS allows).
- **Focus:** cobalt line plus the focus ring.

### Navigation

- **Streamlit multipage sidebar:** Home, Playground, Step-through, Scorecard. Active page marked with cobalt tint, not a thick side stripe.
- Do not invent a custom router; polish chrome around Streamlit’s sidebar.

### Charts

- Shared x-axis on dual temperature / power plots.
- Controller colors identical to legend chips.
- Dashed ink for setpoint; muted line for power limits.
- Copper only for optional event markers (disturbance / step time).
- Value labels on scorecard bars when space allows.

### Insight strip / metrics

- Compact row under the main chart: settling and limit hits per controller (no IAE).
- Violations use warning or critical with the words **feasible** or **violated** (never color alone).

## 7. Information architecture

1. **Home** — 30-second professor path: what this lab proves; open Playground next.
2. **Playground** — live compare; presets; chart dominates; controls in expanders.
3. **Step-through** — one MPC horizon at a time; applied move vs prediction fan.
4. **Scorecard** — lead with the power-limits story; colored bars; table secondary.

Each page: eyebrow label → display title → one “look for” sentence → content.

## 8. Do's and Don'ts

### Do:

- **Do** keep cobalt as a trace, and save the solid fill for the one action.
- **Do** put a word next to every success, warning, and critical color.
- **Do** keep the desk dense and chart-first for projection.
- **Do** reuse MPC / PID / Optimized PID colors everywhere they appear.
- **Do** map theme tokens through `config.toml` + `ui.py` + Plotly together.

### Don't:

- **Don't** look like a consumer course site with hero metrics, identical card grids, and the demo buried under marketing.
- **Don't** use dark dashboards with purple gradients, glass panels, and glow.
- **Don't** use a side stripe wider than 1px as decoration.
- **Don't** put a gradient on text, or a glass card behind a chart.
- **Don't** invent new accent hexes that are not in this file.
- **Don't** change simulation or control math for visual effect.
