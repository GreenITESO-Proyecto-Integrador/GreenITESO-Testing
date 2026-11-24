"""Verify the per-case rerun totals and the production prerequisites."""
import sys

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1].rstrip("/")
with sync_playwright() as playwright:
    for engine, width in ((playwright.chromium, 1440), (playwright.webkit, 390)):
        browser = engine.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(base + "/resultados/#T1-09", wait_until="domcontentloaded")
        summary = page.locator("#multi-account-summary")
        expect(summary).to_contain_text("24 ejecuciones, 22 aprobadas y 2 fallidas")
        expect(page.locator("#T1-09 .retest-table td[data-status='FAIL']:visible")).to_have_count(2)
        expect(page.locator(".retest-table tbody tr")).to_have_count(12)
        expect(page.locator(".retest-table td[data-status='PASS']")).to_have_count(22)
        expect(page.locator(".retest-table td[data-status='FAIL']")).to_have_count(2)
        expect(page.locator(".case-details dt").filter(has_text="Producción · pendiente con otra cuenta ITESO")).to_have_count(12)
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        if base.startswith("https:"):
            chapter = summary.get_by_role("link", name="Ver reejecución en el video")
            expect(chapter).to_have_attribute("href", "/video/#t=496")
            chapter.click()
            expect(page.locator("video")).to_be_visible()
            page.wait_for_function("""() => {
              const player = document.querySelector('video');
              return player?.readyState >= 2 && Math.abs(player.currentTime - 496) < 1;
            }""", timeout=20000)
            expect(page.locator("#transcripcion")).to_contain_text("Hubo 22 resultados aprobados y dos fallidos.")
        print(f"{engine.name}: 24 rerun results, 12 production notes, and new chapter link")
        browser.close()
