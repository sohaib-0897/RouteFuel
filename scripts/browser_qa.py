"""Optional map browser check. Requires separately installed playwright + Chromium."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    plan = json.loads(Path("artifacts/dallas-la-cached.json").read_text(encoding="utf-8"))
    failures = []
    with sync_playwright() as browser_driver:
        browser = browser_driver.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: failures.append(str(error)))
        response = page.goto("http://127.0.0.1:8000" + plan["map_url"])
        assert response.status == 200
        page.wait_for_selector(".leaflet-marker-icon")
        assert page.locator(".leaflet-marker-icon").count() == len(plan["fuel_stops"]) + 2
        assert page.locator("path.leaflet-interactive").count() >= 1
        page.locator(".stop").first.click()
        page.wait_for_selector(".leaflet-popup-content")
        assert "Buy" in page.locator(".leaflet-popup-content").inner_text()
        assert not failures, failures
        page.screenshot(path="artifacts/route-map.png", full_page=True)
        print(
            json.dumps(
                {
                    "map_http_status": response.status,
                    "markers": len(plan["fuel_stops"]) + 2,
                    "javascript_errors": failures,
                }
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
