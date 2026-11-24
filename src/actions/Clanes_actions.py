"""Acciones del módulo 11 · Clanes (tests/Clanes/test_Clanes.py).

001–011 cubren TC-11-002 y TC-11-003 (crear un clan y validar el nombre).
012–025 cubren el resto del plan: TC-11-001 y TC-11-004 a TC-11-016.
EE = 00 es provisional hasta que se haga el reparto de equipos.

Reglas del producto que condicionan el diseño (backend: clans/services.py::create_private_clan):
- BR-04: un usuario lidera un solo clan a la vez. Por eso cada test que crea un clan lo disuelve
  por API al terminar (``finally``); si no, el siguiente test chocaría con "Ya eres líder".
  ``cleanup_run`` disuelve al final de la corrida lo que se les haya escapado.
- El usuario ``leader`` (``_CREATOR_ROLE``) no debe liderar ningún clan al iniciar el módulo.
- El formulario limita el nombre a 50 caracteres y la descripción a 100 (field-limits.ts), aunque
  el backend acepte 100 en el nombre.
"""

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, Route

from src.configs import environment as env
from src.utils.auth import get_session
from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import (
    current_path,
    locator_has_visible_match,
    wait_for_app_ready,
    wait_until,
)
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.test_data import unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_SUBMIT_TIMEOUT = 20_000

# Quien crea los clanes por la UI, y quien crea el clan "ocupante" en el test de nombre duplicado.
_CREATOR_ROLE = "leader"
_OTHER_ROLE = "student"

_CLANS_PATH = "/api/v1/clans/"
_CLAN_PROFILE_PATH = re.compile(r"/clans/[0-9a-fA-F-]{36}")
_NAME_MAX_LENGTH = 50
_DESCRIPTION_MAX_LENGTH = 100
_DESCRIPTION = "Clan creado por las pruebas E2E"

_PUBLIC_LABEL = "Pública"
_PRIVATE_LABEL = "Solo invitación"
_EMPTY_NAME_ERROR = "Escribe un nombre para el clan."
# Un nombre repetido muestra este texto. Un clan de carrera muestra el mensaje propio.
_NAME_REJECTION_ERROR = "No repitas la misma acción en una campaña."
_RESERVED_NAME_ERROR = "Ese nombre es de un clan de carrera. Elige otro."
_ALREADY_LEADER_ERROR = "Ya eres líder de un clan. Solo puedes liderar uno a la vez."
_RESERVED_NAME = "Ingeniería en Mecatrónica"
_MISSING_CLAN_ID = "00000000-0000-4000-8000-000000000099"
_SHORT_CODE = "NO"
_INVALID_CODE_ERROR = "El código tiene 8 caracteres, por ejemplo ABCD-1234."
_DIRECTORY_LIST = re.compile(r"/api/v1/clans/\?")


# --- privadas: navegación y formulario ------------------------------------------------------

def _open_clans(page: Page, role: str = _CREATOR_ROLE) -> None:
    login_as(page, role)
    go_to(page, "/clans")
    wait_for_app_ready(page)
    page.locator(Locs.CLANS_CREATE_BUTTON).first.wait_for(state="visible")


def _open_create_dialog(page: Page) -> None:
    click_robust(page, Locs.CLANS_CREATE_BUTTON)
    page.locator(Locs.CREATE_CLAN_DIALOG).first.wait_for(state="visible", timeout=_SHORT_TIMEOUT)


def _is_dialog_open(page: Page) -> bool:
    return locator_has_visible_match(page.locator(Locs.CREATE_CLAN_DIALOG))


def _fill_form(page: Page, name: str, *, description: str | None = None, privacy: str | None = None) -> None:
    page.locator(Locs.CLAN_NAME_INPUT).fill(name)
    if description is not None:
        page.locator(Locs.CLAN_DESCRIPTION_INPUT).fill(description)
    if privacy is not None:
        click_robust(page, Locs.clan_privacy_chip_with_text(privacy))


def _submit_form(page: Page) -> None:
    click_robust(page, Locs.CLAN_FORM_SUBMIT)


def _form_error_text(page: Page) -> str:
    """Return the visible error messages of the create dialog (name field and general alert)."""
    return " | ".join(
        locator.inner_text().strip()
        for locator in (page.locator(Locs.CLAN_NAME_FIELD_ERROR), page.locator(Locs.CLAN_FORM_ALERT))
        if locator.count()
    )


def _clan_id_from_url(page: Page) -> str | None:
    path = current_path(page)
    return path.rsplit("/", 1)[-1] if _CLAN_PROFILE_PATH.fullmatch(path) else None


def _wait_for_submit_result(page: Page) -> str:
    """Wait until the form either navigated to the new clan ("created") or showed an error ("error")."""
    outcome: list[str] = []

    def _settled() -> bool:
        if _clan_id_from_url(page):
            outcome.append("created")
        elif locator_has_visible_match(page.locator(Locs.CLAN_FORM_ALERT)) or locator_has_visible_match(
            page.locator(Locs.CLAN_NAME_FIELD_ERROR)
        ):
            outcome.append("error")
        return bool(outcome)

    if not wait_until(_settled, page, timeout=_SUBMIT_TIMEOUT, poll_ms=150):
        raise RuntimeError(f"Crear clan no respondió en {_SUBMIT_TIMEOUT} ms (URL: {page.url})")
    return outcome[0]


def _create_clan_via_ui(
    page: Page, name: str, *, description: str | None = None, privacy: str | None = None
) -> str:
    """Create a clan with the dialog and return its id; raise with the form's message if it was refused."""
    _open_create_dialog(page)
    _fill_form(page, name, description=description, privacy=privacy)
    _submit_form(page)
    if _wait_for_submit_result(page) == "error":
        raise RuntimeError(
            f"No se pudo crear el clan {name!r}: {_form_error_text(page)!r}. "
            f"¿El usuario {env.TEST_USERS[_CREATOR_ROLE]} ya lidera un clan?"
        )
    clan_id = _clan_id_from_url(page)
    logger.info("Clan creado por la UI: %s (%s)", name, clan_id)
    return clan_id  # type: ignore[return-value]


# --- privadas: API (preparar y deshacer datos) ----------------------------------------------

def _auth_headers(page: Page, role: str) -> dict[str, str]:
    access = get_session(page.request, env.TEST_USERS[role])["access"]
    return {"Authorization": f"Bearer {access}"}


def _create_clan_via_api(page: Page, role: str, name: str, *, privacy: str = "PUBLIC") -> str:
    response = page.request.post(
        env.API_BASE_URL.rstrip("/") + _CLANS_PATH,
        headers=_auth_headers(page, role),
        data={"name": name, "description": _DESCRIPTION, "privacy": privacy},
    )
    if not response.ok:
        raise RuntimeError(
            f"No se pudo preparar el clan {name!r} con {env.TEST_USERS[role]} ({response.status}): "
            f"{response.text()}"
        )
    return str(response.json()["id"])


def _dissolve_clan(page: Page, clan_id: str | None, role: str = _CREATOR_ROLE) -> None:
    """Dissolve a clan the test created so the user can lead another one (BR-04)."""
    if not clan_id:
        return
    try:
        response = page.request.delete(
            f"{env.API_BASE_URL.rstrip('/')}{_CLANS_PATH}{clan_id}/", headers=_auth_headers(page, role)
        )
        if response.ok or response.status == 404:
            logger.debug("Clan %s disuelto", clan_id)
        else:
            logger.warning("No se pudo disolver el clan %s (%s); lo hará cleanup_run", clan_id, response.status)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo disolver el clan %s (%s); lo hará cleanup_run", clan_id, exc)


def _join_clan_via_api(page: Page, role: str, clan_id: str) -> None:
    """Join as `role`. A public clan accepts at once; an invite-only clan files a pending request."""
    response = page.request.post(
        f"{env.API_BASE_URL.rstrip('/')}{_CLANS_PATH}{clan_id}/join/",
        headers=_auth_headers(page, role),
    )
    if not response.ok:
        raise RuntimeError(
            f"No se pudo unir a {env.TEST_USERS[role]} al clan {clan_id} ({response.status}): {response.text()}"
        )


def _open_clan_profile(page: Page, clan_id: str, role: str) -> None:
    login_as(page, role)
    go_to(page, f"/clans/{clan_id}")
    wait_for_app_ready(page)


def _notice_has(page: Page, text: str, *, timeout: int = _SUBMIT_TIMEOUT) -> bool:
    notice = page.locator(Locs.CLAN_NOTICE).filter(has_text=text)
    if locator_has_visible_match(notice, timeout=timeout):
        return True
    logger.error("No apareció el aviso %r", text)
    return False


def _confirm_dialog(page: Page, label: str) -> None:
    click_robust(page, Locs.dialog_button_with_text(label))


def _expect_hidden(page: Page, selector: str, what: str, *, timeout: int = _SUBMIT_TIMEOUT) -> bool:
    hidden = wait_until(
        lambda: not locator_has_visible_match(page.locator(selector), timeout=300),
        page,
        timeout=timeout,
    )
    if hidden:
        return True
    logger.error("Sigue visible: %s", what)
    return False


_MAX_DIRECTORY_PAGES = 30


def _reveal_clan_card(page: Page, name: str) -> bool:
    """Show the clan card by paging Explorar clanes. The search box does not filter this list."""
    card = page.locator(Locs.clan_card_with_name(name))
    for page_number in range(1, _MAX_DIRECTORY_PAGES + 1):
        if locator_has_visible_match(card, timeout=_SHORT_TIMEOUT):
            return True
        nxt = page.locator(Locs.CLANS_DIRECTORY_NEXT).first
        if nxt.count() == 0 or not nxt.is_enabled():
            logger.error("La tarjeta del clan %r no está en las páginas de Explorar clanes", name)
            return False
        logger.debug("Tarjeta de %r no está en la página %s; se avanza", name, page_number)
        nxt.click()
    logger.error("La tarjeta del clan %r no apareció en %s páginas", name, _MAX_DIRECTORY_PAGES)
    return False


@contextmanager
def _directory_down(page: Page) -> Iterator[None]:
    """Fail GET /api/v1/clans/?… until the caller leaves this block."""

    def _reject(route: Route) -> None:
        if route.request.method == "GET" and _DIRECTORY_LIST.search(route.request.url):
            route.fulfill(status=500, content_type="application/json", body='{"detail":"e2e"}')
            return
        route.fallback()

    page.route("**/api/v1/clans/**", _reject)
    try:
        yield
    finally:
        page.unroute("**/api/v1/clans/**", _reject)


def _with_clan(page: Page, role: str, *, privacy: str = "PUBLIC") -> tuple[str, str]:
    """Create a marked clan by API and return (name, id). The caller dissolves it."""
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    return name, _create_clan_via_api(page, role, name, privacy=privacy)


def _run_creating(page: Page, name: str, check: Callable[[str], bool], **form: str | None) -> bool:
    """Create a clan by the UI, run `check(clan_id)` on its page and always dissolve it afterwards."""
    clan_id = _create_clan_via_ui(page, name, **form)
    try:
        return check(clan_id)
    finally:
        _dissolve_clan(page, clan_id)


# --- privadas: verificaciones ---------------------------------------------------------------

def _expect_visible(page: Page, selector: str, what: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    if locator_has_visible_match(page.locator(selector), timeout=timeout):
        return True
    logger.error("No se ve: %s", what)
    return False


def _clan_profile_matches(
    page: Page, name: str, *, description: str | None, privacy_label: str, clan_id: str
) -> bool:
    if _clan_id_from_url(page) != clan_id:
        logger.error("Se esperaba el perfil del clan %s, la URL es %s", clan_id, page.url)
        return False
    if not _expect_visible(page, Locs.CLAN_PROFILE_TITLE, "el título del perfil del clan"):
        return False
    title = page.locator(Locs.CLAN_PROFILE_TITLE).first.inner_text().strip()
    if title != name:
        logger.error("El perfil muestra %r, se esperaba %r", title, name)
        return False
    banner = f"Creaste {name}. ¡Ya eres su líder!"
    if not _expect_visible(page, Locs.CLAN_SUCCESS_BANNER, f"el aviso '{banner}'"):
        return False
    banner_text = page.locator(Locs.CLAN_SUCCESS_BANNER).first.inner_text()
    if banner not in banner_text:
        logger.error("El aviso dice %r, se esperaba %r", banner_text, banner)
        return False
    if description and not _expect_visible(page, f"//main//p[normalize-space(.)='{description}']", "la descripción"):
        return False
    if not _expect_visible(page, Locs.badge_with_text(privacy_label), f"la insignia '{privacy_label}'"):
        return False
    if not _expect_visible(page, Locs.CLAN_PROFILE_MEMBER_COUNT, "el contador de miembros"):
        return False
    members = page.locator(Locs.CLAN_PROFILE_MEMBER_COUNT).first.inner_text().strip()
    if members != "1 miembro":
        logger.error("El clan nuevo muestra %r, se esperaba '1 miembro' (solo el líder)", members)
        return False
    # El creador queda como líder: ve las acciones exclusivas del líder.
    leader_buttons = [(Locs.CLAN_PROFILE_DISSOLVE_BUTTON, "Disolver clan")]
    if privacy_label == _PRIVATE_LABEL:
        leader_buttons.append((Locs.CLAN_PROFILE_INVITE_CODE_BUTTON, "Invitar con código"))
    return all(_expect_visible(page, selector, f"el botón '{label}'") for selector, label in leader_buttons)


def _expect_form_error(page: Page, message: str) -> bool:
    """The create dialog stays open, shows `message` and no clan was created."""
    result = _wait_for_submit_result(page)
    clan_id = _clan_id_from_url(page)
    if result == "created":
        logger.error("Se creó un clan que debió ser rechazado (%s); se disuelve", clan_id)
        _dissolve_clan(page, clan_id)
        return False
    shown = _form_error_text(page)
    if message not in shown:
        logger.error("Se esperaba el error %r, el formulario muestra %r", message, shown)
        return False
    if not _is_dialog_open(page):
        logger.error("El diálogo se cerró aunque la creación fue rechazada")
        return False
    return True


# --- tests ----------------------------------------------------------------------------------

def test_00_11_001_checkSetUp(page: Page) -> bool:
    _open_clans(page)
    _open_create_dialog(page)
    required = [
        (Locs.CLAN_NAME_INPUT, "el campo Nombre"),
        (Locs.CLAN_DESCRIPTION_INPUT, "el campo Descripción"),
        (Locs.clan_privacy_chip_with_text(_PUBLIC_LABEL), "la opción Pública"),
        (Locs.clan_privacy_chip_with_text(_PRIVATE_LABEL), "la opción Solo invitación"),
        (Locs.CLAN_FORM_SUBMIT, "el botón Crear clan"),
        (Locs.CLAN_FORM_CANCEL, "el botón Cancelar"),
    ]
    if not all(_expect_visible(page, selector, what) for selector, what in required):
        return False
    public_chip = page.locator(Locs.clan_privacy_chip_with_text(_PUBLIC_LABEL)).first
    if public_chip.get_attribute("aria-pressed") != "true":
        logger.error("La privacidad por defecto debería ser Pública")
        return False
    return True


def test_00_11_002_checkCreatePublicClan(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)
    return _run_creating(
        page,
        name,
        lambda clan_id: _clan_profile_matches(
            page, name, description=_DESCRIPTION, privacy_label=_PUBLIC_LABEL, clan_id=clan_id
        ),
        description=_DESCRIPTION,
        privacy=_PUBLIC_LABEL,
    )


def test_00_11_003_checkCreatePrivateInviteClan(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)
    return _run_creating(
        page,
        name,
        lambda clan_id: _clan_profile_matches(
            page, name, description=_DESCRIPTION, privacy_label=_PRIVATE_LABEL, clan_id=clan_id
        ),
        description=_DESCRIPTION,
        privacy=_PRIVATE_LABEL,
    )


def test_00_11_004_checkCreateClanWithoutDescription(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)
    return _run_creating(
        page,
        name,
        lambda clan_id: _clan_profile_matches(
            page, name, description=None, privacy_label=_PUBLIC_LABEL, clan_id=clan_id
        ),
    )


def test_00_11_005_checkCreatedClanListedInDirectory(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)

    def _listed(_clan_id: str) -> bool:
        go_to(page, "/clans")
        wait_for_app_ready(page)
        page.locator(Locs.CLANS_SEARCH_INPUT).fill(name)
        return _expect_visible(
            page, Locs.clan_card_with_name(name), f"la tarjeta del clan {name!r} en 'Explorar clanes'",
            timeout=_SHORT_TIMEOUT * 2,
        )

    return _run_creating(page, name, _listed, description=_DESCRIPTION, privacy=_PUBLIC_LABEL)


def test_00_11_006_checkNameRequired(page: Page) -> bool:
    _open_clans(page)
    _open_create_dialog(page)
    for typed in ("", "   "):  # vacío y solo espacios: el frontend recorta el nombre
        page.locator(Locs.CLAN_NAME_INPUT).fill(typed)
        _submit_form(page)
        if not _expect_visible(page, Locs.CLAN_NAME_FIELD_ERROR, f"el error de nombre con {typed!r}"):
            return False
        shown = page.locator(Locs.CLAN_NAME_FIELD_ERROR).first.inner_text().strip()
        if shown != _EMPTY_NAME_ERROR:
            logger.error("Con %r se esperaba %r, se muestra %r", typed, _EMPTY_NAME_ERROR, shown)
            return False
        clan_id = _clan_id_from_url(page)
        if clan_id:
            logger.error("Se creó un clan con nombre vacío (%s); se disuelve", clan_id)
            _dissolve_clan(page, clan_id)
            return False
    return _is_dialog_open(page)


def test_00_11_007_checkFieldLengthLimits(page: Page) -> bool:
    _open_clans(page)
    _open_create_dialog(page)
    # press_sequentially teclea carácter por carácter, así que el maxlength del input sí aplica.
    page.locator(Locs.CLAN_NAME_INPUT).press_sequentially("N" * (_NAME_MAX_LENGTH + 10))
    page.locator(Locs.CLAN_DESCRIPTION_INPUT).press_sequentially("D" * (_DESCRIPTION_MAX_LENGTH + 20))
    name_length = len(page.locator(Locs.CLAN_NAME_INPUT).input_value())
    description_length = len(page.locator(Locs.CLAN_DESCRIPTION_INPUT).input_value())
    if name_length != _NAME_MAX_LENGTH:
        logger.error("El nombre admitió %s caracteres, el límite es %s", name_length, _NAME_MAX_LENGTH)
        return False
    if description_length != _DESCRIPTION_MAX_LENGTH:
        logger.error(
            "La descripción admitió %s caracteres, el límite es %s", description_length, _DESCRIPTION_MAX_LENGTH
        )
        return False
    return _expect_visible(
        page, Locs.char_counter_with_text(f"{_NAME_MAX_LENGTH}/{_NAME_MAX_LENGTH}"), "el contador del nombre"
    ) and _expect_visible(
        page,
        Locs.char_counter_with_text(f"{_DESCRIPTION_MAX_LENGTH}/{_DESCRIPTION_MAX_LENGTH}"),
        "el contador de la descripción",
    )


def test_00_11_008_checkDuplicateNameRejected(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    # El clan ocupante lo crea otro usuario por API: el líder del test no puede liderar dos (BR-04).
    existing_id = _create_clan_via_api(page, _OTHER_ROLE, name)
    try:
        _open_clans(page)
        _open_create_dialog(page)
        _fill_form(page, name)
        _submit_form(page)
        return _expect_form_error(page, _NAME_REJECTION_ERROR)
    finally:
        _dissolve_clan(page, existing_id, _OTHER_ROLE)


def test_00_11_009_checkReservedCareerNameRejected(page: Page) -> bool:
    _open_clans(page)
    _open_create_dialog(page)
    _fill_form(page, _RESERVED_NAME)
    _submit_form(page)
    return _expect_form_error(page, _RESERVED_NAME_ERROR)


def test_00_11_010_checkSecondLeadershipRejected(page: Page) -> bool:
    first = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    second = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)
    first_id = _create_clan_via_ui(page, first, description=_DESCRIPTION)
    try:
        go_to(page, "/clans")
        wait_for_app_ready(page)
        _open_create_dialog(page)
        _fill_form(page, second)
        _submit_form(page)
        return _expect_form_error(page, _ALREADY_LEADER_ERROR)
    finally:
        _dissolve_clan(page, first_id)


def test_00_11_011_checkCancelDoesNotCreateClan(page: Page) -> bool:
    name = unique_name("Clan", max_length=_NAME_MAX_LENGTH)
    _open_clans(page)
    _open_create_dialog(page)
    _fill_form(page, name, description=_DESCRIPTION)
    click_robust(page, Locs.CLAN_FORM_CANCEL)
    if not wait_until(lambda: not _is_dialog_open(page), page, timeout=_SHORT_TIMEOUT):
        logger.error("El diálogo no se cerró al cancelar")
        return False
    if _clan_id_from_url(page):
        logger.error("Cancelar llevó a un perfil de clan (%s)", page.url)
        return False
    page.locator(Locs.CLANS_SEARCH_INPUT).fill(name)
    if locator_has_visible_match(page.locator(Locs.clan_card_with_name(name)), timeout=_SHORT_TIMEOUT):
        logger.error("Existe un clan %r aunque se canceló la creación", name)
        return False
    return True


def test_00_11_012_checkSearchClansByName(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _open_clans(page)
        return _reveal_clan_card(page, name)
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_013_checkOpenClanProfile(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _open_clans(page)
        if not _reveal_clan_card(page, name):
            return False
        click_robust(page, Locs.clan_card_with_name(name))
        if _clan_id_from_url(page) != clan_id:
            logger.error("La tarjeta no abrió el clan %s (URL: %s)", clan_id, page.url)
            return False
        if not _expect_visible(page, Locs.CLAN_PROFILE_TITLE, "el título del perfil"):
            return False
        title = page.locator(Locs.CLAN_PROFILE_TITLE).first.inner_text().strip()
        if title != name:
            logger.error("El perfil muestra %r, se esperaba %r", title, name)
            return False
        return all(
            (
                _expect_visible(page, f"//main//p[normalize-space(.)='{_DESCRIPTION}']", "la descripción"),
                _expect_visible(page, Locs.badge_with_text(_PUBLIC_LABEL), f"la insignia '{_PUBLIC_LABEL}'"),
                _expect_visible(page, Locs.member_count_with_text("1 miembro"), "el contador '1 miembro'"),
            )
        )
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_014_checkJoinPublicClan(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _open_clan_profile(page, clan_id, _OTHER_ROLE)
        click_robust(page, Locs.CLAN_JOIN_BUTTON)
        return _notice_has(page, f"Te uniste a {name}") and _expect_visible(
            page, Locs.member_count_with_text("2 miembros"), "'2 miembros'", timeout=_SUBMIT_TIMEOUT
        )
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_015_checkLeaveClan(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _OTHER_ROLE)
        click_robust(page, Locs.CLAN_LEAVE_BUTTON)
        _confirm_dialog(page, "Salir del clan")
        if not wait_until(lambda: current_path(page) == "/clans", page, timeout=_SUBMIT_TIMEOUT):
            logger.error("Salir no volvió a /clans (URL: %s)", page.url)
            return False
        return _notice_has(page, f"Saliste de {name}")
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_016_checkSetActiveClan(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _OTHER_ROLE)
        click_robust(page, Locs.CLAN_SET_ACTIVE_BUTTON)
        return _notice_has(page, f"{name} es ahora tu clan activo.") and _expect_visible(
            page, Locs.CLAN_ACTIVE_BADGE, "'Es tu clan activo'", timeout=_SUBMIT_TIMEOUT
        )
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_017_checkCopyInviteLink(page: Page) -> bool:
    _name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        try:
            page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("El navegador no concedió el portapapeles: %s", exc)
        _open_clan_profile(page, clan_id, _CREATOR_ROLE)
        click_robust(page, Locs.CLAN_COPY_LINK_BUTTON)
        if _notice_has(page, "Enlace copiado", timeout=_SHORT_TIMEOUT):
            return True
        alert = page.locator("//*[@role='alert']").filter(has_text=f"/clans/{clan_id}")
        if locator_has_visible_match(alert, timeout=_SHORT_TIMEOUT):
            return True
        logger.error("Ni el aviso ni el enlace manual muestran /clans/%s", clan_id)
        return False
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_018_checkRequestJoinByInviteLink(page: Page) -> bool:
    _name, clan_id = _with_clan(page, _CREATOR_ROLE, privacy="PRIVATE_INVITE")
    try:
        _open_clan_profile(page, clan_id, _OTHER_ROLE)
        if not _expect_visible(page, Locs.CLAN_NOT_FOUND_TITLE, "'No encontramos este clan'", timeout=_SUBMIT_TIMEOUT):
            return False
        click_robust(page, Locs.CLAN_REQUEST_JOIN_BUTTON)
        return _expect_visible(page, Locs.CLAN_REQUEST_SENT_TITLE, "'Solicitud enviada'", timeout=_SUBMIT_TIMEOUT)
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_019_checkAcceptJoinRequest(page: Page) -> bool:
    _name, clan_id = _with_clan(page, _CREATOR_ROLE, privacy="PRIVATE_INVITE")
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _CREATOR_ROLE)
        click_robust(page, Locs.CLAN_ACCEPT_REQUEST_BUTTON)
        return _notice_has(page, "ya es parte del clan") and _expect_visible(
            page, Locs.member_count_with_text("2 miembros"), "'2 miembros'", timeout=_SUBMIT_TIMEOUT
        )
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_020_checkRejectJoinRequest(page: Page) -> bool:
    _name, clan_id = _with_clan(page, _CREATOR_ROLE, privacy="PRIVATE_INVITE")
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _CREATOR_ROLE)
        click_robust(page, Locs.CLAN_REJECT_REQUEST_BUTTON)
        return _notice_has(page, "Rechazaste la solicitud") and _expect_visible(
            page, Locs.CLAN_REQUESTS_EMPTY, "'No hay solicitudes pendientes.'", timeout=_SUBMIT_TIMEOUT
        )
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_021_checkInvalidInviteRejected(page: Page) -> bool:
    _open_clan_profile(page, _MISSING_CLAN_ID, _OTHER_ROLE)
    if not _expect_visible(page, Locs.CLAN_NOT_FOUND_TITLE, "'No encontramos este clan'", timeout=_SUBMIT_TIMEOUT):
        return False
    go_to(page, "/clans")
    wait_for_app_ready(page)
    click_robust(page, Locs.CLANS_JOIN_CODE_BUTTON)
    page.locator(Locs.CLAN_INVITE_CODE_INPUT).fill(_SHORT_CODE)
    click_robust(page, Locs.dialog_button_with_text("Unirme al clan"))
    if not _expect_visible(page, Locs.CLAN_DIALOG_ALERT, "el error del código"):
        return False
    shown = page.locator(Locs.CLAN_DIALOG_ALERT).first.inner_text().strip()
    if shown != _INVALID_CODE_ERROR:
        logger.error("Se esperaba %r, el diálogo muestra %r", _INVALID_CODE_ERROR, shown)
        return False
    return True


def test_00_11_022_checkDissolveClan(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _open_clan_profile(page, clan_id, _CREATOR_ROLE)
        click_robust(page, Locs.CLAN_PROFILE_DISSOLVE_BUTTON)
        _confirm_dialog(page, "Disolver clan")
        if not wait_until(lambda: current_path(page) == "/clans", page, timeout=_SUBMIT_TIMEOUT):
            logger.error("Disolver no volvió a /clans (URL: %s)", page.url)
            return False
        if not _notice_has(page, f"{name} se disolvió."):
            return False
        go_to(page, f"/clans/{clan_id}")
        wait_for_app_ready(page)
        return _expect_visible(page, Locs.CLAN_NOT_FOUND_TITLE, "'No encontramos este clan'", timeout=_SUBMIT_TIMEOUT)
    finally:
        _dissolve_clan(page, clan_id)


def test_00_11_023_checkTransferLeadership(page: Page) -> bool:
    name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _CREATOR_ROLE)
        click_robust(page, Locs.CLAN_TRANSFER_BUTTON)
        click_robust(page, Locs.CLAN_TRANSFER_TRIGGER)
        page.get_by_role("option").first.wait_for(state="visible", timeout=_SHORT_TIMEOUT)
        page.get_by_role("option").first.click()
        _confirm_dialog(page, "Transferir liderazgo")
        if not _notice_has(page, f"es ahora la persona líder de {name}"):
            return False
        return _expect_visible(page, Locs.CLAN_LEAVE_BUTTON, "'Salir del clan'", timeout=_SUBMIT_TIMEOUT) and (
            _expect_hidden(page, Locs.CLAN_PROFILE_DISSOLVE_BUTTON, "Disolver clan")
        )
    finally:
        _dissolve_clan(page, clan_id, _OTHER_ROLE)
        _dissolve_clan(page, clan_id, _CREATOR_ROLE)


def test_00_11_024_checkClanListErrorAndRetry(page: Page) -> bool:
    with _directory_down(page):
        _open_clans(page)
        if not _expect_visible(
            page, Locs.CLAN_DIRECTORY_ERROR_TITLE, "'No se pudieron cargar los clanes'", timeout=_SUBMIT_TIMEOUT
        ):
            return False
    click_robust(page, Locs.CLANS_DIRECTORY_RETRY)
    return _expect_hidden(page, Locs.CLAN_DIRECTORY_ERROR_TITLE, "el error de la lista")


def test_00_11_025_checkClanActiveCampaigns(page: Page) -> bool:
    _name, clan_id = _with_clan(page, _CREATOR_ROLE)
    try:
        _join_clan_via_api(page, _OTHER_ROLE, clan_id)
        _open_clan_profile(page, clan_id, _OTHER_ROLE)
        return _expect_visible(
            page, Locs.CLAN_CAMPAIGNS_TITLE, "'Campañas activas'", timeout=_SUBMIT_TIMEOUT
        ) and _expect_visible(
            page, Locs.CLAN_CAMPAIGNS_EMPTY_TITLE, "'Sin campañas activas'", timeout=_SUBMIT_TIMEOUT
        )
    finally:
        _dissolve_clan(page, clan_id)
