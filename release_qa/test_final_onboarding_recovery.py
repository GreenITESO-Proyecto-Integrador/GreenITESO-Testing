"""Check required onboarding and recovery with disposable accounts and injected errors."""
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect

from release_qa import test_final_identity
from src.utils.auth import get_session, inject_session

isolated_stack = test_final_identity.isolated_stack
journey = test_final_identity.journey


BASE = "http://localhost:8080"
ONBOARDING = "/api/v1/clans/institutional-clan/"


def capture(page, name):
    if output := os.environ.get("TEAM2_RECOVERY_EVIDENCE"):
        page.screenshot(path=Path(output, f"{page.context.browser.browser_type.name}-{name}.png"),
                        animations="disabled")


def test_t121_recovery_after_catalog_and_save_error(journey):
    page, _ = journey
    nickname = f"qa-recuperacion-{uuid4().hex[:6]}"
    session = get_session(page.request, f"{nickname}@iteso.mx")
    inject_session(page, session)
    headers = {"Authorization": f"Bearer {session['access']}"}
    failures = []

    def temporary_failure(route):
        if len(failures) == 1 and route.request.method == "POST":
            failures.append("save")
        elif not failures and route.request.method == "GET" and route.request.url.endswith("/careers/"):
            failures.append("catalog")
        else:
            return route.continue_()
        route.fulfill(status=503, json={"detail": "No disponible por el momento."})

    page.route(f"**{ONBOARDING}careers/", temporary_failure)
    page.route(f"**{ONBOARDING}", temporary_failure)
    page.goto(f"{BASE}/profile")

    form = page.get_by_role("dialog", name="Completa tu perfil")
    career = form.get_by_label("Carrera")
    submit = form.get_by_role("button", name="Continuar", exact=True)
    expect(form.get_by_role("alert")).to_contain_text("No se pudo cargar la lista de carreras")
    expect(career).to_be_disabled()
    expect(submit).to_be_disabled()
    page.keyboard.press("Escape")
    expect(form).to_be_visible()
    capture(page, "catalogo-no-disponible")

    retry = form.get_by_role("button", name="Reintentar")
    retry.focus()
    page.keyboard.press("Enter")
    expect(career).to_be_enabled()
    expected_career = career.locator("option").nth(1).get_attribute("value")
    assert expected_career
    career.select_option(expected_career)
    form.get_by_label("Nickname (opcional)").fill(nickname)
    form.get_by_role("checkbox", name="Perfil privado").check()
    with page.expect_response(lambda response: response.url.endswith(ONBOARDING)
                              and response.request.method == "POST") as rejected:
        submit.press("Enter")
    assert rejected.value.status == 503
    expect(form.get_by_role("alert")).to_be_visible()
    expect(form).to_be_visible()
    expect(career).to_have_value(expected_career)
    expect(form.get_by_label("Nickname (opcional)")).to_have_value(nickname)
    expect(form.get_by_role("checkbox", name="Perfil privado")).to_be_checked()
    before = page.request.get(BASE + ONBOARDING, headers=headers)
    assert before.ok and before.json()["onboarding_completed_at"] is None
    capture(page, "datos-conservados")

    with page.expect_response(lambda response: response.url.endswith(ONBOARDING)
                              and response.request.method == "POST") as saved:
        submit.press("Enter")
    assert saved.value.status == 200 and failures == ["catalog", "save"]
    expect(form).to_have_count(0)
    expect(page.get_by_text(expected_career, exact=True).first).to_be_visible()
    capture(page, "adscripcion-recuperada")
    onboarding = page.request.get(BASE + ONBOARDING, headers=headers)
    assert onboarding.ok and onboarding.json()["institutional_clan"]["name"] == expected_career
    profile = page.request.get(f"{BASE}/api/v1/profile/me/", headers=headers)
    assert profile.ok and profile.json()["visibility"] == "PRIVATE" and profile.json()["nickname"] == nickname


def test_t122_unrecoverable_session_ends_cleanly(journey):
    from release_qa.test_final_identity import learner

    page, _ = journey
    learner(page)
    page.goto(f"{BASE}/profile")
    expect(page.get_by_text("Perfil Ecológico", exact=True)).to_be_visible()
    refreshes = []

    def expired(route):
        refreshes.append(route.request.method)
        route.fulfill(status=401, json={"detail": "La sesión de prueba expiró."})

    page.route("**/api/v1/auth/refresh/", expired)
    page.evaluate("sessionStorage.removeItem('greeniteso.access_token')")
    page.reload()
    expect(page.get_by_role("button", name="Iniciar sesión con @iteso.mx")).to_be_visible()
    assert page.url == f"{BASE}/login"
    assert refreshes == ["POST"]
    assert page.evaluate("""() => ['greeniteso.access_token', 'greeniteso.refresh_token']
        .every(key => sessionStorage.getItem(key) === null)""")
    page.goto(f"{BASE}/clans")
    expect(page.get_by_role("button", name="Iniciar sesión con @iteso.mx")).to_be_visible()
    assert page.url == f"{BASE}/login" and refreshes == ["POST"]
    capture(page, "sesion-expirada")
