"""Additional Team 2 clan checks against the isolated release stack."""

import re
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _click_api, _create_clan, _request_join
from release_qa.test_team2_acceptance import PROFILE, api, db_read_or_seed, join
from src.configs import environment as env
from src.utils.common_actions import go_to

clans = test_final_clans.clans
pytestmark = pytest.mark.full
CAMPAIGNS_API = "/api/v1/campaigns/"
MASK_CODE = '[data-testid="new-invite-code"], #clan-invite-code { color: transparent !important; }'
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _directory_search(page: Page, title: str):
    go_to(page, "/clans")

    def is_search(response):
        url = urlsplit(response.url)
        return url.path == CLAN_API and parse_qs(url.query).get("search") == [title]

    with page.expect_response(is_search) as observed:
        page.get_by_label("Buscar clanes por nombre").fill(title)
    assert observed.value.ok
    return page.get_by_role("link", name=re.compile(re.escape(title)))


def _edit_dialog(leader: Page):
    leader.get_by_role("button", name="Editar clan", exact=True).click()
    dialog = leader.get_by_role("dialog", name="Editar clan")
    expect(dialog.get_by_role("button", name="Guardar cambios")).to_be_disabled()
    return dialog


def _save_clan(leader: Page, clan_id: str, dialog) -> None:
    with leader.expect_response(
        lambda response: urlsplit(response.url).path == f"{CLAN_API}{clan_id}/"
        and response.request.method == "PATCH"
    ) as saved:
        dialog.get_by_role("button", name="Guardar cambios").click()
    assert saved.value.status == 200
    expect(dialog).to_have_count(0)


def test_clan_edit_keeps_members_and_pending_requests(clans):
    actor, screenshot, suffix = clans
    base_name = f"Bosque QA {suffix}"
    new_name = f"Bosque Renombrado {suffix}"
    description = "Descripción actualizada para descubrir clanes."
    with (
        actor("auditoria-editar-lider", "Líder Edición") as leader,
        actor("auditoria-editar-miembro", "Miembro Edición") as member,
        actor("auditoria-editar-solicitante", "Solicitante Edición") as applicant,
    ):
        clan_id = _create_clan(leader, base_name)
        join(member, clan_id)
        expect(_directory_search(applicant, base_name)).to_be_visible()

        dialog = _edit_dialog(leader)
        dialog.get_by_label("Nombre", exact=True).fill(new_name)
        dialog.get_by_label("Descripción (opcional)").fill(description)
        dialog.get_by_role("button", name="Solo invitación", exact=True).click()
        _save_clan(leader, clan_id, dialog)
        leader.reload()
        expect(leader.get_by_role("heading", name=new_name, exact=True)).to_be_visible()
        expect(leader.get_by_text(description, exact=True)).to_be_visible()
        expect(leader.get_by_role("heading", name="Miembros (2)")).to_be_visible()
        screenshot(leader, "clan-editado")

        member.reload()
        expect(member.get_by_role("heading", name=new_name, exact=True)).to_be_visible()
        expect(member.get_by_role("button", name="Salir del clan", exact=True)).to_be_visible()
        expect(_directory_search(applicant, new_name)).to_have_count(0)
        expect(applicant.get_by_text("Sin resultados", exact=True)).to_be_visible()
        screenshot(applicant, "clan-oculto-del-catalogo")

        _request_join(applicant, clan_id)
        leader.reload()
        expect(leader.get_by_role("heading", name="Solicitudes pendientes (1)")).to_be_visible()
        dialog = _edit_dialog(leader)
        dialog.get_by_role("button", name="Pública", exact=True).click()
        _save_clan(leader, clan_id, dialog)
        leader.reload()
        expect(leader.get_by_role("heading", name="Solicitudes pendientes (1)")).to_be_visible()
        expect(leader.get_by_role("heading", name="Miembros (2)")).to_be_visible()
        screenshot(leader, "solicitud-conservada-al-publicar")
        expect(_directory_search(applicant, new_name)).to_be_visible()


def test_leader_revokes_unredeemed_invite_code(clans):
    actor, screenshot, suffix = clans
    title = f"Nubes QA {suffix}"
    with actor("auditoria-revocar-lider", "Líder Revocación") as leader:
        clan = _create_clan(leader, title, invite_only=True)
        leader.add_style_tag(content=MASK_CODE)
        leader.get_by_role("button", name="Invitar con código").click()
        dialog = leader.get_by_role("dialog")
        created = _click_api(
            leader, dialog.get_by_role("button", name="Generar código"), f"{CLAN_API}{clan}/invitations/", 201
        ).json()
        revoke = dialog.get_by_role("button", name=re.compile("^Revocar código"))
        invite_path = f"{CLAN_API}{clan}/invitations/{created['id']}/"
        with leader.expect_response(
            lambda response: urlsplit(response.url).path == invite_path and response.request.method == "DELETE"
        ) as removed:
            revoke.click()
        assert removed.value.status == 204
        expect(revoke).to_have_count(0)
        expect(dialog.get_by_test_id("new-invite-code")).to_have_count(0)

        leader.reload()
        leader.get_by_role("button", name="Invitar con código").click()
        expect(leader.get_by_text("No hay códigos activos.", exact=True)).to_be_visible()
        screenshot(leader, "codigo-revocado")

    with actor("auditoria-revocar-invitado", "Invitado Revocación") as member:
        go_to(member, "/clans")
        member.add_style_tag(content=MASK_CODE)
        member.get_by_role("button", name="Tengo una invitación").click()
        dialog = member.get_by_role("dialog", name="Tengo una invitación")
        code = dialog.get_by_label("Código de invitación")
        code.fill(created["code"])
        _click_api(member, dialog.get_by_role("button", name="Unirme al clan"), f"{CLAN_API}redeem-invitation/", 400)
        expect(code).to_have_attribute("aria-invalid", "true")
        screenshot(member, "codigo-revocado-denegado")


def test_clan_avatar_local_upload_and_remove(clans):
    actor, screenshot, suffix = clans
    title = f"Fresnos QA {suffix}"
    with actor("auditoria-avatar-lider", "Líder Avatar QA") as leader:
        clan = _create_clan(leader, title)
        path = f"{CLAN_API}{clan}/"
        header = "Authorization"
        token = leader.evaluate("sessionStorage.getItem('greeniteso.access_token')")
        assert token
        saved = leader.request.post(
            f"{env.API_BASE_URL}{path}avatar/",
            headers={header: f"Bearer {token}"},
            multipart={"avatar": {"name": "clan.png", "mimeType": "image/png", "buffer": PNG}},
        )
        assert saved.status == 200, f"Avatar local HTTP {saved.status}"
        key = saved.json()["avatar_object_key"]
        detail = api(leader, path)
        assert key and detail["avatar_object_key"] == key
        assert "avatar_url" not in detail
        leader.reload()
        expect(leader.get_by_role("heading", name=title, exact=True)).to_be_visible()
        expect(leader.get_by_role("button", name=re.compile("foto del clan", re.IGNORECASE))).to_have_count(0)
        screenshot(leader, "avatar-clan-solo-api")
        api(leader, f"{path}avatar/", method="DELETE", status=200)
        assert api(leader, path)["avatar_object_key"] == ""


def test_clan_profile_shows_active_clan_campaigns_to_members(clans):
    actor, screenshot, suffix = clans
    title = f"Senderos QA {suffix}"
    active = f"Campaña activa QA {suffix}"
    finished = f"Campaña finalizada QA {suffix}"
    with (
        actor("auditoria-campana-lider", "Líder Campaña QA") as leader,
        actor("auditoria-campana-miembro", "Miembro Campaña QA") as member,
        actor("auditoria-campana-visitante", "Visitante Campaña QA") as visitor,
    ):
        clan = _create_clan(leader, title)
        owner = api(leader, PROFILE)["user_id"]
        db_read_or_seed(f"""
import json
from datetime import timedelta
from django.utils import timezone
from green_iteso.campaigns.models import Campaign
now = timezone.now()
for title, status, end in [({active!r}, "IN_PROGRESS", 1), ({finished!r}, "FINISHED", -1)]:
    Campaign.objects.create(title=title, description="Campaña sintética", creator_id={owner!r},
        scope="PRIVATE", target_clan_id={clan!r}, status=status,
        start_date=now - timedelta(days=3), end_date=now + timedelta(days=end))
print(json.dumps(True))
""")
        go_to(visitor, f"/clans/{clan}")
        expect(visitor.get_by_role("heading", name=title, exact=True)).to_be_visible()
        expect(visitor.get_by_role("heading", name="Campañas activas")).to_have_count(0)
        query = f"{CAMPAIGNS_API}?target_clan={clan}&is_active=true"
        assert api(visitor, query)["results"] == []
        screenshot(visitor, "campanas-visitante")

        join(member, clan)
        member.reload()
        section = member.get_by_role("region", name="Campañas activas")
        expect(section.get_by_text(active, exact=True)).to_be_visible()
        expect(section.get_by_text(finished, exact=True)).to_have_count(0)
        assert [row["title"] for row in api(member, query)["results"]] == [active]
        screenshot(member, "campanas-miembro")
