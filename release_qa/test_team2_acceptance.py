"""Supplemental release acceptance on the disposable GreenITESO stack."""

import json
import re
import subprocess
from uuid import uuid4

from playwright.sync_api import expect

from release_qa import test_final_clans
from release_qa.test_final_clans import CLAN_API, _click_api, _create_clan
from src.configs import environment as env
from src.utils.common_actions import go_to

clans = test_final_clans.clans

PROFILE = "/api/v1/profile/me/"
NOTIFICATIONS = "/api/v1/notifications/"


def db_read_or_seed(code):
    result = subprocess.check_output(
        ["docker", "exec", "greeniteso-final-qa-backend-1", "/opt/venv/bin/python",
         "manage.py", "shell", "-c", code],
        text=True,
    )
    return json.loads(result.strip().splitlines()[-1])


def api(page, path, *, method="GET", data=None, status=200):
    token = page.evaluate("sessionStorage.getItem('greeniteso.access_token')")
    assert token
    response = page.request.fetch(
        env.API_BASE_URL + path, method=method, data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status == status, f"{method} {path}: {response.status}, expected {status}: {response.text()[:220]}"
    return response.json() if status != 204 else None


def join(page, clan_id):
    go_to(page, f"/clans/{clan_id}")
    _click_api(page, page.get_by_role("button", name="Unirme al clan"), f"{CLAN_API}{clan_id}/join/", 201)


def confirm(page, label, *, path, status, method="POST", opener=None):
    page.get_by_role("button", name=opener or label, exact=True).click()
    dialog = page.get_by_role("alertdialog").or_(page.get_by_role("dialog"))
    with page.expect_response(lambda response: response.url.endswith(path) and response.request.method == method) as event:
        dialog.get_by_role("button", name=label, exact=True).click()
    assert event.value.status == status, (path, event.value.status)


def lab_action(suffix):
    return db_read_or_seed(f"""
import json
from green_iteso.actions.models import ActionCategory, ActionMaster
category = ActionCategory.objects.create(code='QA_{suffix}', name='Acción de prueba {suffix}')
action = ActionMaster.objects.create(code='EXT_{suffix}', category=category, name='Reciclaje QA {suffix}',
    description='Acción sintética para comprobar atribución', points=17, daily_limit=10,
    validation_type='NONE', co2_kg_factor='2.500', water_liters_factor='3.000', plastic_kg_factor='0.500')
print(json.dumps(str(action.pk)))
""")


def credit(page, action_id):
    return api(page, "/api/v1/action-logs/", method="POST", status=201,
               data={"action_id": action_id, "idempotency_key": str(uuid4())})


def select(page, clan_id):
    go_to(page, f"/clans/{clan_id}")
    _click_api(page, page.get_by_role("button", name="Establecer como clan activo"),
               f"{CLAN_API}{clan_id}/select-active/", 200)
    expect(page.get_by_text("Es tu clan activo", exact=True)).to_be_visible()


def clan_state(clan_id):
    return db_read_or_seed(f"""
import json
from green_iteso.accounts.models import Clan, ClanMembership
clan = Clan.all_objects.get(pk={clan_id!r})
members = ClanMembership.objects.filter(clan=clan).values_list('user_id', 'role', 'status', 'is_active_private')
print(json.dumps({{'deleted': clan.deleted_at is not None, 'points': clan.total_points,
                  'members': [[str(user), role, status, active] for user, role, status, active in members]}}))
""")


def roster(state):
    return {user: (role, status, active) for user, role, status, active in state["members"]}


def notification_types(page):
    return {entry["notification_type"] for entry in api(page, NOTIFICATIONS)["results"]}


def test_t109_attribution_and_leave(clans):
    actor, screenshot, suffix = clans
    action = lab_action(suffix)
    with (
        actor("T1-09-lider-a", "Líder Robles") as leader_a,
        actor("T1-09-lider-b", "Líder Encinos") as leader_b,
        actor("T1-09-miembro", "Miembro QA") as member,
    ):
        title_a = f"Robles QA {suffix}"
        title_b = f"Encinos QA {suffix}"
        clan_a = _create_clan(leader_a, title_a)
        clan_b = _create_clan(leader_b, title_b)
        join(member, clan_a)
        join(member, clan_b)
        user_id = api(member, PROFILE)["user_id"]
        select(member, clan_a)
        credit(member, action)
        assert (clan_state(clan_a)["points"], clan_state(clan_b)["points"]) == (17, 0)
        select(member, clan_b)
        credit(member, action)
        assert (clan_state(clan_a)["points"], clan_state(clan_b)["points"]) == (17, 17)
        assert roster(clan_state(clan_a))[user_id] == ("MEMBER", "ACCEPTED", False)
        assert roster(clan_state(clan_b))[user_id] == ("MEMBER", "ACCEPTED", True)
        member.reload()
        expect(member.get_by_text("Es tu clan activo", exact=True)).to_be_visible()
        screenshot(member, "T1-09-activo")

        confirm(member, "Salir del clan", path=f"{CLAN_API}{clan_b}/leave/", status=204)
        expect(member.get_by_text(f"Saliste de {title_b}.", exact=True)).to_be_visible()
        screenshot(member, "T1-09-salida")
        previous_membership = roster(clan_state(clan_b)).get(user_id)
        assert api(member, PROFILE)["active_private_clan"] is None
        credit(member, action)
        assert (clan_state(clan_a)["points"], clan_state(clan_b)["points"]) == (17, 17)
        assert api(member, PROFILE)["total_points"] == 51
        assert "CLAN_MEMBER_LEFT" in notification_types(leader_b)
        assert previous_membership is not None and previous_membership[1] != "ACCEPTED", (
            "T2-33 requires an inactive row after leaving; the release deleted it."
        )


def test_t110_transfer_expel_dissolve(clans):
    actor, screenshot, suffix = clans
    action = lab_action(suffix)
    title = f"Guardianes QA {suffix}"
    with (
        actor("T1-10-lider", "Líder Inicial") as leader,
        actor("T1-10-sucesor", "Líder Nuevo") as successor,
        actor("T1-10-miembro", "Miembro QA") as member,
    ):
        clan = _create_clan(leader, title)
        path = f"{CLAN_API}{clan}/"
        join(successor, clan)
        join(member, clan)
        old = api(leader, PROFILE)["user_id"]
        new = api(successor, PROFILE)["user_id"]
        removed = api(member, PROFILE)["user_id"]
        select(member, clan)
        credit(member, action)
        assert clan_state(clan)["points"] == 17

        leader.reload()
        leader.get_by_role("button", name="Transferir liderazgo", exact=True).click()
        dialog = leader.get_by_role("dialog")
        dialog.get_by_role("combobox").click()
        leader.get_by_role("option", name=re.compile(f"Líder Nuevo {suffix}")).click()
        _click_api(leader, dialog.get_by_role("button", name="Transferir liderazgo"), path + "transfer-leadership/", 200)
        expect(leader.get_by_role("button", name="Transferir liderazgo")).to_have_count(0)
        state = roster(clan_state(clan))
        assert state[old][:2] == ("MEMBER", "ACCEPTED")
        assert [user for user, (role, _, _) in state.items() if role == "LEADER"] == [new]
        successor.reload()
        expect(successor.get_by_role("button", name="Disolver clan")).to_be_visible()
        successor.get_by_role("heading", name="Miembros (3)").scroll_into_view_if_needed()
        screenshot(successor, "T1-10-liderazgo")
        assert all("CLAN_LEADER_CHANGED" in notification_types(page) for page in (leader, successor, member))

        confirm(successor, "Expulsar", opener=f"Expulsar a Miembro QA {suffix}", path=path + "kick/", status=204)
        expect(successor.get_by_role("heading", name="Miembros (2)")).to_be_visible()
        screenshot(successor, "T1-10-expulsion")
        assert removed not in roster(clan_state(clan))
        assert clan_state(clan)["points"] == 17
        assert "CLAN_KICKED" in notification_types(member)
        select(successor, clan)

        confirm(successor, "Disolver clan", path=path, status=204, method="DELETE")
        expect(successor.get_by_text(f"{title} se disolvió.", exact=True)).to_be_visible()
        screenshot(successor, "T1-10-disolucion")
        assert clan_state(clan)["deleted"] and clan_state(clan)["points"] == 17
        assert api(successor, PROFILE)["active_private_clan"] is None
        api(leader, path, status=404)
        assert "CLAN_DISSOLVED" in notification_types(leader)
        assert "CLAN_DISSOLVED" not in notification_types(member)
        go_to(leader, "/notifications")
        expect(leader.get_by_text(re.compile(f"{title}.*disuel", re.IGNORECASE)).first).to_be_visible()
        screenshot(leader, "T1-11-notificaciones")


def test_t112_ecological_profile(clans):
    actor, screenshot, suffix = clans
    action = lab_action(suffix)
    campaign = f"Semana Verde QA {suffix}"
    badge = f"Insignia QA {suffix}"
    with actor("T1-12-perfil", "Perfil Ecológico QA") as page:
        go_to(page, "/profile")
        profile = api(page, PROFILE)
        user_id = profile["user_id"]
        db_read_or_seed(f"""
import json
from datetime import timedelta
from django.utils import timezone
from green_iteso.campaigns.models import Campaign, CampaignParticipant
from green_iteso.gamification.models import Badge, UserBadge
now = timezone.now()
for title, status in [({campaign!r}, 'FINISHED'), ('Campaña aún abierta', 'IN_PROGRESS')]:
    campaign = Campaign.objects.create(title=title, scope='GLOBAL', status=status,
        creator_id={user_id!r}, start_date=now - timedelta(days=3), end_date=now - timedelta(days=1))
    CampaignParticipant.objects.create(campaign=campaign, user_id={user_id!r})
badge = Badge.objects.create(name={badge!r}, description='Insignia sintética', points_required=17)
UserBadge.objects.create(user_id={user_id!r}, badge=badge)
print(json.dumps(True))
""")
        bio = "Perfil de prueba de sostenibilidad"
        page.get_by_role("button", name="Editar perfil").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Biografía").fill(bio)
        dialog.get_by_role("button", name=re.compile("^Privado")).click()
        dialog.get_by_role("checkbox", name=re.compile("Notificaciones de impacto")).uncheck()
        with page.expect_response(lambda response: response.url.endswith(PROFILE) and response.request.method == "PATCH") as saved:
            dialog.get_by_role("button", name="Guardar cambios").click()
        assert saved.value.status == 200
        expect(dialog).to_have_count(0)
        credit(page, action)
        page.reload()
        profile = api(page, PROFILE)
        assert profile["total_points"] == 17 and profile["available_points"] == 17
        assert profile["bio"] == bio and profile["preferences"]["notify_impact"] is False
        assert profile["visibility"] == "PRIVATE"
        assert profile["impact_metrics"] == {"co2_kg": "2.500", "water_liters": "3.000", "plastic_kg": "0.500"}
        assert [item["title"] for item in profile["finished_campaigns"]] == [campaign]
        expect(page.get_by_text(bio, exact=True)).to_be_visible()
        expect(page.get_by_text("Puntos Totales", exact=True)).to_be_visible()
        screenshot(page, "T1-12-perfil")
        expect(page.get_by_text(badge, exact=True)).to_be_visible()
        expect(page.get_by_text(campaign, exact=True)).to_be_visible()
        expect(page.get_by_text("Campaña aún abierta", exact=True)).to_have_count(0)
        page.get_by_text(campaign, exact=True).scroll_into_view_if_needed()
        screenshot(page, "T1-12-insignia-campana")
        page.get_by_role("heading", name="Impacto Ambiental Acumulado").scroll_into_view_if_needed()
        screenshot(page, "T1-12-impacto")
        assert profile["level"] is not None and any(entry.get("name") == badge for entry in profile["badges"]), (
            f"T2-20 requires level and earned badges in /profile/me/. "
            f"Actual: level={profile['level']!r}, badges={profile['badges']!r}; the UI showed the badge."
        )


def test_t114_clan_membership_and_discovery_limits(clans):
    actor, screenshot, suffix = clans
    with actor("T1-14-limites", "Límites QA") as page:
        title = f"Catálogo QA {suffix}"
        own_clan = _create_clan(page, f"Líder QA {suffix}")
        profile = api(page, PROFILE)
        user = profile["user_id"]
        assert roster(clan_state(own_clan))[user] == ("LEADER", "ACCEPTED", False)
        api(page, CLAN_API, method="POST", status=400, data={"name": f"Segundo liderazgo {suffix}"})
        targets = db_read_or_seed(f"""
import json
from green_iteso.accounts.models import Clan
rows = Clan.objects.bulk_create([
    Clan(name=f'{title} {{index:02}}', type=Clan.ClanType.PRIVATE)
    for index in range(51)
])
print(json.dumps([str(row.pk) for row in rows[:5]]))
""")
        initial = api(page, f"{CLAN_API}?search=Cat%C3%A1logo%20QA%20{suffix}")
        final = api(page, f"{CLAN_API}?search=Cat%C3%A1logo%20QA%20{suffix}&page=2")
        assert initial["count"] == final["count"] == 51
        assert initial["next"] and not final["next"]
        assert len(initial["results"]) == 50 and len(final["results"]) == 1
        assert not {row["id"] for row in initial["results"]} & {row["id"] for row in final["results"]}
        assert all(title in row["name"] for row in initial["results"] + final["results"])

        for target in targets[:4]:
            api(page, f"{CLAN_API}{target}/join/", method="POST", status=201)
        repeated = f"{CLAN_API}{targets[0]}/join/"
        api(page, repeated, method="POST", status=400)
        assert len([entry for entry in clan_state(targets[0])["members"] if entry[0] == user]) == 1
        api(page, f"{CLAN_API}{targets[4]}/join/", method="POST", status=400)
        assert user not in roster(clan_state(targets[4]))
        current_clan = api(page, PROFILE)["institutional_clan"]
        assert current_clan is not None
        assert current_clan["id"] == profile["institutional_clan"]["id"]

        go_to(page, "/clans")
        search = page.get_by_label("Buscar clanes por nombre")
        search.fill(title)
        expect(page.get_by_role("link", name=re.compile(title)).first).to_be_visible()
        screenshot(page, "T1-14-busqueda")
