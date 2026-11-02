"""Theme tokens, contrast, diagrams, charts and the absence of heater wording."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mpc_core.sim import theme as T
from mpc_core.sim.diagrams import drive_architecture, four_controller_architecture, lqr_design_process
from mpc_core.sim.plotly_charts import QUANTITIES, quantity_figure
from mpc_core.sim.playground import PlaygroundParams, build_playground_scenario, run_bench
from mpc_core.sim.config import default_demo_config
from mpc_core.sim.ui import css

ROOT = Path(__file__).resolve().parents[1]


def _lum(hex_: str) -> float:
    c = [int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("fg", [T.TEXT_PRIMARY, T.TEXT_SECONDARY, T.TEXT_MUTED, T.ACCENT, T.SUCCESS, T.WARNING, T.CRITICAL])
@pytest.mark.parametrize("bg", [T.CANVAS, T.PANEL])
def test_text_contrast_aa(fg: str, bg: str) -> None:
    assert contrast(fg, bg) >= 4.5


@pytest.mark.parametrize("cid", list(T.CONTROLLER_COLORS))
def test_controller_lines_contrast(cid: str) -> None:
    assert contrast(T.CONTROLLER_COLORS[cid], T.CANVAS) >= 3.0


def test_controllers_distinguishable_without_colour() -> None:
    styles = {(T.CONTROLLER_DASH[c], T.CONTROLLER_WIDTH[c]) for c in T.CONTROLLER_COLORS}
    assert len(styles) == 4


def test_css_uses_plex_with_fallbacks_and_no_gradients() -> None:
    s = css()
    assert "IBM Plex Sans" in s and "IBM Plex Mono" in s and "system-ui" in s and "monospace" in s
    assert "gradient" not in s and "blur(" not in s and "glow" not in s


def test_diagrams_are_self_contained_svg() -> None:
    for svg in (drive_architecture(), four_controller_architecture(), lqr_design_process()):
        assert svg.startswith("<svg") and "</svg>" in svg and "http://www.w3.org" in svg
        assert "<image" not in svg and "href=\"http" not in svg


def test_four_controller_diagram_names_all_controllers() -> None:
    svg = four_controller_architecture()
    for name in ("PID", "Optimised PID", "LQR", "MPC"):
        assert name in svg


def test_quantity_figures_have_four_controllers_and_units() -> None:
    p = PlaygroundParams(duration_s=3.0, ref_step_at_s=1.0)
    runs = run_bench(build_playground_scenario(p), cfg=default_demo_config())
    for q in QUANTITIES:
        fig = quantity_figure(runs.runs, q)
        names = {t.name for t in fig.data}
        for label in T.CONTROLLER_LABELS.values():
            assert label in names, (q, label)
        titles = [fig.layout.yaxis.title.text] + [
            getattr(fig.layout, f"yaxis{i}").title.text for i in (2,) if f"yaxis{i}" in fig.layout
        ]
        assert any("[" in (t or "") for t in titles)


HEATER = re.compile(r"(?i:heater|induction|furnace|ibh)|°C|kW")


def test_no_heater_wording_in_app_sources() -> None:
    files = [ROOT / "app.py", *sorted((ROOT / "ui_pages").glob("*.py"))]
    files += [ROOT / "src/mpc_core/sim" / n for n in ("copy_text.py", "ui.py", "ui_state.py", "diagrams.py", "plotly_charts.py", "theme.py")]
    for f in files:
        assert not HEATER.search(f.read_text(encoding="utf-8")), f
