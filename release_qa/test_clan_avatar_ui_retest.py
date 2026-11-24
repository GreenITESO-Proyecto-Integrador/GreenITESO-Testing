"""Verify the local clan avatar UI after the leader uploads via the app's API."""

from playwright.sync_api import expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _create_clan
from release_qa.test_team2_acceptance import api
from release_qa.test_team2_clan_audit import PNG, _edit_dialog
from src.configs import environment as env

clans = test_final_clans.clans


def test_leader_editor_does_not_offer_clan_avatar(clans):
    actor, screenshot, suffix = clans
    name = f"Fresnos QA {suffix}"
    with actor("avatar-editor-lider", "Líder Avatar QA") as leader:
        clan = _create_clan(leader, name)
        path = f"{CLAN_API}{clan}/"
        token = leader.evaluate("sessionStorage.getItem('greeniteso.access_token')")
        assert token
        uploaded = leader.request.post(
            f"{env.API_BASE_URL}{path}avatar/",
            headers={"Authorization": f"Bearer {token}"},
            multipart={"avatar": {"name": "clan.png", "mimeType": "image/png", "buffer": PNG}},
        )
        assert uploaded.status == 200
        object_key = uploaded.json()["avatar_object_key"]
        assert object_key

        leader.reload()
        expect(leader.get_by_role("heading", name=name, exact=True)).to_be_visible()
        detail = api(leader, path)
        assert detail["avatar_object_key"] == object_key
        assert not detail.get("avatar_url")
        screenshot(leader, "T1-18-detalle")

        editor = _edit_dialog(leader)
        expect(editor).to_be_visible()
        expect(editor.locator('input[type="file"]')).to_have_count(0)
        screenshot(leader, "T1-18-editor")
        api(leader, f"{path}avatar/", method="DELETE", status=200)
        assert api(leader, path)["avatar_object_key"] == ""
