"""Verify the deployed signed-out user journeys without changing app data."""
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://greeniteso.mocking.so"
EVIDENCE = Path("reporting/final-peer-qa/production")
ROUTES = ("/profile", "/clans", "/notifications")
ENDPOINTS = ("/api/v1/profile/me/", "/api/v1/clans/", "/api/v1/notifications/")

EVIDENCE.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browsers = ((p.chromium, 1440, 900), (p.webkit, 390, 844))
    for engine, width, height in browsers:
        browser = engine.launch()
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        for protected in ROUTES:
            page.goto(BASE + protected, wait_until="domcontentloaded")
            expect(page).to_have_url(BASE + "/login")
            expect(page.get_by_role("button", name="Iniciar sesión con @iteso.mx")).to_be_visible()
            print(f"{engine.name} {width}px: {protected} → /login")
        page.screenshot(path=EVIDENCE / f"T1-16-prod-{engine.name}.png")
        for endpoint in ENDPOINTS:
            response = context.request.get(BASE + endpoint)
            assert response.status == 401, (endpoint, response.status)
            print(f"{engine.name} {width}px: GET {endpoint} → HTTP 401")
        assert not errors, errors
        browser.close()
