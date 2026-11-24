"""Exercise the supported join, expel, leave, and rejoin UI for a disposable public clan."""
from playwright.sync_api import expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _create_clan
from release_qa.test_team2_acceptance import (
    PROFILE,
    api,
    clan_state,
    confirm,
    credit,
    join,
    lab_action,
    roster,
    select,
)

clans = test_final_clans.clans


def test_t130_rejoin_does_not_restore_active_selection(clans):
    actor, screenshot, suffix = clans
    with (
        actor("T1-30-lider", "Líder QA") as leader,
        actor("T1-30-miembro", "Miembro QA") as member,
    ):
        title = f"Retorno QA {suffix}"
        clan = _create_clan(leader, title)
        path = f"{CLAN_API}{clan}/"
        join(member, clan)
        select(member, clan)
        user_id = api(member, PROFILE)["user_id"]
        action = lab_action(suffix)
        credit(member, action)
        leader.reload()
        expect(leader.get_by_role("heading", name="Miembros (2)")).to_be_visible()
        expect(leader.get_by_role("button", name="Salir del clan")).to_have_count(0)
        confirm(leader, "Expulsar", opener=f"Expulsar a Miembro QA {suffix}",
                path=path + "kick/", status=204)
        assert api(member, PROFILE)["active_private_clan"] is None
        credit(member, action)
        assert clan_state(clan)["points"] == 17
        assert api(member, PROFILE)["total_points"] == 34

        join(member, clan)
        expect(member.get_by_role("button", name="Establecer como clan activo")).to_be_visible()
        assert roster(clan_state(clan))[user_id] == ("MEMBER", "ACCEPTED", False)
        confirm(member, "Salir del clan", path=path + "leave/", status=204)
        expect(member.get_by_text(f"Saliste de {title}.", exact=True)).to_be_visible()
        join(member, clan)
        expect(member.get_by_role("button", name="Salir del clan")).to_be_visible()
        state = clan_state(clan)
        assert len([row for row in state["members"] if row[0] == user_id]) == 1
        assert state["points"] == 17 and api(member, PROFILE)["active_private_clan"] is None
        screenshot(member, "T1-30-reingreso")
