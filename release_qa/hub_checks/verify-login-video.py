from playwright.sync_api import expect, sync_playwright

BASE = "https://lab.ferramos.com"
with sync_playwright() as tools:
    for engine in (tools.chromium, tools.webkit):
        browser = engine.launch()
        page = browser.new_page()
        failures = []
        page.on("pageerror", lambda error, failures=failures: failures.append(str(error)))
        page.goto(f"{BASE}/resultados/#T1-01", wait_until="domcontentloaded")
        case = page.locator("#T1-01")
        expect(case.get_by_text("Aprobado", exact=True)).to_be_visible()
        expect(case).to_have_attribute("open", "")
        link = case.get_by_role("link", name="Ver capítulo (0:52)")
        link.click()
        media = page.locator("video")
        expect(media).to_be_visible()
        expect(media.locator("source")).to_have_attribute("src", "/media/recorrido.mp4?v=14")
        page.wait_for_function("""() => {
            const media = document.querySelector('video');
            return media?.readyState >= 2 && Math.abs(media.currentTime - 52) < 1;
        }""", timeout=15000)
        media.evaluate("video => { video.textTracks[0].mode = 'showing'; }")
        page.wait_for_function("""() => {
            const cues = document.querySelector('video').textTracks[0].cues;
            return cues && Array.from(cues).some(cue =>
              cue.startTime === 52 && cue.text.includes('En producción')
            );
        }""", timeout=15000)
        assert not failures, failures
        print(f"{engine.name}: T1-01 approved, 0:52 chapter seeks and Spanish cues loaded")
        browser.close()
