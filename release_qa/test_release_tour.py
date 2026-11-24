"""Team 2 guided onboarding, using the local release build and fresh learners."""
import os
import re
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect

from release_qa import test_final_identity
from src.utils.auth import get_session, inject_session

isolated_stack = test_final_identity.isolated_stack
journey = test_final_identity.journey

GENERAL_STEPS = [
    ("Desde aquí puedes volver a tu dashboard", "/"),
    ("Consulta aquí tus métricas ambientales", "/"),
    ("En la tienda puedes canjear tus puntos", "/store"),
    ("Comparte tus logros y descubre el impacto", "/feed"),
    ("Consulta tu posición y compárate", "/leaderboard"),
    ("Explora el catálogo para conocer las acciones", "/actions"),
]
CAMPAIGN_STEPS = [
    "Las campañas reúnen retos ambientales",
    "Usa estos filtros para encontrar campañas",
    "Abre una tarjeta para consultar los detalles",
    "Aquí puedes revisar tus propuestas",
    "También puedes crear una campaña para tu clan",
]


def screenshot(page, name):
    directory = os.environ.get("TEAM2_TOUR_EVIDENCE")
    if directory:
        page.screenshot(path=Path(directory, name), animations="disabled")


def assert_step(page, label, path):
    expect(page).to_have_url(re.compile(re.escape(path) + "$"))
    expect(page.get_by_text(label, exact=False)).to_be_visible(timeout=12_000)


def replay(page, title):
    page.get_by_role("button", name="Menú de usuario").click()
    page.get_by_role("menuitem", name=title).click()


def first_login(page):
    session = get_session(page.request, f"qa-tour-{uuid4().hex[:9]}@iteso.mx")
    inject_session(page, session, skip_tour=False)
    page.goto("http://localhost:8080/")
    form = page.get_by_role("dialog", name="Completa tu perfil")
    expect(form).to_be_visible()
    career = form.get_by_label("Carrera")
    career.select_option(index=1)
    form.get_by_role("button", name="Continuar", exact=True).click()
    expect(form).to_have_count(0)


def test_t115_skip_reload_and_replay(journey):
    page, _ = journey
    first_login(page)
    assert_step(page, GENERAL_STEPS[0][0], "/")
    page.get_by_role("button", name="Saltar", exact=True).click()
    expect(page.get_by_role("button", name="Saltar", exact=True)).to_have_count(0)
    page.reload()
    expect(page.get_by_role("heading", name="Tu impacto")).to_be_visible()
    assert page.evaluate("Object.entries(localStorage).some(([k, v]) => k.startsWith('greeniteso.guided-tour.') && k.endsWith('.simple') && v === 'skipped')")
    expect(page.get_by_text(GENERAL_STEPS[0][0], exact=False)).to_have_count(0)
    replay(page, "Recorrido general")
    assert_step(page, GENERAL_STEPS[0][0], "/")
    screenshot(page, "T1-15-repetir.png")
    page.get_by_role("button", name="Saltar", exact=True).click()
    replay(page, "Recorrido de campañas")
    assert_step(page, CAMPAIGN_STEPS[0], "/campaigns")
    screenshot(page, "T1-15-campanas.png")


def test_t115_complete_both_tours(journey):
    page, _ = journey
    first_login(page)
    for index, (label, path) in enumerate(GENERAL_STEPS):
        assert_step(page, label, path)
        button = "Finalizar" if index == len(GENERAL_STEPS) - 1 else re.compile("^Siguiente")
        page.get_by_role("button", name=button).click()
    for index, label in enumerate(CAMPAIGN_STEPS):
        if index == len(CAMPAIGN_STEPS) - 2:
            assert_step(page, label, "/campaigns")
            screenshot(page, "T1-15-penultimo.png")
        try:
            assert_step(page, label, "/campaigns")
        except AssertionError:
            if index != len(CAMPAIGN_STEPS) - 1:
                raise
            expect(page.get_by_role("button", name="Crear campaña de clan")).to_be_visible()
            expect(page.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
            assert page.evaluate("!Object.entries(localStorage).some(([k, v]) => k.endsWith('.campaigns') && v === 'completed')")
            screenshot(page, "T1-15-paso-ausente.png")
            raise AssertionError("Campaign tour closed before the fifth step, with no completion state") from None
        button = "Finalizar" if index == len(CAMPAIGN_STEPS) - 1 else re.compile("^Siguiente")
        if index == len(CAMPAIGN_STEPS) - 1:
            screenshot(page, "T1-15-finalizar.png")
        page.get_by_role("button", name=button).click()
    expect(page.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    assert page.evaluate("Object.entries(localStorage).filter(([k, v]) => k.startsWith('greeniteso.guided-tour.') && v === 'completed').length") == 2


def test_t119_staff_and_admin_onboarding(browser):
    import subprocess

    for role in ("STAFF", "ADMIN"):
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        try:
            page = context.new_page()
            email = f"qa-onboarding-{role.lower()}-{uuid4().hex[:8]}@iteso.mx"
            get_session(page.request, email)
            subprocess.run([
                "docker", "exec", "greeniteso-final-qa-backend-1", "/opt/venv/bin/python",
                "manage.py", "assign_user_role", email, role,
            ], capture_output=True, check=True, text=True)
            refreshed = page.request.post(
                "http://localhost:8080/api/v1/auth/login/",
                data={"id_token": f"mock:{email}", "access_token": ""},
            )
            assert refreshed.ok and refreshed.json()["user"]["role"] == role
            inject_session(page, refreshed.json())
            if role == "STAFF":
                page.goto("http://localhost:8080/")
                form = page.get_by_role("dialog", name="Completa tu perfil")
                expect(form).to_be_visible()
                expect(form.get_by_text("Staff ITESO", exact=True)).to_be_attached()
                screenshot(page, "T1-19-staff.png")
            else:
                page.goto("http://localhost:8080/admin/users")
                expect(page.get_by_role("heading", name="Usuarios", exact=True)).to_be_visible()
                expect(page.get_by_role("dialog", name="Completa tu perfil")).to_have_count(0)
        finally:
            context.close()


def test_t120_browser_logout_handoff(journey):
    from release_qa.test_final_identity import learner

    page, _ = journey
    learner(page)
    page.goto("http://localhost:8080/")
    expect(page.get_by_role("heading", name="Tu impacto")).to_be_visible()
    requests = []
    page.on("request", lambda request: requests.append(request.method)
            if request.url.endswith("/api/v1/auth/logout/") else None)
    page.get_by_role("button", name="Menú de usuario").click()
    page.get_by_role("menuitem", name="Cerrar sesión").click()
    expect(page).to_have_url(re.compile("/login$"))
    expect(page.get_by_role("button", name="Iniciar sesión con @iteso.mx")).to_be_visible()
    screenshot(page, "T1-20-salida.png")
    assert "POST" in requests, "The application signed out locally without calling the backend logout endpoint"
