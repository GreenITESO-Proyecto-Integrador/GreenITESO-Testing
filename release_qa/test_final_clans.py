"""Team 1 acceptance checks for Team 2 clans on an isolated GreenITESO stack."""

import os
import re
from contextlib import contextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import Browser, Error, Locator, Page, expect

from src.configs import environment as env
from src.utils.auth import get_session, inject_session
from src.utils.common_actions import go_to

CLAN_API = "/api/v1/clans/"
pytestmark = pytest.mark.full


@pytest.fixture
def clans(browser: Browser):
    """Prepare synthetic browser sessions and optional video for each role."""
    for url in (env.BASE_URL, env.API_BASE_URL):
        assert urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}
    assert not env.E2E_CLEANUP
    assert env.AUTH_MODE == "mock"

    evidence = os.getenv("FINAL_QA_CLAN_EVIDENCE")
    output = Path(evidence, browser.browser_type.name) if evidence else None
    mobile = os.getenv("FINAL_QA_MOBILE") == "1"
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900}
    suffix = uuid4().hex[:6]

    @contextmanager
    def actor(scene: str, name: str):
        video_options = {}
        if output:
            video_options = {"record_video_dir": output / "videos", "record_video_size": viewport}
        context = browser.new_context(viewport=viewport, **video_options)
        page = context.new_page()
        page.set_default_timeout(12_000)
        try:
            email = f"qa-clanes.{scene.lower()}.{suffix}@iteso.mx"
            session = get_session(page.request, email)
            headers = {"Authorization": f"Bearer {session['access']}"}
            onboarding = f"{env.API_BASE_URL}{CLAN_API}institutional-clan/"
            careers = page.request.get(f"{onboarding}careers/", headers=headers)
            assert careers.ok, f"Carreras: HTTP {careers.status}"
            saved = page.request.post(
                onboarding,
                headers=headers,
                data={"career": careers.json()["careers"][0], "nickname": f"{name} {suffix}"},
            )
            assert saved.ok, f"Datos sintéticos de sesión: HTTP {saved.status}"
            inject_session(page, session)
            yield page
        except Exception:
            with suppress(Error):
                screenshot(page, f"{scene}-fallo")
            raise
        finally:
            video = page.video
            context.close()
            if output and video:
                Path(video.path()).replace(output / "videos" / f"{scene}.webm")

    def screenshot(page: Page, name: str) -> None:
        if output and page.url.startswith(env.BASE_URL):
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=output / f"{name}.png")

    return actor, screenshot, suffix


def _click_api(page: Page, button: Locator, path: str, status: int):
    with page.expect_response(
        lambda response: urlsplit(response.url).path == path
        and response.request.method == "POST"
    ) as intercepted:
        button.click()
    response = intercepted.value
    assert response.status == status, f"{path}: HTTP {response.status}, se esperaba {status}"
    return response


def _create_clan(page: Page, title: str, *, invite_only: bool = False) -> str:
    go_to(page, "/clans")
    page.get_by_role("button", name="Crear clan", exact=True).click()
    dialog = page.get_by_role("dialog", name="Crear clan")
    submit = dialog.get_by_role("button", name="Crear clan", exact=True)
    submit.click()
    expect(dialog.get_by_text("Escribe un nombre para el clan.")).to_be_visible()
    dialog.get_by_label("Nombre", exact=True).fill(title)
    dialog.get_by_label("Descripción (opcional)").fill("Clan sintético para una prueba de clase.")
    if invite_only:
        dialog.get_by_role("button", name="Solo invitación", exact=True).click()
    result = _click_api(page, submit, CLAN_API, 201).json()
    expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
    assert result["privacy"] == ("PRIVATE_INVITE" if invite_only else "PUBLIC")
    return str(result["id"])


@pytest.mark.sanity
def test_t1_06_public_clan_creation_join_and_active_persistence(clans):
    actor, screenshot, suffix = clans
    title = f"Guardianes del Campus {suffix}"
    with actor("T1-06-creacion", "Líder Público") as leader:
        clan_id = _create_clan(leader, title)
        expect(leader.get_by_role("button", name="Transferir liderazgo")).to_be_visible()
        screenshot(leader, "T1-06-creacion")

    with actor("T1-06-membresia", "Miembro Público") as member:
        go_to(member, "/clans")
        member.get_by_label("Buscar clanes por nombre").fill(title)
        member.get_by_role("link", name=re.compile(re.escape(title))).first.click()
        expect(member.get_by_role("heading", name=title, exact=True)).to_be_visible()
        path = f"{CLAN_API}{clan_id}/"
        result = _click_api(
            member, member.get_by_role("button", name="Unirme al clan"), f"{path}join/", 201
        )
        assert result.json()["status"] == "ACCEPTED"
        _click_api(
            member,
            member.get_by_role("button", name="Establecer como clan activo"),
            f"{path}select-active/",
            200,
        )
        expect(member.get_by_text("Es tu clan activo", exact=True)).to_be_visible()
        member.reload()
        expect(member.get_by_text("Es tu clan activo", exact=True)).to_be_visible()
        expect(member.get_by_role("button", name="Salir del clan")).to_be_visible()
        screenshot(member, "T1-06-membresia")


def _request_join(page: Page, clan_id: str) -> None:
    go_to(page, f"/clans/{clan_id}")
    expect(page.get_by_role("heading", name="No encontramos este clan")).to_be_visible()
    result = _click_api(
        page,
        page.get_by_role("button", name="Solicitar unirme"),
        f"{CLAN_API}{clan_id}/join/",
        201,
    )
    assert result.json()["status"] == "PENDING"
    expect(page.get_by_role("heading", name="Solicitud enviada")).to_be_visible()


@pytest.mark.sanity
def test_t1_07_private_requests_and_leader_controls(clans):
    actor, screenshot, suffix = clans
    title = f"Semillas del Campus {suffix}"
    with (
        actor("T1-07-lider", "Líder Privado") as leader,
        actor("T1-07-solicitud", "Aspirante Uno") as accepted,
        actor("T1-07-rechazo", "Aspirante Dos") as rejected,
    ):
        clan_id = _create_clan(leader, title, invite_only=True)
        _request_join(accepted, clan_id)
        screenshot(accepted, "T1-07-solicitud")
        _request_join(rejected, clan_id)

        leader.reload()
        expect(leader.get_by_role("heading", name="Solicitudes pendientes (2)")).to_be_visible()
        screenshot(leader, "T1-07-pendientes")
        _click_api(
            leader,
            leader.get_by_role("button", name=re.compile("Aceptar solicitud de Aspirante Uno")),
            f"{CLAN_API}{clan_id}/accept-request/",
            200,
        )
        _click_api(
            leader,
            leader.get_by_role("button", name=re.compile("Rechazar solicitud de Aspirante Dos")),
            f"{CLAN_API}{clan_id}/reject-request/",
            200,
        )
        expect(leader.get_by_role("heading", name="Solicitudes pendientes (0)")).to_be_visible()
        expect(leader.get_by_text(f"Aspirante Uno {suffix}", exact=True)).to_be_visible()
        expect(leader.get_by_text(f"Aspirante Dos {suffix}", exact=True)).to_have_count(0)
        leader.reload()
        expect(leader.get_by_role("heading", name="Solicitudes pendientes (0)")).to_be_visible()
        screenshot(leader, "T1-07-decisiones")

        accepted.reload()
        expect(accepted.get_by_role("heading", name=title, exact=True)).to_be_visible()
        expect(accepted.get_by_role("button", name="Salir del clan")).to_be_visible()
        for name in ("Invitar con código", "Editar clan", "Transferir liderazgo", "Disolver clan"):
            expect(accepted.get_by_role("button", name=name)).to_have_count(0)
        expect(accepted.get_by_role("heading", name=re.compile("Solicitudes pendientes"))).to_have_count(0)
        denied = accepted.evaluate(
            """async path => {
                const token = sessionStorage.getItem('greeniteso.access_token');
                const response = await fetch(path, {headers: {Authorization: `Bearer ${token}`}});
                return response.status;
            }""",
            f"{CLAN_API}{clan_id}/requests/",
        )
        assert denied == 403, f"Bandeja de solicitudes desde cuenta miembro: HTTP {denied}, se esperaba 403"
        screenshot(accepted, "T1-07-miembro")

        rejected.reload()
        expect(rejected.get_by_role("heading", name="No encontramos este clan")).to_be_visible()
        screenshot(rejected, "T1-07-rechazo")


def test_t1_07_private_code_is_single_use(clans):
    actor, screenshot, suffix = clans
    title = f"Raíces del Campus {suffix}"
    mask = '[data-testid="new-invite-code"], #clan-invite-code { color: transparent !important; }'
    with actor("T1-07-codigo-lider", "Líder Invitación") as leader:
        clan_id = _create_clan(leader, title, invite_only=True)
        leader.add_style_tag(content=mask)
        leader.get_by_role("button", name="Invitar con código").click()
        generated = _click_api(
            leader,
            leader.get_by_role("button", name="Generar código"),
            f"{CLAN_API}{clan_id}/invitations/",
            201,
        )
        expect(leader.get_by_text("Código nuevo", exact=True)).to_be_visible()
        code = generated.json()["code"]
        assert leader.get_by_test_id("new-invite-code").text_content() == code
        screenshot(leader, "T1-07-codigo-generado")

    with actor("T1-07-codigo-valido", "Invitado Privado") as member:
        go_to(member, "/clans")
        member.add_style_tag(content=mask)
        member.get_by_role("button", name="Tengo una invitación").click()
        dialog = member.get_by_role("dialog", name="Tengo una invitación")
        field = dialog.get_by_label("Código de invitación")
        submit = dialog.get_by_role("button", name="Unirme al clan")
        field.fill("ABC")
        submit.click()
        expect(dialog.get_by_text("El código tiene 8 caracteres", exact=False)).to_be_visible()
        field.fill(code)
        result = _click_api(member, submit, f"{CLAN_API}redeem-invitation/", 201)
        assert result.json()["status"] == "ACCEPTED"
        expect(member.get_by_role("heading", name=title, exact=True)).to_be_visible()
        member.reload()
        expect(member.get_by_role("button", name="Salir del clan")).to_be_visible()
        screenshot(member, "T1-07-codigo-aceptado")

    with actor("T1-07-codigo-reutilizado", "Intento Repetido") as other:
        go_to(other, "/clans")
        other.add_style_tag(content=mask)
        other.get_by_role("button", name="Tengo una invitación").click()
        dialog = other.get_by_role("dialog", name="Tengo una invitación")
        dialog.get_by_label("Código de invitación").fill(code)
        _click_api(
            other,
            dialog.get_by_role("button", name="Unirme al clan"),
            f"{CLAN_API}redeem-invitation/",
            400,
        )
        expect(dialog.get_by_label("Código de invitación")).to_have_attribute("aria-invalid", "true")
        screenshot(other, "T1-07-codigo-reutilizado")
