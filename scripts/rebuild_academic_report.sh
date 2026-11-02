#!/usr/bin/env bash
# Rebuild metrics, figures, tables and the LaTeX PDF for report/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/rebuild_report_metrics.py   # metrics_summary.json, results/, report/figures/
python3 scripts/rebuild_report_charts.py    # results_table.tex, numbers.tex, results_tables.md

cd report
if command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -interaction=nonstopmode drivebench_report.tex
elif command -v pdflatex >/dev/null 2>&1; then
  pdflatex -interaction=nonstopmode drivebench_report.tex
  pdflatex -interaction=nonstopmode drivebench_report.tex
  pdflatex -interaction=nonstopmode drivebench_report.tex
elif command -v tectonic >/dev/null 2>&1; then
  tectonic drivebench_report.tex
else
  echo "No LaTeX engine found (latexmk/pdflatex/tectonic). PDF not rebuilt." >&2
  exit 1
fi
echo "wrote report/drivebench_report.pdf"
