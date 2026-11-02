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
    ("", DOCS / "streamlit-overview.png", "Industrial DC Motor Control Lab"),
    ("playground", DOCS / "streamlit-playground.png", "Playground"),
    ("step_through", DOCS / "streamlit-step-through.png", "Step-through"),
    ("scorecard", DOCS / "streamlit-scorecard.png", "Scorecard"),
]

# Click each preset button; wait for the Active caption to show the case.
PLAYGROUND_PRESET_SHOTS = [
    ("Speed step", DOCS / "streamlit-playground-speed-step.png", "1000→2000 RPM"),
    ("Load step", DOCS / "streamlit-playground-load-step.png", "→ 0.100"),
    ("Load removal", DOCS / "streamlit-playground-load-removal.png", "→ 0.050"),
    ("Periodic load", DOCS / "streamlit-playground-periodic-load.png", "sin(0.5 Hz)"),
    ("Noisy encoder", DOCS / "streamlit-playground-noisy-encoder.png", "encoder σ=15"),
    ("Tight limits", DOCS / "streamlit-playground-tight-limits.png", "14 V / 4.0 A"),
    ("Mismatch", DOCS / "streamlit-playground-mismatch.png", "mismatch on"),
    ("Reverse", DOCS / "streamlit-playground-reverse.png", "1000→-1000 RPM"),
]


def _wait_text(page: Page, text: str, timeout: float = 90_000) -> None:
    page.get_by_text(text, exact=False).first.wait_for(timeout=timeout)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Page-level shots: fresh context each time.
        for path, out, wait_text in PAGE_SHOTS:
            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            url = f"{BASE}/{path}" if path else BASE
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            _wait_text(page, wait_text)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(out), full_page=True)
            print(f"Wrote {out.name}")
            context.close()

        # Preset shots: one playground session, click through presets.
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        page.goto(f"{BASE}/playground", wait_until="domcontentloaded", timeout=120_000)
        _wait_text(page, "Playground")
        page.wait_for_timeout(2500)

        for label, out, marker in PLAYGROUND_PRESET_SHOTS:
            page.get_by_role("button", name=label, exact=True).first.click()
            _wait_text(page, marker)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(out), full_page=True)
            print(f"Wrote {out.name} ({label})")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
