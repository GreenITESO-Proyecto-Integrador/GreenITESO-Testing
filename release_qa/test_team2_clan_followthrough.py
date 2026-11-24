"""Check the follow-through of ordinary clan invitations and notifications."""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _click_api, _create_clan
from release_qa.test_team2_acceptance import NOTIFICATIONS, api, db_read_or_seed, join
from src.utils.common_actions import go_to

clans = test_final_clans.clans
pytestmark = pytest.mark.full
MASK_CODE = '[data-testid="new-invite-code"], #clan-invite-code { color: transparent !important; }'


def test_read_clan_join_notification_persists_after_reload(clans):
    actor, screenshot, suffix = clans
    title = f"Río de Lectura {suffix}"
    notice = "Nuevo miembro en tu clan"
    with (
        actor("seguimiento-aviso-lider", "Líder Lectura") as leader,
        actor("seguimiento-aviso-miembro", "Miembro Lectura") as member,
    ):
        clan = _create_clan(leader, title)
        join(member, clan)
        go_to(leader, "/notifications")
        expect(leader.get_by_text(notice, exact=True)).to_be_visible()
        expect(leader.get_by_text("Tienes 1 notificaciones sin leer.", exact=True)).to_be_visible()
        event, = [row for row in api(leader, NOTIFICATIONS)["results"] if row["notification_type"] == "CLAN_MEMBER_JOINED"]
        assert event["is_read"] is False
        path = f"{NOTIFICATIONS}{event['id']}/"
        mark = leader.get_by_role("button", name="Marcar como leída", exact=True)
        with leader.expect_response(
            lambda response: urlsplit(response.url).path == path and response.request.method == "PATCH"
        ) as patch:
            mark.click()
        assert patch.value.status == 200
        assert patch.value.json()["is_read"] is True
        expect(leader.get_by_text("Estás al día.", exact=True)).to_be_visible()

        leader.reload()
        expect(leader.get_by_text(notice, exact=True)).to_be_visible()
        expect(leader.get_by_text("Estás al día.", exact=True)).to_be_visible()
        expect(mark).to_have_count(0)
        after, = [row for row in api(leader, NOTIFICATIONS)["results"] if row["id"] == event["id"]]
        assert after["is_read"] is True
        screenshot(leader, "aviso-leido-tras-recarga")


def test_expired_invite_is_hidden_and_cannot_be_redeemed(clans):
    actor, screenshot, suffix = clans
    with actor("seguimiento-expira-lider", "Líder Caducidad") as leader:
        clan = _create_clan(leader, f"Lago de Invitación {suffix}", invite_only=True)
        leader.add_style_tag(content=MASK_CODE)
        leader.get_by_role("button", name="Invitar con código", exact=True).click()
        dialog = leader.get_by_role("dialog")
        invite = _click_api(
            leader, dialog.get_by_role("button", name="Generar código"), f"{CLAN_API}{clan}/invitations/", 201
        ).json()
        valid_hours = (datetime.fromisoformat(invite["expires_at"]) - datetime.now(UTC)).total_seconds() / 3600
        assert 47 < valid_hours < 49
        expect(dialog.get_by_role("button", name=re.compile("^Revocar código"))).to_be_visible()

        # Advance this one synthetic fixture beyond its expiry while keeping the normal invite flow.
        assert db_read_or_seed(f"""
import json
from datetime import timedelta
from django.utils import timezone
from green_iteso.accounts.models import ClanInvitation
now = timezone.now()
row = ClanInvitation.objects.filter(pk={invite['id']!r}, clan_id={clan!r})
updated = row.update(created_at=now - timedelta(hours=49), expires_at=now - timedelta(hours=1))
print(json.dumps(updated))
""") == 1
        leader.reload()
        leader.get_by_role("button", name="Invitar con código", exact=True).click()
        expect(leader.get_by_text("No hay códigos activos.", exact=True)).to_be_visible()
        screenshot(leader, "invitacion-caducada-oculta")

    with actor("seguimiento-expira-invitado", "Invitado Caducidad") as member:
        go_to(member, "/clans")
        member.add_style_tag(content=MASK_CODE)
        member.get_by_role("button", name="Tengo una invitación", exact=True).click()
        dialog = member.get_by_role("dialog")
        code = dialog.get_by_label("Código de invitación")
        code.fill(invite["code"])
        refused = _click_api(
            member, dialog.get_by_role("button", name="Unirme al clan"), f"{CLAN_API}redeem-invitation/", 400
        )
        assert "code" in refused.json()
        expect(code).to_have_attribute("aria-invalid", "true")
        expect(dialog.get_by_role("alert")).to_have_text(
            "El código no es válido o ya venció. Pídele uno nuevo al líder del clan."
        )
        expect(member).to_have_url(re.compile(r"/clans$"))
        screenshot(member, "invitacion-caducada-denegada")
