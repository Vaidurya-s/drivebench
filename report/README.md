# DriveBench technical report

Report on speed regulation of a permanent-magnet DC (PMDC) drive with PID, optimised PID, LQR (with integral action) and MPC.

| Artifact | Path |
| --- | --- |
| LaTeX source | [`drivebench_report.tex`](drivebench_report.tex) |
| Built PDF | [`drivebench_report.pdf`](drivebench_report.pdf) |
| Figures | [`figures/`](figures/) (`fig_*.png`, generated) |
| Metrics used in the PDF | [`metrics_summary.json`](metrics_summary.json) |
| Generated tables and number macros | [`results_table.tex`](results_table.tex), [`numbers.tex`](numbers.tex), [`results_tables.md`](results_tables.md) |
| Shorter Markdown draft | [`report.md`](report.md) (headline numbers typed from the JSON; re-check after a rebuild) |

British spelling. All figures quoted in the PDF text come from `numbers.tex` (generated), all plots from `scripts/report_figures.py`, and the table from `results_table.tex`; nothing is typed by hand.

## Rebuild from the repo root

```bash
pip install -e ".[dev]"
bash scripts/rebuild_academic_report.sh
```

Or step by step:

```bash
python3 scripts/rebuild_report_metrics.py   # runs every scenario for all four controllers (~15 min); writes metrics_summary.json, results/, figures
python3 scripts/rebuild_report_charts.py    # results_table.tex, numbers.tex, results_tables.md
cd report && latexmk -pdf -interaction=nonstopmode drivebench_report.tex
```

To redraw only the figures from a previous run, keep `report/figures/_results.pkl` (git-ignored) and run `python scripts/report_figures.py`.

Dependencies: Python 3.12+, the project `[dev]` extras (matplotlib, pytest, streamlit), and a LaTeX engine with `tikz`, `tcolorbox`, `titlesec`, `fancyhdr`, `enumitem` and `siunitx` (MiKTeX and TeX Live include them).

## Layout

Summary box → drive and its limits (TikZ signal path) → motor model → four control laws (TikZ lanes, pole map, MPC horizon schematic) → fairness table → results (table, IAE ranking heat-map, zoomed transients, current-speed plane, current-limit timeline, robustness dot plot, error against computation) → limitations → reproduction commands.
