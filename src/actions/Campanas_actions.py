"""Acciones del módulo 04 · Campañas (tests/Campanas/test_Campanas.py).

Usuarios: campaign_leader (L, líder del clan de prueba), student (S, miembro del clan) y admin (A).
Solo TC-04-008 (POST de campaña global) y TC-04-012 (error del listado) usan mocks; todo lo demás
pega al backend real. El estado compartido entre tests vive en `_STATE`; todos los tests del módulo
corren en orden dentro del mismo proceso (ver tests/Campanas/__init__.py).
"""

import re
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.sync_api import Locator, Page, Request

from src.configs import environment as env
from src.utils.api import ApiClient, api_for_page
from src.utils.common_actions import click_filter_chip, go_to, login_as
from src.utils.helpers import locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import RouteHandle, mock_api_error, mock_api_json
from src.utils.test_data import is_marked, register_membership, unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_MAX_PAGES = 30
_MX_TZ = ZoneInfo("America/Mexico_City")

# Solo el listado (``/campaigns/?page=1&...``): no el detalle (``/campaigns/<id>/``) ni ``/proposals/``.
_LIST_URL = re.compile(r"/api/v1/campaigns/\?")

_CLANS_PATH = "/api/v1/clans/"
_CAMPAIGNS_PATH = "/api/v1/campaigns/"
_ACTIONS_PATH = "/api/v1/actions/"

# Chips (components/campaigns/campaign-filters.ts y ProposalList.tsx)
_STATUS_GROUP = "Filtrar campañas por estado"
_SCOPE_GROUP = "Filtrar campañas por alcance"
_PROPOSAL_GROUP = "Filtrar propuestas por estado"
_CHIP_PROMOTION = "En promoción"
_CHIP_ACTIVE = "Activas"
_CHIP_FINISHED = "Finalizadas"
_CHIP_CLAN = "De clan"
_CHIP_PENDING = "Pendientes"

# Badges de estado (lib/campaign-meta.ts)
_BADGE_PROMOTION = "En promoción"
_BADGE_ACTIVE = "Activa"
_BADGE_FINISHED = "Finalizada"
_BADGE_PENDING = "Pendiente"

# Botones (CampaignFormDialog, UserMissionsView, AdminMissionsView, CampaignDetailDialog, ...)
_BTN_PROPOSE = "Proponer campaña"
_BTN_CREATE_CLAN = "Crear campaña de clan"
_BTN_CREATE = "Crear campaña"
_BTN_JOIN = "Unirme"
_BTN_EDIT = "Editar campaña"
_BTN_SAVE = "Guardar cambios"
_BTN_ADD_MISSION = "Agregar misión"
_BTN_START = "Iniciar campaña"
_BTN_FINISH = "Finalizar campaña"
_BTN_CANCEL = "Cancelar"
_BTN_RETRY = "Reintentar"
_PAGE_NEXT = "Página siguiente"

# Campos del formulario (CampaignFormDialog, EditCampaignForm, AddMissionForm)
_LABEL_TITLE = "Título"
_LABEL_DESCRIPTION = "Descripción"
_LABEL_START = "Fecha de inicio"
_LABEL_END = "Fecha de fin"
_LABEL_TARGET = "Meta"
_LABEL_ADD_TARGET = "Meta (veces)"
_TRIGGER_CLAN = "campaign-clan"
_TRIGGER_MISSION_1 = "mission-action-1"
_TRIGGER_ADD_MISSION = "add-mission-action"

# Mensajes (componentes de campañas y SuccessBanner)
_MSG_JOINED = "¡Listo! Te uniste a la campaña. Ya puedes completar sus misiones."
_MSG_PROPOSED = "¡Propuesta enviada! Un administrador la revisará pronto."
_MSG_CREATED_CLAN = "¡Campaña creada! Ya está disponible para tu clan."
_MSG_CREATED_GLOBAL = "¡Campaña creada! Ya está disponible para la comunidad."
_MSG_SAVED = "¡Listo! Los cambios de la campaña se guardaron."
_MSG_MISSION_ADDED = "Misión agregada a la campaña."
_MSG_STARTED = "¡Listo! La campaña ya está activa."
_MSG_FINISHED = "La campaña se finalizó."
_MSG_FORBIDDEN_CLAN = "Solo el líder de este clan puede crear campañas"
_MSG_LIST_ERROR = "No se pudieron cargar las campañas"
_MSG_LOADING = "Cargando campañas…"
_MSG_EMPTY = "No hay campañas"
_MSG_REQUIRED = (
    "Escribe un título.",
    "Escribe una descripción.",
    "Elige la fecha de inicio.",
    "Elige la fecha de fin.",
    "Agrega al menos una misión a la campaña.",
)

_STATE: dict[str, Any] = {}


# --- privadas: datos y API ------------------------------------------------------------------


def _campaign_dates(days: int = 3) -> tuple[str, str]:
    """Return (inicio, fin) como YYYY-MM-DD: mañana en Ciudad de México y `days` días después."""
    tomorrow = datetime.now(_MX_TZ).date() + timedelta(days=1)
    return tomorrow.isoformat(), (tomorrow + timedelta(days=days)).isoformat()


def _mx_iso(day: str, *, end_of_day: bool) -> str:
    """ISO datetime of `day` (YYYY-MM-DD) at 00:00:00 or 23:59:59 in Mexico City, like the frontend sends it."""
    moment = dtime(23, 59, 59) if end_of_day else dtime(0, 0, 0)
    return datetime.combine(date.fromisoformat(day), moment, tzinfo=_MX_TZ).isoformat()


def _catalog(page: Page) -> list[dict[str, Any]]:
    """Return the first two active catalog actions (GET actions/); each mission uses one of them."""
    items = [item for item in api_for_page(page).pages("student", _ACTIONS_PATH) if item.get("id")]
    if len(items) < 2:
        raise RuntimeError("El catálogo de acciones necesita al menos 2 acciones activas")
    return items[:2]


def _label(action: dict[str, Any]) -> str:
    """Option text of an action in the mission select: "<nombre> · <puntos> pts"."""
    return f"{action['name']} · {action['points']} pts"


def _create_api_campaign(api: ApiClient, *, title: str, clan_id: str, action_id: str) -> dict[str, Any]:
    """Create a PRIVATE campaign for the clan as L, starting tomorrow, with one mission."""
    start, end = _campaign_dates()
    body = {
        "title": title,
        "description": unique_name("Campaña de prueba", max_length=100),
        "scope": "PRIVATE",
        "target_clan": clan_id,
        "start_date": _mx_iso(start, end_of_day=False),
        "end_date": _mx_iso(end, end_of_day=True),
        "missions": [{"action_id": action_id, "target_count": 1}],
    }
    return api.json("campaign_leader", "POST", _CAMPAIGNS_PATH, data=body, expected=(201,))


def _find_api_campaign(api: ApiClient, role: str, *, title: str, clan_id: str) -> dict[str, Any] | None:
    """Look a clan campaign up by its exact title (the title carries the run marker)."""
    for campaign in api.pages(role, _CAMPAIGNS_PATH, {"target_clan": clan_id}):
        if campaign.get("title") == title:
            return campaign
    return None


def _api_campaign(api: ApiClient, role: str, campaign_id: str) -> dict[str, Any]:
    return api.json(role, "GET", f"{_CAMPAIGNS_PATH}{campaign_id}/")


def _state(key: str) -> Any:
    """Read a value stored by the setup; a missing value means the setup did not run."""
    if key not in _STATE:
        raise RuntimeError(f"Falta '{key}' en el estado del módulo: revisa que el setup (_000) haya corrido")
    return _STATE[key]


# --- privadas: navegación y listados --------------------------------------------------------


def _dialog(page: Page) -> Locator:
    return page.get_by_role("dialog")


def _visible(locator: Locator, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(locator, timeout=timeout)


def _click(locator: Locator, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Click the first match once it is visible; retry with force, then with a JS click."""
    target = locator.first
    target.wait_for(state="visible", timeout=timeout)
    try:
        target.click(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.debug("click normal falló (%s); reintento con force=True", exc)
        try:
            target.click(force=True, timeout=timeout)
        except Exception as force_exc:  # noqa: BLE001
            logger.debug("click con force falló (%s); último recurso: JS", force_exc)
            target.evaluate("el => { el.click(); return true; }")


def _open_list(page: Page, *, status: str | None = None, scope: str | None = None) -> None:
    """Open /campaigns (the session is already injected) and apply the filter chips."""
    go_to(page, "/campaigns")
    wait_for_app_ready(page)
    if status:
        click_filter_chip(page, _STATUS_GROUP, status)
    if scope:
        click_filter_chip(page, _SCOPE_GROUP, scope)


def _next_page_button(page: Page) -> Locator:
    """Next-page arrow of the campaigns grid (the proposals list has its own pager)."""
    nav = page.get_by_role("navigation", name="Paginación de campañas")
    return nav.get_by_role("button", name=_PAGE_NEXT)


def _page_indicator(page: Page) -> Locator:
    return page.get_by_role("progressbar", name="Página de campañas")


def _wait_list_ready(page: Page, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Wait until the campaigns section stops loading and shows cards, the empty state or the error."""
    section = page.locator("section").filter(has=page.get_by_role("heading", name="Todas las campañas", exact=True))

    def _ready() -> bool:
        if section.get_by_text(_MSG_LOADING, exact=True).count() > 0:
            return False
        return (
            section.locator("[data-slot='card']").count() > 0
            or section.get_by_role("heading", name=_MSG_EMPTY, exact=True).count() > 0
            or section.get_by_role("heading", name=_MSG_LIST_ERROR, exact=True).count() > 0
        )

    if not wait_until(_ready, page, timeout=timeout, poll_ms=150):
        raise RuntimeError("La lista de campañas no terminó de cargar")


def _find_card(page: Page, title: str, *, max_pages: int = _MAX_PAGES) -> Locator:
    """Find the campaign card with `title`, walking the pages of the current filter."""
    _wait_list_ready(page)
    card = page.locator(Locs.role_with_descendant_text("button", title)).first
    for number in range(1, max_pages + 1):
        if _visible(card, timeout=1_000):
            logger.debug("Tarjeta %s encontrada en la página %s", title, number)
            return card
        next_button = _next_page_button(page)
        if next_button.count() == 0 or not next_button.first.is_enabled():
            break
        next_button.first.click()
        target = str(number + 1)
        if not wait_until(
            lambda expected=target: _page_indicator(page).first.get_attribute("aria-valuenow") == expected,
            page,
            timeout=_SHORT_TIMEOUT,
        ):
            raise RuntimeError(f"La paginación no llegó a la página {target}")
    raise RuntimeError(f"La campaña {title!r} no aparece en la lista (filtros aplicados)")


def _open_card(page: Page, card: Locator, title: str) -> Locator:
    """Click a card and wait for its detail dialog; return the dialog locator."""
    _click(card)
    dialog = _dialog(page)
    dialog.wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)
    if not _visible(dialog.get_by_text(title, exact=True), timeout=env.DEFAULT_TIMEOUT):
        raise RuntimeError(f"El detalle de {title!r} no muestra su título")
    return dialog


def _open_campaign(page: Page, title: str, *, status: str | None = None, scope: str | None = None) -> Locator:
    """List → filter → find the card → open its detail dialog."""
    _open_list(page, status=status, scope=scope)
    return _open_card(page, _find_card(page, title), title)


def _open_create_dialog(page: Page, button_name: str) -> Locator:
    """Open a create dialog from the page header button."""
    _click(page.get_by_role("button", name=button_name, exact=True))
    dialog = _dialog(page)
    dialog.wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)
    return dialog


def _visible_option(page: Page, option_text: str) -> Locator | None:
    """Return the visible option with `option_text`, trying the role first and then the XPath."""
    candidates = (
        page.get_by_role("option", name=option_text, exact=True),
        page.locator(Locs.option_with_text(option_text)),
    )
    for candidate in candidates:
        if _visible(candidate, timeout=1_000):
            return candidate.first
    return None


def _select_trigger(page: Page, element_id: str) -> Locator:
    """Trigger of a Select by id: role=combobox first, then any element with that id."""
    combobox = page.locator(Locs.combobox_with_id(element_id))
    if combobox.count() > 0:
        return combobox.first
    logger.debug("Sin combobox con id %s; uso el elemento por id", element_id)
    return page.locator(f"[id='{element_id}']").first


def _select_option(page: Page, element_id: str, option_text: str, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Pick `option_text` in the base-ui Select whose trigger has `element_id` (role=combobox, role=option items).

    Open the trigger, click the option; retries, then force, then a JS click. Verifies that the
    trigger now shows the option text.
    """
    page.locator(f"[id='{element_id}']").first.wait_for(state="visible", timeout=timeout)
    trigger = _select_trigger(page, element_id)
    deadline = time.monotonic() + timeout / 1000
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            option = _visible_option(page, option_text)
            if option is None:
                trigger.click(timeout=1_000)
                option = _visible_option(page, option_text)
            if option is None:
                logger.debug("_select_option: la opción %r no aparece (intento %s)", option_text, attempt)
                page.wait_for_timeout(150)
                continue
            if attempt <= 2:
                option.click(timeout=1_000)
            elif attempt == 3:
                logger.debug("_select_option: reintento con force=True en %r", option_text)
                option.click(force=True, timeout=1_000)
            else:
                logger.debug("_select_option: último recurso, click por JS en %r", option_text)
                option.evaluate("el => { el.click(); return true; }")
        except Exception as exc:  # noqa: BLE001
            logger.debug("_select_option: el click en %r falló: %s", option_text, exc)
            continue
        if wait_until(lambda: option_text in (trigger.text_content() or ""), page, timeout=2_000, poll_ms=150):
            logger.info("Opción elegida: %s", option_text)
            return
    raise RuntimeError(f"No se pudo elegir {option_text!r} en #{element_id}")


def _fill_form(dialog: Locator, *, title: str, description: str, start: str, end: str) -> None:
    dialog.get_by_label(_LABEL_TITLE, exact=True).fill(title)
    dialog.get_by_label(_LABEL_DESCRIPTION, exact=True).fill(description)
    dialog.get_by_label(_LABEL_START, exact=True).fill(start)
    dialog.get_by_label(_LABEL_END, exact=True).fill(end)


def _add_mission_in_form(page: Page, dialog: Locator, option_text: str) -> None:
    """Add the first mission row of a create/propose form and pick its action."""
    _click(dialog.get_by_role("button", name=_BTN_ADD_MISSION, exact=True))
    _select_option(page, _TRIGGER_MISSION_1, option_text)
    dialog.get_by_label(_LABEL_TARGET, exact=True).fill("1")


def _submit(dialog: Locator, button_name: str) -> None:
    _click(dialog.get_by_role("button", name=button_name, exact=True))


def _dialog_closed(page: Page) -> bool:
    return wait_until(lambda: not _dialog(page).is_visible(), page, timeout=env.DEFAULT_TIMEOUT)


# --- setup ----------------------------------------------------------------------------------


def _led_clan(api: ApiClient) -> dict[str, Any] | None:
    """Return the PRIVATE clan L already leads (the backend allows only one), or None."""
    leader_id = api.user_id("campaign_leader")
    for clan in api.pages("campaign_leader", _CLANS_PATH):
        if clan.get("type") != "PRIVATE":
            continue
        detail = api.json("campaign_leader", "GET", f"{_CLANS_PATH}{clan['id']}/")
        for member in detail.get("members", []):
            if str(member.get("user_id")) == leader_id and member.get("role") == "LEADER":
                return detail
    return None


def _setup_clan(api: ApiClient) -> dict[str, Any]:
    """Clan of L with S as member: reuse the one L already leads, else create a marked one."""
    clan = _led_clan(api)
    if clan is None:
        clan = api.json(
            "campaign_leader",
            "POST",
            _CLANS_PATH,
            data={
                "name": unique_name("Clan campañas", max_length=100),
                "description": unique_name("Clan de pruebas", max_length=100),
                "privacy": "PUBLIC",
            },
            expected=(201,),
        )
        api.json("student", "POST", f"{_CLANS_PATH}{clan['id']}/join/", expected=(200, 201))
        return clan

    # Clan real de L (sin marcador): la limpieza no lo disuelve; S se une solo durante la corrida.
    logger.info("Setup de Campañas: se reusa el clan %r que ya lidera campaign_leader", clan["name"])
    student_id = api.user_id("student")
    if not any(str(m.get("user_id")) == student_id for m in clan.get("members", [])):
        api.json("student", "POST", f"{_CLANS_PATH}{clan['id']}/join/", expected=(200, 201))
        register_membership("student", clan["id"])
    return clan


def test_00_04_000_checkSetupCampaigns(page: Page) -> bool:
    """Setup vía API: clan de L (el que ya lidera o uno nuevo) con S de miembro, y L crea la campaña A (privada)."""
    api = api_for_page(page)
    first, second = _catalog(page)
    clan = _setup_clan(api)
    clan_name = clan["name"]

    title_a = unique_name("Campaña A", max_length=50)
    campaign_a = _create_api_campaign(api, title=title_a, clan_id=clan["id"], action_id=first["id"])
    _STATE.update(
        {
            "clan_id": clan["id"],
            "clan_name": clan_name,
            "action_1": first,
            "action_2": second,
            "campaign_a": {"id": campaign_a["id"], "title": title_a},
        }
    )
    logger.info("Setup de Campañas: clan %s, campaña A %s", clan["id"], campaign_a["id"])
    return True


# --- tests ----------------------------------------------------------------------------------


def test_00_04_001_checkListAndDetail(page: Page) -> bool:
    """S ve la tarjeta de A ("Clan · <clan>", "En promoción") y su detalle con fechas, misiones y participantes."""
    login_as(page, "student")
    campaign = _state("campaign_a")
    _open_list(page, status=_CHIP_PROMOTION, scope=_CHIP_CLAN)
    card = _find_card(page, campaign["title"])
    if not _visible(card.get_by_text(f"Clan · {_state('clan_name')}", exact=True)):
        logger.error("La tarjeta no muestra 'Clan · <nombre del clan>'")
        return False
    if not _visible(card.get_by_text(_BADGE_PROMOTION, exact=True)):
        logger.error("La tarjeta de A no muestra el estado 'En promoción'")
        return False

    dialog = _open_card(page, card, campaign["title"])
    checks = {
        "badge en promoción": dialog.get_by_text(_BADGE_PROMOTION, exact=True),
        "fechas": dialog.get_by_text("Fechas", exact=True),
        "participantes": dialog.get_by_text("Participantes", exact=True),
        "misiones": dialog.get_by_role("heading", name="Misiones", exact=True),
        "acción de la misión": dialog.get_by_text(_state("action_1")["name"], exact=True),
        "nombre del clan": dialog.get_by_text(_state("clan_name"), exact=True),
    }
    missing = [name for name, locator in checks.items() if not _visible(locator)]
    for name in missing:
        logger.error("En el detalle de A no se ve: %s", name)
    return not missing


def test_00_04_002_checkStatusAndScopeFilters(page: Page) -> bool:
    """Los chips mandan status y scope como query params; A aparece en "En promoción" + "De clan" y no en "Finalizadas"."""
    login_as(page, "student")
    campaign = _state("campaign_a")
    _open_list(page)
    click_filter_chip(page, _STATUS_GROUP, _CHIP_PROMOTION)
    with page.expect_request(
        lambda req: "/api/v1/campaigns/?" in req.url and "status=PROMOTION" in req.url and "scope=PRIVATE" in req.url
    ) as request_info:
        click_filter_chip(page, _SCOPE_GROUP, _CHIP_CLAN)
    logger.info("Petición de filtros: %s", request_info.value.url)

    _find_card(page, campaign["title"])

    # Esperar la respuesta del filtro nuevo: si no, se revisa la lista anterior, que sigue en pantalla.
    with page.expect_response(
        lambda res: "/api/v1/campaigns/?" in res.url and "status=FINISHED" in res.url and res.request.method == "GET"
    ):
        click_filter_chip(page, _STATUS_GROUP, _CHIP_FINISHED)
    _wait_list_ready(page)
    if _visible(page.locator(Locs.role_with_descendant_text("button", campaign["title"])), timeout=1_000):
        logger.error("A aparece en 'Finalizadas' aunque sigue en promoción")
        return False
    status = _api_campaign(api_for_page(page), "student", campaign["id"])["status"]
    if status != "PROMOTION":
        logger.error("El estado de A en la API es %s, se esperaba PROMOTION", status)
        return False
    return True


def test_00_04_003_checkJoinPromotionCampaign(page: Page) -> bool:
    """S se une a A: aparece el aviso, el botón "Unirme" desaparece y la API marca is_participant=true."""
    login_as(page, "student")
    campaign = _state("campaign_a")
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_PROMOTION, scope=_CHIP_CLAN)
    _click(dialog.get_by_role("button", name=_BTN_JOIN, exact=True))
    if not _visible(dialog.get_by_text(_MSG_JOINED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció el aviso de inscripción")
        return False
    # El aviso sale antes de que el detalle se refresque: espera a que el botón desaparezca.
    if not wait_until(
        lambda: not dialog.get_by_role("button", name=_BTN_JOIN, exact=True).is_visible(),
        page,
        timeout=env.DEFAULT_TIMEOUT,
    ):
        logger.error("El botón 'Unirme' sigue visible después de inscribirse")
        return False
    if _api_campaign(api_for_page(page), "student", campaign["id"]).get("is_participant") is not True:
        logger.error("La API no marca a S como participante de A")
        return False
    return True


def test_00_04_004_checkProposeGlobalCampaign(page: Page) -> bool:
    """S propone una campaña global: aviso de envío y la propuesta aparece como "Pendiente". No notifica a nadie."""
    login_as(page, "student")
    action = _catalog(page)[0]
    title = unique_name("Propuesta", max_length=50)
    start, end = _campaign_dates()
    _open_list(page)
    dialog = _open_create_dialog(page, _BTN_PROPOSE)
    _fill_form(
        dialog, title=title, description=unique_name("Propuesta de prueba", max_length=100), start=start, end=end
    )
    _add_mission_in_form(page, dialog, _label(action))
    _submit(dialog, _BTN_PROPOSE)

    if not _visible(page.get_by_text(_MSG_PROPOSED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció el aviso '¡Propuesta enviada!…'")
        return False
    click_filter_chip(page, _PROPOSAL_GROUP, _CHIP_PENDING)
    proposal = page.locator(Locs.li_with_text(title)).first
    if not _visible(proposal, timeout=env.DEFAULT_TIMEOUT):
        logger.error("La propuesta %r no aparece en 'Mis propuestas'", title)
        return False
    return _visible(proposal.get_by_text(_BADGE_PENDING, exact=True))


def test_00_04_005_checkRequiredFields(page: Page) -> bool:
    """El formulario de propuesta muestra los 5 mensajes de campos obligatorios y no envía nada."""
    login_as(page, "student")
    _open_list(page)
    sent: list[str] = []

    def _record_post(request: Request) -> None:
        if request.method == "POST" and "/campaigns/" in request.url:
            sent.append(request.url)

    dialog = _open_create_dialog(page, _BTN_PROPOSE)
    page.on("request", _record_post)
    try:
        _submit(dialog, _BTN_PROPOSE)
        missing = [text for text in _MSG_REQUIRED if not _visible(dialog.get_by_text(text, exact=True))]
        for text in missing:
            logger.error("No apareció el mensaje obligatorio: %s", text)
        if missing:
            return False
        _click(dialog.get_by_role("button", name=_BTN_CANCEL, exact=True))
        if not _dialog_closed(page):
            logger.error("El diálogo no se cerró al cancelar")
            return False
    finally:
        page.remove_listener("request", _record_post)
    if sent:
        logger.error("Se envió una petición de campaña con el formulario vacío: %s", sent)
        return False
    return True


def test_00_04_006_checkLeaderCreatesClanCampaign(page: Page) -> bool:
    """L crea la campaña B de su clan (queda inscrito como participante automáticamente)."""
    login_as(page, "campaign_leader")
    clan_id = _state("clan_id")
    action = _state("action_1")
    title = unique_name("Campaña de clan", max_length=50)
    start, end = _campaign_dates()
    _open_list(page)
    dialog = _open_create_dialog(page, _BTN_CREATE_CLAN)
    _select_option(page, _TRIGGER_CLAN, _state("clan_name"))
    _fill_form(dialog, title=title, description=unique_name("Clan campaña", max_length=100), start=start, end=end)
    _add_mission_in_form(page, dialog, _label(action))
    _submit(dialog, _BTN_CREATE)

    if not _visible(page.get_by_text(_MSG_CREATED_CLAN, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció '¡Campaña creada! Ya está disponible para tu clan.'")
        return False
    created = _find_api_campaign(api_for_page(page), "campaign_leader", title=title, clan_id=clan_id)
    if created is None or created.get("scope") != "PRIVATE":
        logger.error("La API no devuelve la campaña B como PRIVATE del clan")
        return False
    _STATE["campaign_b"] = {"id": created["id"], "title": title}
    return True


def test_00_04_007_checkNonLeaderCannotCreateClanCampaign(page: Page) -> bool:
    """S (miembro, no líder) intenta crear una campaña de clan: 403 y el aviso del líder."""
    login_as(page, "student")
    clan_id = _state("clan_id")
    action = _catalog(page)[0]
    start, end = _campaign_dates()
    _open_list(page)
    dialog = _open_create_dialog(page, _BTN_CREATE_CLAN)
    _select_option(page, _TRIGGER_CLAN, _state("clan_name"))
    _fill_form(
        dialog,
        title=unique_name("Intento sin permiso", max_length=50),
        description=unique_name("Intento de prueba", max_length=100),
        start=start,
        end=end,
    )
    _add_mission_in_form(page, dialog, _label(action))

    with page.expect_response(
        lambda resp: resp.request.method == "POST" and resp.url.split("?")[0].rstrip("/").endswith("/api/v1/campaigns")
    ) as response_info:
        _submit(dialog, _BTN_CREATE)
    if response_info.value.status != 403:
        logger.error(
            "La API respondió %s; se esperaba 403 para un miembro que no lidera el clan", response_info.value.status
        )
        return False
    if not _visible(dialog.get_by_role("alert").filter(has_text=_MSG_FORBIDDEN_CLAN), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No se muestra el aviso 'Solo el líder de este clan…'")
        return False
    logger.info("Clan %s: el 403 llegó y no se creó nada", clan_id)
    return True


def test_00_04_008_checkAdminCreatesGlobalCampaign(page: Page) -> bool:
    """A crea una campaña global. Se intercepta el POST: NO se crea nada real (notificaría a todos)."""
    login_as(page, "admin")
    action = _catalog(page)[0]
    title = unique_name("Global", max_length=50)
    start, end = _campaign_dates()
    fake_campaign = {
        "id": str(uuid4()),
        "title": title,
        "scope": "GLOBAL",
        "status": "PROMOTION",
        "approval_status": "APPROVED",
    }
    # Red de seguridad: cualquier POST a /api/v1/campaigns… que el mock no atrape se contesta con error
    # aquí mismo y nunca llega al backend. Se registra primero; el mock (registrado después) tiene prioridad.
    guard: RouteHandle = mock_api_error(page, lambda url: "/api/v1/campaigns" in url, status=599, method="POST")
    route: RouteHandle = mock_api_json(page, "**/api/v1/campaigns/", fake_campaign, status=201, method="POST")
    try:
        _open_list(page)
        dialog = _open_create_dialog(page, _BTN_CREATE)
        _fill_form(
            dialog, title=title, description=unique_name("Global de prueba", max_length=100), start=start, end=end
        )
        _add_mission_in_form(page, dialog, _label(action))
        _submit(dialog, _BTN_CREATE)

        if not _visible(page.get_by_text(_MSG_CREATED_GLOBAL, exact=True), timeout=env.DEFAULT_TIMEOUT):
            logger.error("No apareció '¡Campaña creada! Ya está disponible para la comunidad.'")
            return False
        if not route.requests:
            logger.error("No se interceptó el POST de campañas")
            return False
        body = route.requests[-1].post_data_json or {}
    finally:
        route.restore()
        guard.restore()
    if guard.requests:
        logger.error(
            "Un POST de campañas no coincidió con el mock y lo bloqueó la red de seguridad: %s",
            [r.url for r in guard.requests],
        )
        return False

    checks = {
        "scope GLOBAL": body.get("scope") == "GLOBAL",
        "sin target_clan": "target_clan" not in body,
        "título": body.get("title") == title,
        "misiones": body.get("missions") == [{"action_id": action["id"], "target_count": 1}],
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name in failed:
        logger.error("El body interceptado no cumple: %s (body=%s)", name, body)
    return not failed


def test_00_04_009_checkEditPromotionCampaignAndAddMission(page: Page) -> bool:
    """L edita B (título con marcador) y le agrega una misión mientras está en promoción."""
    login_as(page, "campaign_leader")
    campaign = _state("campaign_b")
    new_title = unique_name("Campaña editada", max_length=50)
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_PROMOTION, scope=_CHIP_CLAN)

    _click(dialog.get_by_role("button", name=_BTN_EDIT, exact=True))
    dialog.get_by_label(_LABEL_TITLE, exact=True).fill(new_title)
    _click(dialog.get_by_role("button", name=_BTN_SAVE, exact=True))
    if not _visible(dialog.get_by_text(_MSG_SAVED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció '¡Listo! Los cambios de la campaña se guardaron.'")
        return False
    _STATE["campaign_b"] = {"id": campaign["id"], "title": new_title}

    _click(dialog.get_by_role("button", name=_BTN_ADD_MISSION, exact=True))
    _select_option(page, _TRIGGER_ADD_MISSION, _label(_state("action_2")))
    dialog.get_by_label(_LABEL_ADD_TARGET, exact=True).fill("1")
    _submit(dialog, _BTN_ADD_MISSION)
    if not _visible(dialog.get_by_text(_MSG_MISSION_ADDED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció 'Misión agregada a la campaña.'")
        return False

    api = api_for_page(page)
    saved = _api_campaign(api, "campaign_leader", campaign["id"])
    if saved.get("title") != new_title or len(saved.get("missions", [])) != 2:
        logger.error(
            "La API no refleja la edición: título=%r, misiones=%s", saved.get("title"), len(saved.get("missions", []))
        )
        return False
    return is_marked(new_title)


def test_00_04_010_checkEditBlockedOutsidePromotion(page: Page) -> bool:
    """Una campaña ya activa (C, iniciada por API) muestra "Activa" y no ofrece editar ni agregar misiones."""
    api = api_for_page(page)
    clan_id = _state("clan_id")
    action = _state("action_1")
    title = unique_name("Campaña activa", max_length=50)
    campaign = _create_api_campaign(api, title=title, clan_id=clan_id, action_id=action["id"])
    api.json("campaign_leader", "POST", f"{_CAMPAIGNS_PATH}{campaign['id']}/start/", expected=(200,))
    _STATE["campaign_c"] = {"id": campaign["id"], "title": title}

    login_as(page, "campaign_leader")
    dialog = _open_campaign(page, title, status=_CHIP_ACTIVE, scope=_CHIP_CLAN)
    if not _visible(dialog.get_by_text(_BADGE_ACTIVE, exact=True)):
        logger.error("La campaña iniciada no muestra el estado 'Activa'")
        return False
    if _visible(dialog.get_by_role("button", name=_BTN_EDIT, exact=True), timeout=1_000):
        logger.error("Se ofrece 'Editar campaña' en una campaña activa")
        return False
    if _visible(dialog.get_by_role("button", name=_BTN_ADD_MISSION, exact=True), timeout=1_000):
        logger.error("Se ofrece 'Agregar misión' en una campaña activa")
        return False
    return True


def test_00_04_011_checkAdminCannotJoin(page: Page) -> bool:
    """A ve la campaña A (el clan sigue vivo) pero no tiene el botón "Unirme"."""
    login_as(page, "admin")
    campaign = _state("campaign_a")
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_PROMOTION, scope=_CHIP_CLAN)
    if _visible(dialog.get_by_role("button", name=_BTN_JOIN, exact=True), timeout=1_000):
        logger.error("El admin ve el botón 'Unirme' en la campaña A")
        return False
    return True


def test_00_04_012_checkListErrorAndRetry(page: Page) -> bool:
    """Si el listado falla (500 simulado) aparece el error; al restaurar y reintentar, las campañas cargan."""
    login_as(page, "student")
    campaign = _state("campaign_a")
    route = mock_api_error(page, _LIST_URL, status=500)
    try:
        go_to(page, "/campaigns")
        wait_for_app_ready(page)
        error_title = page.get_by_role("heading", name=_MSG_LIST_ERROR, exact=True)
        if not _visible(error_title, timeout=env.DEFAULT_TIMEOUT):
            logger.error("No se muestra el error '%s'", _MSG_LIST_ERROR)
            return False
    finally:
        route.restore()

    error_section = page.locator("section").filter(has=error_title)
    _click(error_section.get_by_role("button", name=_BTN_RETRY, exact=True))
    if not wait_until(lambda: not _visible(error_title, timeout=200), page, timeout=env.DEFAULT_TIMEOUT):
        logger.error("El error del listado no desapareció al reintentar")
        return False
    click_filter_chip(page, _STATUS_GROUP, _CHIP_PROMOTION)
    click_filter_chip(page, _SCOPE_GROUP, _CHIP_CLAN)
    return _visible(_find_card(page, campaign["title"]), timeout=env.DEFAULT_TIMEOUT)


def test_00_04_013_checkStartPromotionCampaign(page: Page) -> bool:
    """L inicia B: confirma "¿Iniciar “…”?", aparece "¡Listo! La campaña ya está activa." y queda "Activa"."""
    login_as(page, "campaign_leader")
    campaign = _state("campaign_b")
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_PROMOTION, scope=_CHIP_CLAN)
    _click(dialog.get_by_role("button", name=_BTN_START, exact=True))
    if not _visible(dialog.get_by_text(f"¿Iniciar “{campaign['title']}”?", exact=True)):
        logger.error("No aparece la confirmación '¿Iniciar “…”?'")
        return False
    _click(dialog.get_by_role("button", name=_BTN_START, exact=True))
    if not _visible(dialog.get_by_text(_MSG_STARTED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció '¡Listo! La campaña ya está activa.'")
        return False
    if not _visible(dialog.get_by_text(_BADGE_ACTIVE, exact=True)):
        logger.error("La campaña no muestra el estado 'Activa'")
        return False
    return _api_campaign(api_for_page(page), "campaign_leader", campaign["id"])["status"] == "IN_PROGRESS"


def test_00_04_014_checkFinishActiveCampaign(page: Page) -> bool:
    """L finaliza B: confirma, aparece "La campaña se finalizó." y queda "Finalizada"."""
    login_as(page, "campaign_leader")
    campaign = _state("campaign_b")
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_ACTIVE, scope=_CHIP_CLAN)
    _click(dialog.get_by_role("button", name=_BTN_FINISH, exact=True))
    if not _visible(dialog.get_by_text(f"¿Finalizar “{campaign['title']}”?", exact=True)):
        logger.error("No aparece la confirmación '¿Finalizar “…”?'")
        return False
    _click(dialog.get_by_role("button", name=_BTN_FINISH, exact=True))
    if not _visible(dialog.get_by_text(_MSG_FINISHED, exact=True), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció 'La campaña se finalizó.'")
        return False
    if not _visible(dialog.get_by_text(_BADGE_FINISHED, exact=True)):
        logger.error("La campaña no muestra el estado 'Finalizada'")
        return False
    return _api_campaign(api_for_page(page), "campaign_leader", campaign["id"])["status"] == "FINISHED"


def test_00_04_015_checkCancelStart(page: Page) -> bool:
    """L abre "Iniciar campaña" en A y cancela: A sigue en promoción y la API no cambia.

    Nunca se confirma el inicio: si el clic en "Cancelar" fallara, A quedaría iniciada de verdad.
    """
    login_as(page, "campaign_leader")
    campaign = _state("campaign_a")
    dialog = _open_campaign(page, campaign["title"], status=_CHIP_PROMOTION, scope=_CHIP_CLAN)
    _click(dialog.get_by_role("button", name=_BTN_START, exact=True))
    if not _visible(dialog.get_by_text(f"¿Iniciar “{campaign['title']}”?", exact=True)):
        logger.error("No aparece la confirmación antes de cancelar")
        return False
    _click(dialog.get_by_role("button", name=_BTN_CANCEL, exact=True))
    if not _visible(dialog.get_by_text(_BADGE_PROMOTION, exact=True)):
        logger.error("Después de cancelar, A no muestra 'En promoción'")
        return False
    if not _visible(dialog.get_by_role("button", name=_BTN_START, exact=True), timeout=1_000):
        logger.error("Después de cancelar no vuelve el botón 'Iniciar campaña'")
        return False
    return _api_campaign(api_for_page(page), "campaign_leader", campaign["id"])["status"] == "PROMOTION"
