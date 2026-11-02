# Academic report (Industrial Control)

Course write-up for the offset-free MPC vs PID lab on the PMDC motor drive.

| Artifact | Path |
| --- | --- |
| LaTeX source | [`main.tex`](main.tex) |
| Built PDF | [`report.pdf`](report.pdf) |
| Figures | [`figures/`](figures/) |
| Metrics used in the PDF | [`metrics_summary.json`](metrics_summary.json) |
| Generated tables | [`results_table.tex`](results_table.tex) (`\input` by `main.tex`), [`results_tables.md`](results_tables.md) |
| Shorter Markdown draft | [`report.md`](report.md) (headline numbers are typed from the JSON; rebuild metrics, then check them) |

British spelling. Prefer numbers from `metrics_summary.json` after a metrics rebuild.

## What the numbers mean

- **Batch scenarios** in `metrics_summary.json → scenarios`: the ten motor scenarios plus the opposite mismatch corner (`model_mismatch_low`). Each has `mpc`, `pid` and `optimized_pid` metric sets (the full list is `SCORECARD_COLUMNS` in `sim/metrics.py`).
- **Optimised PID** uses the frozen gains in `optimized_pid_gains` (tuned once on `speed_tracking`, also stored in `data/ui/optimized_pid.json`). Nothing is retuned per scenario.
- **`robustness_model_mismatch`** compares MPC, the frozen optimised PID and an optimised PID retuned on the mismatched plant.
- **MPC / motor / drive settings** are stored under `mpc`, `motor`, `drive`, `timing`.
- Simulation PNGs under `figures/<scenario>.png` are produced by the metrics script. Architecture and bar charts (`architecture.png`, `iae_bars.png`, `current_limit_bars.png`, `robustness_bars.png`) and the generated tables come from the charts script. The opening MPC loop figure is `assets/mpc-infographic.png`.

## Rebuild from the repo root

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full pipeline: metrics → charts and tables → PDF
bash scripts/rebuild_academic_report.sh
```

Or step by step:

```bash
python3 scripts/rebuild_report_metrics.py   # report/metrics_summary.json + figures/<scenario>.png
python3 scripts/rebuild_report_charts.py    # architecture, bar charts, results tables
cd report
latexmk -pdf -interaction=nonstopmode main.tex   # preferred
# else: pdflatex main.tex && pdflatex main.tex
# else: tectonic main.tex
cp -f main.pdf report.pdf
```

Dependencies: Python 3.12+, project `[dev]` extras (matplotlib, pytest, streamlit), and a LaTeX engine (`latexmk`, `pdflatex`, or `tectonic`; `multirow` is required). CasADi and SciPy come from the core install.

A full metrics rebuild takes a few minutes. Do not hand-edit numbers in `main.tex` tables; change the sim, rebuild metrics and charts (which regenerates `results_table.tex`). The prose in `main.tex` and `report.md` quotes a few numbers: re-check them against the JSON after any rebuild.

## Layout of `main.tex`

Abstract → MPC loop infographic → introduction → models (plant, prediction model and observer, drive, measurement) → controllers → system design → experimental setup → results (generated table, IAE bars, traces, drive limits, noise and robustness) → discussion and limitations → conclusion → references.
