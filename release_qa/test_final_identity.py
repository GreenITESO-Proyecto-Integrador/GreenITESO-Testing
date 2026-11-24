"""Team 1 peer acceptance tests for the isolated GreenITESO release stack."""

import os
import re
import struct
import uuid
import zlib
from pathlib import Path

import pytest
from playwright.sync_api import expect

from src.actions import Auth_actions
from src.configs import environment
from src.utils.auth import get_session, inject_session
from src.utils.common_actions import go_to, logout
from src.utils.locators import Locs

pytestmark = [pytest.mark.full, pytest.mark.sanity]
INSTITUTIONAL = "/api/v1/clans/institutional-clan/"
PROFILE = "/api/v1/profile/me/"
ACCESS = "greeniteso.access_token"
REFRESH = "greeniteso.refresh_token"
EVIDENCE = os.environ.get("GREENITESO_IDENTITY_EVIDENCE")


@pytest.fixture(autouse=True)
def isolated_stack():
    # This file provisions synthetic users and writes to their profiles.
    assert environment.BASE_URL == environment.API_BASE_URL == "http://localhost:8080"
    assert environment.AUTH_MODE == "mock"
    assert not environment.E2E_CLEANUP


@pytest.fixture
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": (
            {"width": 390, "height": 844}
            if os.environ.get("GREENITESO_IDENTITY_MOBILE") == "1"
            else {"width": 1440, "height": 900}
        ),
    }


@pytest.fixture
def journey(browser, browser_context_args, request):
    case = request.node.name.split("_")[1].upper().replace("T1", "T1-")
    dest = Path(EVIDENCE, case) if EVIDENCE else None
    if dest:
        dest.mkdir(parents=True, exist_ok=True)
    options = dict(browser_context_args)
    if dest and os.environ.get("GREENITESO_IDENTITY_VIDEO") == "1":
        options.update(record_video_dir=dest, record_video_size={"width": 1440, "height": 900})
    context = browser.new_context(**options)
    page = context.new_page()
    try:
        yield page, dest
    finally:
        try:
            if dest and not page.is_closed():
                page.screenshot(path=dest / "resultado.png", timeout=5000, animations="disabled")
        finally:
            video = page.video
            context.close()
            if dest and video:
                video.path().replace(dest / "recorrido.webm")


def learner(page, *, onboard=True, visibility="PUBLIC"):
    alias = f"qa-identity-{uuid.uuid4().hex[:9]}"
    session = get_session(page.request, f"{alias}@iteso.mx")
    if onboard:
        choices = page.request.get(INSTITUTIONAL + "careers/", headers=auth_headers(session))
        assert choices.ok, f"Career catalogue returned {choices.status}"
        assigned = page.request.post(
            INSTITUTIONAL,
            headers=auth_headers(session),
            data={
                "career": choices.json()["careers"][0],
                "nickname": alias,
                "visibility": visibility,
            },
        )
        assert assigned.ok, f"Synthetic onboarding fixture returned {assigned.status}"
    inject_session(page, session)
    return session


def auth_headers(session):
    return {"Authorization": f"Bearer {session['access']}"}


def hold_for_recording(page):
    if EVIDENCE and os.environ.get("GREENITESO_IDENTITY_VIDEO") == "1":
        page.wait_for_timeout(900)


def assert_profile(page):
    expect(page.locator(Locs.PROFILE_NAME_TITLE)).to_be_visible()
    expect(page).to_have_url(re.compile(r"/profile$"))


def synthetic_png():
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))

    color = b"\x11\xcc\x91"
    stripe = b"\x16\x4c\x40"
    scanlines = b"".join(
        b"\x00" + b"".join(stripe if abs(x - y) < 8 else color for x in range(96))
        for y in range(96)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 96, 96, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines))
        + chunk(b"IEND", b"")
    )


def test_t101_login_screen_and_synthetic_session(journey):
    page, dest = journey
    assert Auth_actions.test_00_01_001_checkLoginScreen(page)
    if dest:
        page.screenshot(path=dest / "pantalla-institucional.png", animations="disabled")
    hold_for_recording(page)
    learner(page)
    go_to(page, "/profile")
    assert_profile(page)
    page.reload(wait_until="domcontentloaded")
    assert_profile(page)
    hold_for_recording(page)


def test_t102_protected_routes_and_logout(journey):
    page, _ = journey
    assert Auth_actions.test_00_01_004_checkProtectedRouteRedirect(page)
    hold_for_recording(page)
    learner(page)
    go_to(page, "/profile")
    assert_profile(page)
    hold_for_recording(page)
    logout(page)
    expect(page).to_have_url(re.compile(r"/login$"))
    expect(page.locator(Locs.LOGIN_BUTTON)).to_be_visible()
    go_to(page, "/profile")
    expect(page).to_have_url(re.compile(r"/login$"))
    hold_for_recording(page)


def test_t103_two_refresh_token_rotations(journey):
    page, dest = journey
    learner(page)
    go_to(page, "/profile")
    assert_profile(page)
    statuses = []
    for _ in range(2):
        previous_token = page.evaluate("(key) => sessionStorage.getItem(key)", REFRESH)
        assert previous_token is not None, "The synthetic session must have a refresh token"
        page.evaluate("(key) => sessionStorage.removeItem(key)", ACCESS)
        with page.expect_response(
            lambda response: response.url.endswith("/api/v1/auth/refresh/") and response.request.method == "POST"
        ) as renewed:
            page.reload(wait_until="domcontentloaded")
        statuses.append(renewed.value.status)
        assert renewed.value.status == 200, f"Refresh {len(statuses)} returned {renewed.value.status}"
        assert_profile(page)
        assert page.evaluate("([key, prior]) => sessionStorage.getItem(key) !== prior", [REFRESH, previous_token])
        hold_for_recording(page)
    if dest:
        (dest / "renovaciones.txt").write_text(f"Renovación 1: HTTP {statuses[0]}\nRenovación 2: HTTP {statuses[1]}\n")


def test_t104_student_denied_admin_view_and_operation(journey):
    page, dest = journey
    session = learner(page)
    go_to(page, "/audit")
    expect(page.locator(Locs.ACCESS_DENIED_TITLE)).to_be_visible()
    expect(page).to_have_url(re.compile(r"/audit$"))
    directory = page.request.get("/api/v1/users/", headers=auth_headers(session))
    assert directory.status == 403, f"Admin directory returned {directory.status} for a student"
    if dest:
        (dest / "permisos.txt").write_text(f"Directorio administrativo como estudiante: HTTP {directory.status}\n")
    hold_for_recording(page)


def test_t105_first_login_validates_and_persists_institutional_membership(journey):
    page, dest = journey
    session = learner(page, onboard=False)
    go_to(page, "/clans")
    form = page.get_by_role("dialog", name="Completa tu perfil")
    expect(form).to_be_visible()
    career = form.get_by_label("Carrera")
    expect(career).to_be_enabled()
    invalid = page.request.post(
        INSTITUTIONAL, headers=auth_headers(session), data={"career": "Carrera QA inexistente"}
    )
    assert invalid.status == 400, f"Unknown career returned {invalid.status}"
    form.get_by_role("button", name="Continuar", exact=True).click()
    expect(form.get_by_text("Elige tu carrera.", exact=True)).to_be_visible()
    if dest:
        page.screenshot(path=dest / "carrera-obligatoria.png")
    hold_for_recording(page)
    chosen = career.locator("option:not([value=''])").first.get_attribute("value")
    assert chosen
    career.select_option(chosen)
    alias = session["user"]["email"].split("@", 1)[0]
    form.get_by_label("Nickname (opcional)").fill(alias)
    with page.expect_response(
        lambda response: response.url.endswith(INSTITUTIONAL) and response.request.method == "POST"
    ) as submitted:
        form.get_by_role("button", name="Continuar", exact=True).click()
    assert submitted.value.status == 200, f"Onboarding returned {submitted.value.status}"
    expect(form).to_be_hidden()
    expect(page.get_by_text(chosen, exact=True).first).to_be_visible()
    page.reload(wait_until="domcontentloaded")
    expect(page.get_by_text(chosen, exact=True).first).to_be_visible()
    persisted = page.request.get(INSTITUTIONAL, headers=auth_headers(session))
    assert persisted.ok, f"Reading institutional membership returned {persisted.status}"
    values = persisted.json()
    assert values["career"] == chosen and values["nickname"] == alias
    assert values["institutional_clan"]["name"] == chosen
    assert values["onboarding_completed_at"]
    hold_for_recording(page)


def test_t108_private_avatar_upload_persists_and_stays_private(journey):
    page, dest = journey
    owner = learner(page, visibility="PRIVATE")
    go_to(page, "/profile")
    assert_profile(page)
    page.get_by_role("button", name="Editar perfil").click()
    editor = page.get_by_role("dialog")
    expect(editor).to_be_visible()
    editor.get_by_test_id("profile-avatar-file").set_input_files(
        {"name": "avatar-sintetico.png", "mimeType": "image/png", "buffer": synthetic_png()}
    )
    expect(editor.get_by_text("Se subirá «avatar-sintetico.png» al guardar.", exact=True)).to_be_visible()
    hold_for_recording(page)
    editor.get_by_role("button", name="Guardar cambios", exact=True).click()
    expect(editor.get_by_text("¡Perfil actualizado correctamente!", exact=True)).to_be_visible()
    expect(editor).to_be_hidden()
    avatar = page.locator("main img[src*='/api/v1/avatars/']").first
    expect(avatar).to_be_visible()
    go_to(page, "/clans")
    go_to(page, "/profile")
    expect(avatar).to_be_visible()
    page.reload(wait_until="domcontentloaded")
    expect(avatar).to_be_visible()
    assert avatar.evaluate("image => image.complete && image.naturalWidth > 0")
    profile = page.request.get(PROFILE, headers=auth_headers(owner))
    assert profile.ok, f"Owner profile returned {profile.status}"
    assert profile.json()["visibility"] == "PRIVATE"
    private_image = f"/api/v1/avatars/{owner['user']['id']}/"
    visitor_context = page.context.browser.new_context(base_url=environment.BASE_URL, viewport=page.viewport_size)
    visitor_page = visitor_context.new_page()
    visitor_session = learner(visitor_page)
    visitor = visitor_page.request.get(private_image, headers=auth_headers(visitor_session))
    assert visitor.status == 404, f"Unsigned private avatar returned {visitor.status} to another student"
    membership = page.request.get(INSTITUTIONAL, headers=auth_headers(owner))
    assert membership.ok, f"Owner institutional assignment returned {membership.status}"
    clan_id = membership.json()["institutional_clan"]["id"]
    clan_path = f"/clans/{clan_id}"
    roster = visitor_page.request.get(f"/api/v1{clan_path}/", headers=auth_headers(visitor_session))
    assert roster.ok, f"Visitor's clan roster returned {roster.status}"
    member = next(row for row in roster.json()["members"] if row["user_id"] == owner["user"]["id"])
    assert not member["avatar_url"], "The private photo must be absent from the other student's roster data"
    go_to(visitor_page, clan_path)
    members = visitor_page.locator("section[aria-labelledby='clan-members-title']")
    expect(members).to_be_visible()
    more = members.get_by_role("button", name=re.compile("Mostrar todos"))
    if more.count():
        more.click()
    alias = owner["user"]["email"].split("@", 1)[0]
    listed = members.get_by_role("listitem").filter(has_text=alias)
    expect(listed).to_be_visible()
    expect(listed.locator("img[src*='/api/v1/avatars/']")).to_have_count(0)
    if dest:
        listed.scroll_into_view_if_needed()
        visitor_page.screenshot(path=dest / "vista-de-otro-estudiante.png", animations="disabled")
    visitor_context.close()
    if dest:
        (dest / "visibilidad.txt").write_text(
            f"La foto persistió para su propietario. Consulta de otro estudiante sin firma: HTTP {visitor.status}.\n"
        )
    hold_for_recording(page)
