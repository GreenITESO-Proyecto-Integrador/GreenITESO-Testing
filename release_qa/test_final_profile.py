"""GreenITESO Team 2 functional browser checks on the disposable local stack."""

import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from release_qa.test_team2_acceptance import api, credit, db_read_or_seed, lab_action
from src.configs import environment
from src.utils.auth import inject_session

BASE = "http://localhost:8080"
LOGIN = "/api/v1/auth/login/"
PROFILE = "/api/v1/profile/me/"
CAREER = "/api/v1/clans/institutional-clan/"
OUT = Path(os.environ.get("FINAL_PROFILE_EVIDENCE", "reporting/final-peer-qa/profile"))
pytestmark = pytest.mark.full


@pytest.fixture(autouse=True)
def isolated_stack():
    assert environment.BASE_URL == environment.API_BASE_URL == BASE
    assert environment.AUTH_MODE == "mock" and not environment.E2E_CLEANUP


def login_mock(page, email):
    return page.request.post(LOGIN, data={"id_token": f"mock:{email}", "access_token": ""})


@contextmanager
def actor(browser, label, *, email=None, onboard=True, role=None):
    output = OUT / browser.browser_type.name
    output.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        base_url=BASE,
        viewport={"width": 1440, "height": 900},
        record_video_dir=output / "video",
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.set_default_timeout(10_000)
    video = page.video
    try:
        email = email or f"qa-perfil-{uuid4().hex[:10]}@iteso.mx"
        response = login_mock(page, email)
        assert response.ok, f"Identidad sintética: HTTP {response.status}"
        if role:
            subprocess.run(
                [
                    "docker", "exec", "greeniteso-final-qa-backend-1", "/opt/venv/bin/python",
                    "manage.py", "assign_user_role", email, role,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            response = login_mock(page, email)
            assert response.ok and response.json()["user"]["role"] == role
        session = response.json()
        if onboard:
            headers = {"Authorization": f"Bearer {session['access']}"}
            catalogue = page.request.get(CAREER + "careers/", headers=headers)
            assert catalogue.ok
            selected = catalogue.json()["careers"][0]
            saved = page.request.post(
                CAREER, headers=headers, data={"career": selected, "nickname": email.split("@")[0]}
            )
            assert saved.ok, f"Preparación de cuenta sintética: HTTP {saved.status}"
        inject_session(page, session)
        yield page, email, session
    finally:
        context.close()
        if video:
            video.path().replace(output / "video" / f"{label}.webm")


def capture(page, name):
    output = OUT / page.context.browser.browser_type.name
    page.screenshot(path=output / f"{name}.png", animations="disabled")


def link_click(page, control, path, http_status, *, with_body=False):
    with page.expect_response(
        lambda response: urlsplit(response.url).path == path and response.request.method == "POST"
    ) as exchange:
        control.click()
    assert exchange.value.status == http_status, (path, exchange.value.status)
    return exchange.value.json() if with_body else None


def note(browser, name, lines):
    (OUT / browser.browser_type.name / f"{name}.txt").write_text("\n".join(lines) + "\n")


def nickname_dialog(page, name):
    page.get_by_role("button", name="Cambiar nickname", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Nuevo nickname").fill(name)
    return dialog


def test_t121_nickname_free_insufficient_and_paid_persist(browser):
    suffix = uuid4().hex[:6]
    with actor(browser, "T1-21-nickname") as (page, _, _):
        page.goto("/profile")
        section = page.get_by_role("region", name="Cuenta")
        expect(section.get_by_text("Tu primer cambio es gratis.", exact=True)).to_be_visible()
        dialog = nickname_dialog(page, f"Eco inicial {suffix}")
        first = link_click(page, dialog.get_by_role("button", name="Guardar", exact=True), PROFILE + "nickname/", 200, with_body=True)
        assert (first["points_spent"], first["available_points"], first["next_change_cost"]) == (0, 0, 50)
        expect(dialog).to_be_hidden()
        dialog = nickname_dialog(page, f"Eco final {suffix}")
        expect(dialog.get_by_text("No te alcanzan los puntos para cambiarlo todavía.")).to_be_visible()
        expect(dialog.get_by_role("button", name=re.compile("Pagar 50 puntos"))).to_be_disabled()
        capture(page, "T1-21-saldo-insuficiente")
        dialog.get_by_role("button", name="Cancelar", exact=True).click()
        action = lab_action(suffix)
        for _ in range(4):
            credit(page, action)
        page.reload()
        expect(section.get_by_text(f"Eco inicial {suffix}", exact=True)).to_be_visible()
        dialog = nickname_dialog(page, f"Eco final {suffix}")
        expect(dialog.get_by_text("Cambiarlo cuesta 50 puntos. Tienes 68.", exact=True)).to_be_visible()
        capture(page, "T1-21-confirmar-cobro")
        paid = link_click(
            page, dialog.get_by_role("button", name="Pagar 50 puntos y guardar"), PROFILE + "nickname/", 200, with_body=True
        )
        assert (paid["points_spent"], paid["available_points"]) == (50, 18)
        expect(dialog).to_be_hidden()
        page.reload()
        expect(section.get_by_text(f"Eco final {suffix}", exact=True)).to_be_visible()
        saved = api(page, PROFILE)
        assert (saved["nickname"], saved["available_points"], saved["total_points"]) == (f"Eco final {suffix}", 18, 68)
        capture(page, "T1-21-persistencia")
        note(browser, "T1-21-prueba", [
            "Primer cambio por interfaz: HTTP 200, costo 0, siguiente costo 50.",
            "Con 0 puntos, el segundo cambio estuvo deshabilitado.",
            "Con 68 puntos disponibles, el segundo cambio cobró 50.",
            "Después de recargar, persistieron el nickname, 18 puntos disponibles y 68 puntos acumulados.",
        ])


def test_t122_self_deactivation_and_synthetic_reactivation(browser):
    suffix = uuid4().hex[:6]
    with actor(browser, "T1-22-desactivacion") as (page, email, original):
        page.goto("/profile")
        action = lab_action(suffix)
        credit(page, action)
        # Reopen the profile after setup so live badge celebrations cannot cover the account controls.
        page.reload()
        assert api(page, PROFILE)["total_points"] == 17
        page.get_by_role("button", name="Desactivar cuenta", exact=True).click()
        dialog = page.get_by_role("dialog", name="Desactivar cuenta")
        submit = dialog.get_by_role("button", name="Desactivar mi cuenta", exact=True)
        expect(submit).to_be_disabled()
        dialog.get_by_role("checkbox").check()
        expect(submit).to_be_enabled()
        capture(page, "T1-22-confirmacion")
        link_click(page, submit, PROFILE + "deactivate/", 204)
        expect(page).to_have_url(re.compile("/login$"))
        expect(page.get_by_role("heading", name="Inicia sesión")).to_be_visible()
        page.goto("/profile")
        expect(page).to_have_url(re.compile("/login$"))
        capture(page, "T1-22-sesion-cerrada")
    with actor(browser, "T1-22-reactivacion", email=email, onboard=False) as (page, _, renewed):
        assert renewed["reactivated"] is True
        assert renewed["user"]["id"] == original["user"]["id"]
        page.goto("/profile")
        form = page.get_by_role("dialog", name="Completa tu perfil")
        expect(form).to_be_visible()
        options = form.get_by_label("Carrera")
        choice = options.locator("option:not([value=''])").first.get_attribute("value")
        assert choice
        options.select_option(choice)
        link_click(page, form.get_by_role("button", name="Continuar", exact=True), CAREER, 200)
        expect(form).to_be_hidden()
        saved = api(page, PROFILE)
        assert (saved["total_points"], saved["available_points"], saved["current_streak"]) == (0, 0, 0)
        impact = saved["impact_metrics"]
        assert all(float(impact[key]) == 0 for key in ("co2_kg", "water_liters", "plastic_kg"))
        capture(page, "T1-22-perfil-reiniciado")
        note(browser, "T1-22-prueba", [
            "La cuenta sintética inició con 17 puntos acumulados.",
            "El botón estuvo deshabilitado hasta marcar la confirmación. Desactivar devolvió HTTP 204 y volvió al acceso.",
            "Un nuevo inicio local con proveedor sintético reactivó el mismo ID.",
            "Después de volver a elegir carrera, el perfil mostró puntos, racha e impacto en cero.",
            "No se ejecutó Microsoft real durante esta reactivación.",
        ])


def test_t123_admin_filter_ban_and_unban(browser):
    suffix = uuid4().hex[:6]
    target = f"qa-moderacion-{suffix}@iteso.mx"
    with actor(browser, "T1-23-cuenta", email=target) as (student, _, identity):
        student.goto("/profile")
        target_id = identity["user"]["id"]
        credit(student, lab_action(suffix))
        assert api(student, PROFILE)["total_points"] == 17
    with actor(browser, "T1-23-moderacion", onboard=False, role="ADMIN") as (admin, _, _):
        admin.goto("/admin/users")
        expect(admin.get_by_role("heading", name="Usuarios", exact=True)).to_be_visible()
        query = admin.get_by_role("searchbox", name="Buscar por ID, correo o nombre")
        query.fill(target)
        row = admin.get_by_role("list", name="Usuarios").get_by_role("listitem").filter(has_text=target)
        expect(row.get_by_text("Activa", exact=True)).to_be_visible()
        row.get_by_role("button", name=re.compile("^Banear a ")).click()
        dialog = admin.get_by_role("alertdialog").or_(admin.get_by_role("dialog"))
        capture(admin, "T1-23-confirmar-bloqueo")
        link_click(admin, dialog.get_by_role("button", name="Banear", exact=True), f"/api/v1/users/{target_id}/ban/", 200)
        expect(row.get_by_text("Baneada", exact=True)).to_be_visible()
        admin.get_by_role("button", name="Baneados", exact=True).click()
        expect(row.get_by_text("Baneada", exact=True)).to_be_visible()
        capture(admin, "T1-23-filtro-baneados")
        blocked = login_mock(admin, target)
        assert blocked.status == 403, f"Inicio ordinario de cuenta bloqueada: HTTP {blocked.status}"
        row.get_by_role("button", name=re.compile("^Desbanear a ")).click()
        link_click(
            admin, dialog.get_by_role("button", name="Desbanear", exact=True), f"/api/v1/users/{target_id}/unban/", 200
        )
        expect(row).to_have_count(0)
        admin.get_by_role("button", name="No baneados", exact=True).click()
        query.fill(target_id)
        expect(row.get_by_text("Activa", exact=True)).to_be_visible()
        capture(admin, "T1-23-busqueda-id")
    with actor(browser, "T1-23-cuenta-restaurada", email=target, onboard=False) as (student, _, _):
        student.goto("/profile")
        assert api(student, PROFILE)["total_points"] == 17
        note(browser, "T1-23-prueba", [
            "El administrador encontró la cuenta sintética por correo y por identificador.",
            "El bloqueo y el desbloqueo desde la ventana Usuarios devolvieron HTTP 200.",
            "El filtro Baneados incluyó la cuenta bloqueada y el filtro No baneados incluyó la cuenta restaurada.",
            "La cuenta bloqueada recibió HTTP 403 al iniciar sesión. Al restaurarla, volvió a entrar y conservó 17 puntos.",
        ])


def test_t124_profile_action_history_filters_and_ownership(browser):
    suffix = uuid4().hex[:6]
    with actor(browser, "T1-24-datos-comparacion") as (peer, _, peer_identity):
        peer.goto("/profile")
        credit(peer, lab_action("B" + suffix))
        assert api(peer, PROFILE)["total_points"] == 17
        assert peer_identity["user"]["id"]
    with actor(browser, "T1-24-historial") as (page, _, identity):
        action = lab_action("A" + suffix)
        page.goto("/profile")
        credit(page, action)
        user_id = identity["user"]["id"]
        seeded = db_read_or_seed(f"""
import json
from green_iteso.accounts.models import User
from green_iteso.actions.models import ActionLog, ActionMaster
user = User.objects.get(id={user_id!r})
action = ActionMaster.objects.get(id={action!r})
for state in ('PENDING_AUDIT', 'REJECTED'):
    ActionLog.objects.create(user=user, action=action, institutional_clan=user.profile.institutional_clan,
                             idempotency_key={suffix!r} + state, status=state, points_awarded=0)
print(json.dumps(2))
""")
        assert seeded == 2
        page.reload()
        history = page.get_by_role("region", name="Historial de Acciones")
        rows = history.get_by_role("listitem")
        selector = history.get_by_label("Filtrar acciones por estado")
        expect(rows).to_have_count(3)
        expect(history.get_by_text(f"Reciclaje QA B{suffix}", exact=True)).to_have_count(0)
        for state, label, slug in (
            ("APPROVED", "Aprobado", "aprobadas"),
            ("PENDING_AUDIT", "Pendiente", "pendientes"),
            ("REJECTED", "Rechazado", "rechazadas"),
        ):
            with page.expect_response(
                lambda result, state=state: urlsplit(result.url).path == "/api/v1/action-logs/mine/"
                and parse_qs(urlsplit(result.url).query).get("status") == [state]
            ) as exchange:
                selector.select_option(state)
            assert exchange.value.status == 200
            data = exchange.value.json()
            delivered = data["results"] if isinstance(data, dict) else data
            assert len(delivered) == 1 and delivered[0]["status"] == state
            expect(rows).to_have_count(1)
            expect(rows.get_by_text(label, exact=True)).to_be_visible()
            history.scroll_into_view_if_needed()
            capture(page, f"T1-24-{slug}")
        selector.select_option("ALL")
        expect(rows).to_have_count(3)
        note(browser, "T1-24-prueba", [
            "El historial mostró tres registros propios y excluyó la acción del otro estudiante sintético.",
            "Cada filtro consultó el backend real y devolvió un solo registro del estado elegido.",
            "Se verificaron acciones aprobadas, pendientes y rechazadas. Al volver a Todas, reaparecieron las tres.",
        ])
