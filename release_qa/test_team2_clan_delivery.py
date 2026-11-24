"""Verify two release integrations in the browser against the isolated stack."""

import json
import re
from time import monotonic
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, WebSocket, expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _create_clan
from release_qa.test_final_identity import synthetic_png
from release_qa.test_team2_acceptance import NOTIFICATIONS, PROFILE, api, join
from src.utils.common_actions import go_to

clans = test_final_clans.clans
pytestmark = pytest.mark.full


def _edit_profile_photo(owner: Page, *, upload: bool) -> None:
    go_to(owner, "/profile")
    owner.get_by_role("button", name="Editar perfil").click()
    dialog = owner.get_by_role("dialog")
    if upload:
        dialog.get_by_role("button", name=re.compile("^Público")).click()
        dialog.get_by_test_id("profile-avatar-file").set_input_files(
            {"name": "avatar-miembro-sintetico.png", "mimeType": "image/png", "buffer": synthetic_png()}
        )
        expect(dialog.get_by_text("Se subirá «avatar-miembro-sintetico.png» al guardar.", exact=True)).to_be_visible()
    else:
        dialog.get_by_role("button", name=re.compile("^Privado")).click()
    dialog.get_by_role("button", name="Guardar cambios", exact=True).click()
    expect(dialog.get_by_text("¡Perfil actualizado correctamente!", exact=True)).to_be_visible()
    expect(dialog).to_be_hidden()


def _roster_row(viewer: Page, nickname: str):
    region = viewer.get_by_role("region", name=re.compile("^Miembros"))
    row = region.get_by_role("listitem").filter(has_text=nickname)
    expect(row).to_be_visible()
    return row


def test_clan_roster_loads_public_member_avatar_and_hides_it_after_privacy_change(clans):
    actor, screenshot, suffix = clans
    title = f"Bosque de Miembros {suffix}"
    nickname = f"Miembro Avatar {suffix}"
    with (
        actor("cierre-avatar-lider", "Líder Avatar") as leader,
        actor("cierre-avatar-miembro", "Miembro Avatar") as member,
        actor("cierre-avatar-visitante", "Visitante Avatar") as viewer,
    ):
        clan_id = _create_clan(leader, title)
        join(member, clan_id)
        _edit_profile_photo(member, upload=True)
        profile = api(member, PROFILE)
        user_id = profile["user_id"]
        assert profile["visibility"] == "PUBLIC"
        avatar_path = f"/api/v1/avatars/{user_id}/"

        with viewer.expect_response(lambda response: urlsplit(response.url).path == avatar_path) as loaded:
            go_to(viewer, f"/clans/{clan_id}")
        assert loaded.value.status == 200
        assert loaded.value.headers["content-type"].startswith("image/")
        roster = _roster_row(viewer, nickname)
        image = roster.locator("img[src*='/api/v1/avatars/']")
        expect(image).to_be_visible()
        expect(image).to_have_js_property("naturalWidth", 96)
        screenshot(viewer, "avatar-publico-en-clan")

        _edit_profile_photo(member, upload=False)
        assert api(member, PROFILE)["visibility"] == "PRIVATE"
        viewer.reload()
        roster = _roster_row(viewer, nickname)
        expect(roster.locator("img[src*='/api/v1/avatars/']")).to_have_count(0)
        data = api(viewer, f"{CLAN_API}{clan_id}/")
        entry = next(row for row in data["members"] if row["user_id"] == user_id)
        assert entry["avatar_url"] == ""
        screenshot(viewer, "avatar-privado-en-clan")


def test_clan_join_notification_reaches_open_browser_and_persists(clans):
    actor, screenshot, suffix = clans
    clan_name = f"Río de Avisos {suffix}"
    notice_title = "Nuevo miembro en tu clan"
    member_name = f"Miembro Avisos {suffix}"
    with (
        actor("cierre-aviso-lider", "Líder Avisos") as leader,
        actor("cierre-aviso-miembro", "Miembro Avisos") as member,
    ):
        clan_id = _create_clan(leader, clan_name)
        authenticated = []
        delivered = []

        def observe_frame(payload):
            message = json.loads(payload)
            if message.get("type") == "auth.ok":
                authenticated.append(True)
            if message.get("type") == "notification.created":
                event = message.get("notification", {})
                if event.get("notification_type") == "CLAN_MEMBER_JOINED":
                    delivered.append(event["id"])

        def observe_socket(socket: WebSocket) -> None:
            if urlsplit(socket.url).path == "/ws/notifications/":
                socket.on("framereceived", observe_frame)

        leader.on("websocket", observe_socket)
        go_to(leader, "/notifications")
        expect(leader.get_by_role("heading", name="Notificaciones", exact=True)).to_be_visible()
        expect(leader.get_by_text("No tienes notificaciones.", exact=True)).to_be_visible()
        deadline = monotonic() + 8
        while not authenticated and monotonic() < deadline:
            leader.wait_for_timeout(80)
        assert authenticated, "El socket de notificaciones no confirmó la sesión."

        # The member acts in another browser context while the leader stays on the same page.
        requests = []
        leader.on("framenavigated", lambda frame: requests.append(True) if frame == leader.main_frame else None)
        join(member, clan_id)
        toast = leader.get_by_role("status").filter(has_text=notice_title)
        expect(toast).to_contain_text(clan_name)
        expect(toast).to_contain_text(member_name)
        expect(leader.get_by_text("Tienes 1 notificaciones sin leer.", exact=True)).to_be_visible()
        assert not requests, "El navegador del líder navegó antes de recibir el aviso."
        assert len(delivered) == 1, "Se esperaba una entrega WebSocket del evento de incorporación."
        screenshot(leader, "aviso-en-vivo")

        api_notices = api(leader, NOTIFICATIONS)["results"]
        joined, = [row for row in api_notices if row["notification_type"] == "CLAN_MEMBER_JOINED"]
        assert joined["id"] == delivered[0]
        assert joined["is_read"] is False
        leader.reload()
        expect(leader.get_by_text(notice_title, exact=True)).to_be_visible()
        screenshot(leader, "aviso-tras-recarga")
