"""Headless screenshots of the school ranking list.

Responsibility: start `python -m http.server` on web/, load the page in
headless Chrome via Playwright, and save the Grade 6 ranking in English and
the Grade 9 ranking in Chinese into screenshots/. Raises if the server or
browser cannot start. Does not capture the map.

Run:  .venv/bin/python scripts/screenshot.py
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765


def main() -> int:
    """CLI entry; exit 0 when both screenshots were written."""
    parser = argparse.ArgumentParser()
    parser.parse_args()
    out_dir = ROOT / "screenshots"
    out_dir.mkdir(exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "-d", str(ROOT / "web")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.0)
        if server.poll() is not None:
            raise RuntimeError(f"http.server exited early (port {PORT} busy?)")
        with sync_playwright() as pw:
            # Use the system Chrome when present so no browser download is needed.
            try:
                browser = pw.chromium.launch(channel="chrome")
            except Exception:  # noqa: BLE001
                browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 950})
            page.goto(f"http://localhost:{PORT}/", wait_until="networkidle")
            page.wait_for_selector("body[data-ready='1']", timeout=30000)
            page.wait_for_selector("#rankTable tbody tr")
            page.screenshot(path=str(out_dir / "a_school_rank_pat6_en.png"))

            page.click("#lang")
            page.select_option("#gradeConfig", "6-9")
            page.wait_for_timeout(300)
            page.screenshot(path=str(out_dir / "b_school_rank_pat9_zh.png"))
            browser.close()
    finally:
        server.terminate()
    print("wrote", *sorted(p.name for p in out_dir.glob("*.png")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
