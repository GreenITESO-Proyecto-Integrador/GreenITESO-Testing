import sys

from playwright.sync_api import expect, sync_playwright

base = sys.argv[1].rstrip("/")
with sync_playwright() as tools:
    for engine, width, height in ((tools.chromium, 1440, 950), (tools.webkit, 390, 844)):
        browser = engine.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.goto(base + "/resultados/#T1-01", wait_until="domcontentloaded")
        first = page.locator("#T1-01")
        expect(first).to_have_attribute("open", "")
        pages = page.locator(".case-card")
        expect(pages).to_have_count(30)
        first.locator(".case-evidence").scroll_into_view_if_needed()
        first_image = first.locator(".evidence-gallery img").first
        expect(first_image).to_have_attribute("alt", "Sesión activa tras recargar en producción")
        expect(first.locator(".evidence-gallery a").first).to_have_attribute("href", base + "/evidencia/T1-01/recarga-produccion.png")
        expect(page.locator("#T1-09 .status-tag")).to_have_text("Fallido")
        expect(page.locator("#T1-12 .status-tag")).to_have_text("Fallido")
        expect(page.locator("#T1-13 .status-tag")).to_have_text("Aprobado")
        tour_case = page.locator("#T1-15")
        expect(tour_case.locator(".status-tag")).to_have_text("Parcial")
        expect(tour_case).to_contain_text("Con cero o una campaña activa")
        expect(tour_case.locator("a[href$='/tour-retest/produccion.txt']")).to_have_count(1)
        expect(tour_case.locator(".case-links a[href^='/video/#t=']")).to_have_count(1)
        for case_id, status in (("T1-09", "Fallido"), ("T1-12", "Fallido"),
                                ("T1-18", "Parcial"), ("T1-20", "Fallido")):
            case = page.locator(f"#{case_id}")
            expect(case.locator(".status-tag")).to_have_text(status)
            expect(case.locator("a[href$='-production.txt']")).to_have_count(1)
            expect(case.locator("a[href$='-local.txt']")).to_have_count(1)
        page.locator("#status").select_option("FAIL")
        expect(page.locator(".case-card:visible")).to_have_count(3)
        page.locator("#reset").click()
        for card in pages.all():
            card.evaluate("(item)=>{item.open=true}")
        screenshots = page.locator(".evidence-gallery img")
        assert screenshots.count() == 93, screenshots.count()
        for start in range(0, screenshots.count(), 8):
            bounds = [start, start + 8]
            screenshots.evaluate_all("""(images, [start, end]) => images.slice(start, end)
                .forEach(image => { image.loading = 'eager'; })
            """, bounds)
            page.wait_for_function("""([start, end]) => [...document.querySelectorAll('.evidence-gallery img')]
                .slice(start, end).every(image => image.complete && image.naturalWidth > 0 && image.alt.length > 0)
            """, arg=bounds, timeout=30000)
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        first.locator(".case-evidence").scroll_into_view_if_needed()
        page.goto(base + "/video/", wait_until="domcontentloaded")
        transcript = page.locator("#transcripcion")
        expect(transcript.locator(".transcript-chapter")).to_have_count(23)
        expect(transcript.get_by_text("Inicio institucional en producción", exact=True)).to_be_visible()
        denial = transcript.locator(".transcript-chapter").filter(has_text="Cuenta personal rechazada en producción")
        expect(denial).to_contain_text("Microsoft rechazó el ingreso")
        expect(transcript).to_contain_text("la aplicación borró la membresía")
        expect(transcript).to_contain_text("el recorrido de campañas se cerró antes del paso final")
        expect(page.locator(".chapter-cases a[href='/resultados/#T1-16']")).to_have_count(1)
        expect(page.locator(".chapter-cases a[href='/resultados/#T1-30']")).to_have_count(1)
        for case_id in ("T1-09", "T1-12", "T1-18", "T1-20"):
            expect(page.locator(f".chapter-cases a[href='/resultados/#{case_id}']")).to_have_count(1)
        expect(transcript).to_contain_text("El menú no llamó al cierre del servidor")
        expect(transcript).to_contain_text("La notificación de ingreso llegó sin recargar.")
        expect(page.get_by_role("link", name="Leer la transcripción")).to_have_attribute("href", "#transcripcion")
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        if base.startswith("https:"):
            transcript.locator(".transcript-chapter").nth(2).get_by_role("link").click()
            page.wait_for_function("""() => {
                const media = document.querySelector('video');
                return media?.readyState >= 2 && Math.abs(media.currentTime - 52) < 1;
            }""", timeout=15000)
            page.locator('video').evaluate("media => { media.textTracks[0].mode = 'showing'; }")
            page.wait_for_function("document.querySelector('track').readyState === 2", timeout=15000)
            denial.get_by_role("link").click()
            page.wait_for_function("""() => {
                const media = document.querySelector('video');
                return Math.abs(media.currentTime - 69) < 1;
            }""", timeout=15000)
            assert page.locator('video').evaluate("v => Array.from(v.textTracks[0].cues).some(c => c.text.includes('Microsoft rechazó'))")
        assert not errors, errors
        print(f"{engine.name} {width}px: 93 screenshots decoded, 30 cases, 23 transcript chapters")
        comparison = transcript.locator(".transcript-chapter").filter(has_text="Recorrido de campañas en local y producción")
        expect(comparison).to_contain_text("Con cero o una campaña")
        expect(comparison).to_contain_text("tres fallidos y dos parciales")
        if base.startswith("https:"):
            comparison.get_by_role("link").click()
            page.wait_for_function("""() => {
                const media = document.querySelector('video');
                return media?.readyState >= 2 && Math.abs(media.currentTime - 285) < 1;
            }""", timeout=15000)
        page.goto(base + "/resultados/?estado=FAIL", wait_until="domcontentloaded")
        expect(page.locator("#status")).to_have_value("FAIL")
        expect(page.locator(".case-card:visible")).to_have_count(3)
        browser.close()
