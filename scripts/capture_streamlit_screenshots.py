"""Capture Streamlit multipage UI screenshots for README.

Requires a running app: streamlit run app.py
Regen: python scripts/capture_streamlit_screenshots.py
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE = "http://127.0.0.1:8501"

PAGE_SHOTS = [
    ("", DOCS / "drivebench-overview.png", "System overview"),
    ("bench", DOCS / "drivebench-bench.png", "Experiment Bench"),
    ("lqr_studio", DOCS / "drivebench-lqr-studio.png", "LQR Design Studio"),
    ("mpc_explorer", DOCS / "drivebench-mpc-explorer.png", "MPC Prediction Explorer"),
    ("performance", DOCS / "drivebench-performance.png", "Performance Review"),
    ("plant_model", DOCS / "drivebench-plant-model.png", "Plant Model"),
]

# Click each bench preset; wait for the scenario name in the status bar.
PLAYGROUND_PRESET_SHOTS = [
    ("Speed step", DOCS / "drivebench-bench-speed-step.png", "setpoint step"),
    ("Load step", DOCS / "drivebench-bench-load-step.png", "load step"),
    ("Reverse", DOCS / "drivebench-bench-reverse.png", "reverse"),
]


def _wait_text(page: Page, text: str, timeout: float = 90_000) -> None:
    page.get_by_text(text, exact=False).first.wait_for(timeout=timeout)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")

        # Page-level shots: fresh context each time.
        for path, out, wait_text in PAGE_SHOTS:
            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            url = f"{BASE}/{path}" if path else BASE
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            _wait_text(page, wait_text)
            page.wait_for_timeout(12000)
            page.screenshot(path=str(out), full_page=True)
            print(f"Wrote {out.name}")
            context.close()

        # Preset shots: one bench session, click through presets.
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        page.goto(f"{BASE}/bench", wait_until="domcontentloaded", timeout=120_000)
        _wait_text(page, "Experiment Bench")
        page.wait_for_timeout(2500)

        for label, out, marker in PLAYGROUND_PRESET_SHOTS:
            page.get_by_role("button", name=label, exact=True).first.click()
            _wait_text(page, marker)
            page.wait_for_timeout(12000)
            page.screenshot(path=str(out), full_page=True)
            print(f"Wrote {out.name} ({label})")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
