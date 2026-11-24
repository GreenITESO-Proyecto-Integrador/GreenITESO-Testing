"""Verify the new production images and chapter links within their cases."""
import json
import sys
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1].rstrip("/")
with urlopen(base + "/assets/results.json", timeout=20) as response:
    manifest = json.load(response)
new_cases = json.loads(Path(__file__).with_name("production-captures.json").read_text())
chapters = {case["id"]: case["chapter"] for case in manifest["cases"]}

with sync_playwright() as playwright:
    for engine, width in ((playwright.chromium, 1440), (playwright.webkit, 390)):
        browser = engine.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(base + "/resultados/#T1-07", wait_until="domcontentloaded")
        expect(page.locator("#T1-07")).to_have_attribute("open", "")
        expect(page.locator(".production-evidence")).to_have_count(0)
        for case_id, result in new_cases.items():
            card = page.locator(f"#{case_id}")
            if not card.evaluate("region => region.open"):
                card.locator(":scope > summary").click()
            for name, caption in result["captures"]:
                image = card.locator(f'img[src$="/live-production/{name}.png"]')
                expect(image).to_have_attribute("alt", "Producción · " + caption)
                page.wait_for_function("(image) => image.complete && image.naturalWidth > 0",
                                       arg=image.element_handle(), timeout=15000)
            expect(card.locator(f'a[href="/video/#t={chapters[case_id]}"]')).to_have_count(1)
            card.locator(":scope > summary").click()
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        tour = page.locator("#T1-15")
        tour.locator(":scope > summary").click()
        tour.locator(".evidence-record summary").click()
        expect(tour.locator(".evidence-record")).to_contain_text("este botón")
        if base.startswith("https:"):
            tour.locator(f'a[href="/video/#t={chapters["T1-15"]}"]').click()
            expect(page.locator("video")).to_be_visible()
            page.wait_for_function("""time => {
              const media = document.querySelector('video');
              return media?.readyState >= 2 && Math.abs(media.currentTime-time) < 1;
            }""", arg=chapters["T1-15"], timeout=20000)
            expect(page.locator("#transcripcion")).to_contain_text("Guardianes del Ahuehuete")
        print(f"{engine.name}: 13 production case cards, all captures, in-case records and video links")
        browser.close()
