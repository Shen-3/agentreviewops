from __future__ import annotations
from pathlib import Path

from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_URL = "http://127.0.0.1:5173"
SCREENSHOT_PATH = Path("/private/tmp/agentreview-dashboard.png")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(DASHBOARD_URL)
        page.get_by_text("AI pull request review queue").wait_for()
        page.get_by_text("Analysis runs").wait_for()
        page.get_by_text("API unavailable. Showing demo analysis data.").wait_for()
        page.locator(".analysis-row", has_text="platform/checkout-api").first.wait_for()
        page.get_by_role("heading", name="Findings").wait_for()
        page.get_by_role("heading", name="Report preview").wait_for()
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        browser.close()

    print(f"Dashboard screenshot written to {SCREENSHOT_PATH}")


if __name__ == "__main__":
    main()
