"""Acciones del módulo 07 · Auditoría (tests/Auditoria/test_Auditoria.py).

Usuarios: admin (A, revisa), campaign_leader (D, dueño de la evidencia que se aprueba y de las propuestas)
y store (T, dueño de la evidencia que se rechaza). D solo lo usan este módulo y Campañas, y T solo Tienda;
aprobar mueve los puntos de D y rechazar no mueve los de T. No se usa `student` (lo comparten 9 módulos que
corren en paralelo, entre ellos Notificaciones).

Reglas de seguridad (estas pruebas corren contra prod por default):

- Nunca se actúa sobre "la primera tarjeta": la cola de prod tiene evidencias y propuestas de gente
  real. Cada tarjeta se busca por el id de su registro (evidencias) o por el título con marcador (propuestas).
- Aprobar una propuesta global que sigue abierta a inscripciones invita a TODOS los usuarios activos
  (`notify_campaign_invite`). Por eso, fuera del stack desechable (AUTH_MODE != mock), TC-07-005
  intercepta el POST de aprobación: se prueba la UI y la petición, y el backend no se toca.
- El límite diario es por usuario y por acción, y el catálogo que carga el CI (catalog_draft.json) tiene UNA sola
  acción con foto y límite 1. Por eso cada usuario registra una sola evidencia (D la que se aprueba, T la que se
  rechaza) y el setup no depende de que el catálogo tenga una segunda acción con foto. La limpieza de la corrida
  rechaza esas evidencias (revierte puntos) y las propuestas con marcador pendientes.

Todos los tests del módulo corren en orden dentro del mismo proceso; el estado compartido vive en `_STATE`.
EE = 00 es provisional hasta que se haga el reparto de equipos.
"""

import base64
import re
import struct
import zlib
from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.sync_api import Page, Request

from src.configs import environment as env
from src.utils.api import ApiClient, api_for_page
from src.utils.common_actions import click_filter_chip, click_robust, go_to, login_as
from src.utils.helpers import is_on_path, locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import mock_api_error, mock_api_json
from src.utils.test_data import unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_MX_TZ = ZoneInfo("America/Mexico_City")
_MAX_PROPOSAL_PAGES = 30
# La API pagina de 50 en 50 (PAGE_SIZE) y el frontend solo lee la primera página de la cola.
_QUEUE_PAGE_SIZE = 50

_OWNER = "campaign_leader"  # dueño de la evidencia que se aprueba y de las propuestas
_REJECT_OWNER = "store"  # dueño de la evidencia que se rechaza (rechazar no mueve puntos)
_AUDIT_PATH = "/audit"
_LOGS_PATH = "/api/v1/action-logs/"
_MY_LOGS_PATH = "/api/v1/action-logs/mine/"
_ACTIONS_PATH = "/api/v1/actions/"
_PROFILE_PATH = "/api/v1/profile/me/"
_PROPOSALS_PATH = "/api/v1/campaigns/proposals/"

# Peticiones del navegador que se simulan: solo la cola (con su query) y solo la lista de propuestas.
_QUEUE_URL = re.compile(r"/api/v1/action-logs/\?status=PENDING_AUDIT")
_PROPOSALS_LIST_URL = re.compile(r"/api/v1/campaigns/proposals/(\?.*)?$")
_PROPOSAL_APPROVE_URL = "**/api/v1/campaigns/proposals/*/approve/"
_EMPTY_PAGE = {"count": 0, "next": None, "previous": None, "results": []}

_TAB_EVIDENCE = "Evidencias"
_TAB_PROPOSALS = "Propuestas de campañas"
_PROPOSAL_GROUP = "Filtrar propuestas por estado"
_CHIP_PENDING = "Pendientes"
_CHIP_REJECTED = "Rechazadas"
_BTN_APPROVE = "Aprobar"
_BTN_REJECT = "Rechazar"
_BTN_CONFIRM_REJECT = "Confirmar rechazo"
_BADGE_PENDING = "PENDIENTE"
_MSG_REASON_REQUIRED = "Indica el motivo del rechazo."
_MSG_APPROVE_FAILED = "Failed to approve evidence"
_NOTICE_APPROVED = "Propuesta aprobada. Ya es una campaña disponible para la comunidad."
_NOTICE_REJECTED = "Propuesta rechazada. El motivo quedó visible para quien la envió."

# En el stack desechable (AUTH_MODE=mock) aprobar de verdad es inofensivo; en un ambiente real no.
_APPROVE_PROPOSAL_FOR_REAL = env.AUTH_MODE == "mock"

_STATE: dict[str, Any] = {}


# --- privadas: datos y API ------------------------------------------------------------------


def _state(key: str) -> Any:
    """Read a value stored by the setup; a missing value means the setup did not run."""
    if key not in _STATE:
        raise RuntimeError(f"Falta '{key}' en el estado del módulo: revisa que el setup (_000) haya corrido")
    return _STATE[key]


def _make_png(size: int = 8) -> bytes:
    """Build a valid solid-green PNG in memory (JPG/PNG/WEBP up to 5 MB are accepted as evidence)."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    row = b"\x00" + b"\x2e\xa0\x43" * size  # filtro 0 + píxeles RGB
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )


def _campaign_dates(days: int = 3) -> tuple[str, str]:
    """Return (inicio, fin) como YYYY-MM-DD: mañana en Ciudad de México y `days` días después."""
    tomorrow = datetime.now(_MX_TZ).date() + timedelta(days=1)
    return tomorrow.isoformat(), (tomorrow + timedelta(days=days)).isoformat()


def _mx_iso(day: str, *, end_of_day: bool) -> str:
    """ISO datetime of `day` (YYYY-MM-DD) at 00:00:00 or 23:59:59 in Mexico City, like the frontend sends it."""
    moment = dtime(23, 59, 59) if end_of_day else dtime(0, 0, 0)
    return datetime.combine(date.fromisoformat(day), moment, tzinfo=_MX_TZ).isoformat()


def _catalog(api: ApiClient) -> list[dict[str, Any]]:
    """Return the active catalog actions (GET actions/)."""
    items = [item for item in api.pages(_OWNER, _ACTIONS_PATH) if item.get("id")]
    if not items:
        raise RuntimeError("El catálogo de acciones está vacío")
    return items


def _create_pending_log(api: ApiClient, owner: str) -> dict[str, Any]:
    """Register a photo action as `owner` and return {"id", "action", "owner"} of the new PENDING_AUDIT log.

    Tries the photo actions from the end of the catalog (Campañas uses the first ones) and moves on to the
    next one when the daily limit answers 429.
    """
    photo = [a for a in _catalog(api) if a.get("validation_type") == "PHOTO"]
    if not photo:
        raise RuntimeError("El catálogo no tiene acciones con validación por foto")
    png = _make_png()
    for action in reversed(photo):
        response = api.call(
            owner,
            "POST",
            _LOGS_PATH,
            multipart={
                "action_id": action["id"],
                "idempotency_key": str(uuid4()),
                "evidence": {"name": "e2e-evidencia.png", "mimeType": "image/png", "buffer": png},
            },
        )
        if response.status == 201:
            body = response.json()
            if body.get("status") != "PENDING_AUDIT":
                raise RuntimeError(f"La evidencia de {action['name']!r} quedó en {body.get('status')}, no pendiente")
            logger.info("Evidencia pendiente %s de %s con la acción %r", body["log_id"], owner, action["name"])
            return {"id": str(body["log_id"]), "action": action, "owner": owner}
        if response.status == 429:
            logger.info("Límite diario alcanzado en %r; se prueba otra acción con foto", action["name"])
            continue
        raise RuntimeError(f"POST {_LOGS_PATH} → {response.status}: {response.text()[:300]}")
    raise RuntimeError(
        f"{owner} ya agotó hoy el límite diario de todas las acciones con foto "
        "(cada corrida usa una por usuario y la limpieza no libera el cupo); "
        "repite mañana o usa un ambiente desechable"
    )


def _create_proposal(api: ApiClient, *, title: str, action_id: str) -> dict[str, Any]:
    """Submit a global campaign proposal as D, starting tomorrow, with one mission."""
    start, end = _campaign_dates()
    body = {
        "title": title,
        "description": unique_name("Propuesta de auditoría", max_length=100),
        "start_date": _mx_iso(start, end_of_day=False),
        "end_date": _mx_iso(end, end_of_day=True),
        "missions": [{"action_id": action_id, "target_count": 1}],
    }
    return api.json(_OWNER, "POST", _PROPOSALS_PATH, data=body, expected=(201,))


def _api_log(api: ApiClient, log: dict[str, Any]) -> dict[str, Any]:
    """Read a test log from its owner's own history (GET action-logs/mine/)."""
    for item in api.pages(log["owner"], _MY_LOGS_PATH):
        if str(item.get("id")) == log["id"]:
            return item
    raise RuntimeError(f"El registro {log['id']} no aparece en el historial de {log['owner']}")


def _api_proposal(api: ApiClient, proposal_id: str) -> dict[str, Any]:
    """Read one proposal as admin (GET campaigns/proposals/)."""
    for proposal in api.pages("admin", _PROPOSALS_PATH):
        if str(proposal.get("id")) == proposal_id:
            return proposal
    raise RuntimeError(f"La propuesta {proposal_id} no aparece en la API de propuestas")


def _total_points(api: ApiClient, owner: str) -> int:
    return int(api.json(owner, "GET", _PROFILE_PATH)["total_points"])


# --- privadas: UI ---------------------------------------------------------------------------


def _visible(page: Page, selector: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(page.locator(selector), timeout=timeout)


def _open_audit(page: Page, query: str = "", *, login: bool = True) -> None:
    """Sign in as admin (once per tab), open /audit and wait for the panel title."""
    if login:
        login_as(page, "admin")
    go_to(page, f"{_AUDIT_PATH}{query}")
    wait_for_app_ready(page)
    if not _visible(page, Locs.AUDIT_TITLE, timeout=env.DEFAULT_TIMEOUT):
        raise RuntimeError("No se ve 'Panel de revisión': ¿la cuenta admin tiene el rol ADMIN en este ambiente?")


def _tab_selected(page: Page, text: str) -> bool:
    tab = page.locator(Locs.audit_tab_with_text(text)).first
    return _visible(page, Locs.audit_tab_with_text(text)) and tab.get_attribute("aria-selected") == "true"


def _wait_card_gone(page: Page, selector: str, *, timeout: int = env.DEFAULT_TIMEOUT) -> bool:
    try:
        page.locator(selector).first.wait_for(state="hidden", timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


def _find_evidence_card(page: Page, log_id: str) -> None:
    """Wait for the card of `log_id`; explain it when the queue holds more than the UI can show."""
    if _visible(page, Locs.audit_card_with_log_id(log_id), timeout=env.DEFAULT_TIMEOUT):
        return
    queue = api_for_page(page).json("admin", "GET", _LOGS_PATH, params={"status": "PENDING_AUDIT"})
    total = queue.get("count") if isinstance(queue, dict) else len(queue)
    if isinstance(total, int) and total > _QUEUE_PAGE_SIZE:
        raise RuntimeError(
            f"La cola tiene {total} evidencias pendientes y el frontend solo muestra la primera página "
            f"({_QUEUE_PAGE_SIZE}, de las más antiguas): la evidencia de prueba {log_id} "
            "no se puede revisar desde la UI"
        )
    raise RuntimeError(f"La evidencia {log_id} no aparece en la cola de auditoría")


def _find_proposal_card(page: Page, title: str) -> bool:
    """Find the proposal card by its marked title, paging through the list (the UI pages it client-side)."""
    card = page.locator(Locs.li_with_text(title))
    for _ in range(_MAX_PROPOSAL_PAGES):
        if locator_has_visible_match(card, timeout=_SHORT_TIMEOUT):
            return True
        next_page = page.locator(Locs.AUDIT_PROPOSALS_NEXT_PAGE).first
        if not locator_has_visible_match(next_page, timeout=500) or next_page.is_disabled():
            return False
        next_page.click()
    return False


def _queue_or_error_settled(page: Page) -> bool:
    """True once the evidence tab left 'loading': it shows the list, the empty state or the error."""
    return any(
        _visible(page, selector, timeout=200)
        for selector in (Locs.AUDIT_ANY_EVIDENCE_CARD, Locs.AUDIT_QUEUE_EMPTY_TITLE, Locs.AUDIT_QUEUE_ERROR_TITLE)
    )


# --- tests ----------------------------------------------------------------------------------


def test_00_07_000_checkSetUp(page: Page) -> bool:
    """Crea con la API las 2 evidencias pendientes (una por usuario) y las 2 propuestas que usan los demás tests."""
    api = api_for_page(page)
    approve_log = _create_pending_log(api, _OWNER)
    reject_log = _create_pending_log(api, _REJECT_OWNER)
    mission_action = _catalog(api)[0]["id"]
    _STATE.update(
        approve_log=approve_log,
        reject_log=reject_log,
        approve_proposal=_create_proposal(
            api, title=unique_name("Auditoría aprobar", max_length=60), action_id=mission_action
        ),
        reject_proposal=_create_proposal(
            api, title=unique_name("Auditoría rechazar", max_length=60), action_id=mission_action
        ),
    )
    return True


def test_00_07_001_checkOpenAuditPanel(page: Page) -> bool:
    _open_audit(page)
    if not is_on_path(page, _AUDIT_PATH):
        logger.error("Se esperaba /audit, la URL es %s", page.url)
        return False
    if not _visible(page, Locs.AUDIT_SUBTITLE):
        logger.error("No se ve la descripción del panel")
        return False
    if not wait_until(lambda: _tab_selected(page, _TAB_EVIDENCE), page, timeout=_SHORT_TIMEOUT):
        logger.error("La pestaña 'Evidencias' no está seleccionada al abrir el panel")
        return False
    if not _visible(page, Locs.audit_tab_with_text(_TAB_PROPOSALS)):
        logger.error("No se ve la pestaña 'Propuestas de campañas'")
        return False
    if not wait_until(lambda: _queue_or_error_settled(page), page, timeout=env.DEFAULT_TIMEOUT):
        logger.error("La cola no terminó de cargar")
        return False
    if _visible(page, Locs.AUDIT_QUEUE_ERROR_TITLE, timeout=200):
        logger.error("La cola de auditoría muestra el error de carga")
        return False
    return True


def test_00_07_002_checkPendingEvidenceList(page: Page) -> bool:
    log = _state("approve_log")
    action = log["action"]
    _open_audit(page)
    _find_evidence_card(page, log["id"])
    card = page.locator(Locs.audit_card_with_log_id(log["id"])).first
    # Según la versión del frontend la tarjeta identifica al usuario por su id o por su correo.
    owner_refs = (api_for_page(page).user_id(log["owner"]), env.TEST_USERS[log["owner"]])
    expected = {
        "el nombre de la acción": (action["name"],),
        "el estado PENDIENTE": (_BADGE_PENDING,),
        "los puntos": (f"{action['points']} pts",),
        "el usuario (id o correo)": owner_refs,
    }
    text = card.inner_text()
    missing = [label for label, options in expected.items() if not any(option in text for option in options)]
    if missing:
        logger.error("La tarjeta no muestra: %s (texto: %r)", ", ".join(missing), text[:200])
        return False
    if not _visible(page, Locs.audit_evidence_image(action["name"]), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No se ve la foto de la evidencia de %r", action["name"])
        return False
    image = page.locator(Locs.audit_evidence_image(action["name"])).first
    loaded = wait_until(
        lambda: bool(image.evaluate("el => el.complete && el.naturalWidth > 0")), page, timeout=_SHORT_TIMEOUT
    )
    if not loaded:
        logger.error("La foto de la evidencia no cargó (el GET de la evidencia con token no devolvió una imagen)")
    return loaded


def test_00_07_003_checkApproveEvidence(page: Page) -> bool:
    log = _state("approve_log")
    api = api_for_page(page)
    points_before = _total_points(api, log["owner"])
    _open_audit(page)
    _find_evidence_card(page, log["id"])
    click_robust(page, Locs.audit_card_button(log["id"], _BTN_APPROVE))
    if not _wait_card_gone(page, Locs.audit_card_with_log_id(log["id"])):
        logger.error("La tarjeta de la evidencia aprobada no salió de la cola")
        return False
    if _visible(page, Locs.alert_with_text(_MSG_APPROVE_FAILED), timeout=500):
        logger.error("La UI mostró el error al aprobar")
        return False
    status = _api_log(api, log)["status"]
    if status != "APPROVED":
        logger.error("La API dejó la evidencia en %s, se esperaba APPROVED", status)
        return False
    expected_points = points_before + int(log["action"]["points"])
    if not wait_until(lambda: _total_points(api, log["owner"]) == expected_points, page, timeout=_SHORT_TIMEOUT):
        logger.error(
            "Los puntos de %s no subieron %s (antes %s, ahora %s)",
            log["owner"],
            log["action"]["points"],
            points_before,
            _total_points(api, log["owner"]),
        )
        return False
    return True


def test_00_07_004_checkRejectNeedsReason(page: Page) -> bool:
    log = _state("reject_log")
    api = api_for_page(page)
    decisions: list[str] = []

    def _record_decision(request: Request) -> None:
        if request.method == "PATCH" and "/audit/" in request.url:
            decisions.append(request.url)

    page.on("request", _record_decision)
    _open_audit(page)
    _find_evidence_card(page, log["id"])
    reason_input = page.locator(Locs.audit_reason_input_with_log_id(log["id"])).first

    # Sin motivo, y con solo espacios: avisa, no manda nada y la evidencia sigue pendiente.
    for attempt in ("", "   "):
        reason_input.fill(attempt)
        click_robust(page, Locs.audit_card_button(log["id"], _BTN_REJECT))
        if not _visible(page, Locs.alert_with_text(_MSG_REASON_REQUIRED)):
            logger.error("No apareció '%s' al rechazar con el motivo %r", _MSG_REASON_REQUIRED, attempt)
            return False
        if decisions:
            logger.error("Se mandó un PATCH sin motivo: %s", decisions)
            return False
    if not _visible(page, Locs.audit_card_with_log_id(log["id"]), timeout=500):
        logger.error("La tarjeta desapareció aunque no se indicó el motivo")
        return False
    if _api_log(api, log)["status"] != "PENDING_AUDIT":
        logger.error("La evidencia cambió de estado sin motivo")
        return False

    # Con motivo: se rechaza y la API guarda el motivo.
    reason = unique_name("Motivo de rechazo", max_length=80)
    reason_input.fill(reason)
    click_robust(page, Locs.audit_card_button(log["id"], _BTN_REJECT))
    if not _wait_card_gone(page, Locs.audit_card_with_log_id(log["id"])):
        logger.error("La tarjeta rechazada no salió de la cola")
        return False
    saved = _api_log(api, log)
    if saved["status"] != "REJECTED" or saved.get("rejection_reason") != reason:
        logger.error(
            "La API tiene estado=%s motivo=%r; se esperaba REJECTED y %r",
            saved["status"],
            saved.get("rejection_reason"),
            reason,
        )
        return False
    return True


def test_00_07_005_checkApproveProposal(page: Page) -> bool:
    proposal = _state("approve_proposal")
    title, proposal_id = proposal["title"], str(proposal["id"])
    api = api_for_page(page)
    # Fuera del stack desechable aprobar invitaría a todos los usuarios reales: se intercepta el POST.
    guard = None
    if not _APPROVE_PROPOSAL_FOR_REAL:
        guard = mock_api_json(
            page,
            _PROPOSAL_APPROVE_URL,
            {"id": proposal_id, "title": title, "approval_status": "APPROVED"},
            method="POST",
        )
    try:
        _open_audit(page, "?tab=propuestas")
        if not _find_proposal_card(page, title):
            logger.error("La propuesta %r no aparece entre las pendientes", title)
            return False
        click_robust(page, Locs.audit_proposal_button(title, _BTN_APPROVE))
        if not _visible(page, Locs.text_exact(_NOTICE_APPROVED), timeout=env.DEFAULT_TIMEOUT):
            logger.error("No apareció el aviso '%s'", _NOTICE_APPROVED)
            return False
        status = _api_proposal(api, proposal_id)["approval_status"]
        if guard is None:
            if status != "APPROVED":
                logger.error("La API dejó la propuesta en %s, se esperaba APPROVED", status)
                return False
            return _wait_card_gone(page, Locs.li_with_text(title))
        sent = [request.url for request in guard.requests]
        if len(sent) != 1 or not sent[0].endswith(f"/proposals/{proposal_id}/approve/"):
            logger.error("Se esperaba un POST a .../proposals/%s/approve/, se mandó: %s", proposal_id, sent)
            return False
        if status != "PENDING":
            logger.error("La propuesta cambió a %s: la petición simulada llegó al backend real", status)
            return False
        return True
    finally:
        if guard is not None:
            guard.restore()


def test_00_07_006_checkRejectProposalWithReason(page: Page) -> bool:
    proposal = _state("reject_proposal")
    title, proposal_id = proposal["title"], str(proposal["id"])
    api = api_for_page(page)
    _open_audit(page, "?tab=propuestas")
    if not _find_proposal_card(page, title):
        logger.error("La propuesta %r no aparece entre las pendientes", title)
        return False
    click_robust(page, Locs.audit_proposal_button(title, _BTN_REJECT))
    textarea = page.locator(f"{Locs.li_with_text(title)}//textarea").first
    if not locator_has_visible_match(textarea, timeout=_SHORT_TIMEOUT):
        logger.error("No se abrió el campo del motivo del rechazo")
        return False
    confirm = page.locator(Locs.audit_proposal_button(title, _BTN_CONFIRM_REJECT)).first
    if not confirm.is_disabled():
        logger.error("'Confirmar rechazo' debe estar deshabilitado mientras no haya motivo")
        return False
    reason = unique_name("Motivo de la propuesta", max_length=80)
    textarea.fill(reason)
    if confirm.is_disabled():
        logger.error("'Confirmar rechazo' sigue deshabilitado con un motivo escrito")
        return False
    click_robust(page, Locs.audit_proposal_button(title, _BTN_CONFIRM_REJECT))
    if not _visible(page, Locs.text_exact(_NOTICE_REJECTED), timeout=env.DEFAULT_TIMEOUT):
        logger.error("No apareció el aviso '%s'", _NOTICE_REJECTED)
        return False
    saved = _api_proposal(api, proposal_id)
    if saved["approval_status"] != "REJECTED" or saved.get("rejection_reason") != reason:
        logger.error(
            "La API tiene estado=%s motivo=%r; se esperaba REJECTED y %r",
            saved["approval_status"],
            saved.get("rejection_reason"),
            reason,
        )
        return False
    # En 'Rechazadas' la tarjeta muestra el motivo guardado.
    click_filter_chip(page, _PROPOSAL_GROUP, _CHIP_REJECTED)
    if not _find_proposal_card(page, title):
        logger.error("La propuesta rechazada no aparece en el filtro 'Rechazadas'")
        return False
    return locator_has_visible_match(page.locator(Locs.li_with_text(title)).get_by_text(reason, exact=True))


def test_00_07_007_checkProposalsTabFromUrl(page: Page) -> bool:
    _open_audit(page, "?tab=propuestas")
    if not wait_until(lambda: _tab_selected(page, _TAB_PROPOSALS), page, timeout=_SHORT_TIMEOUT):
        logger.error("Con ?tab=propuestas no queda seleccionada 'Propuestas de campañas'")
        return False
    if _tab_selected(page, _TAB_EVIDENCE):
        logger.error("'Evidencias' también aparece seleccionada")
        return False
    chip = page.get_by_role("group", name=_PROPOSAL_GROUP, exact=True).get_by_role(
        "button", name=_CHIP_PENDING, exact=True
    )
    chip_pressed = locator_has_visible_match(chip, timeout=_SHORT_TIMEOUT) and (
        chip.first.get_attribute("aria-pressed") == "true"
    )
    if not chip_pressed:
        logger.error("El filtro de propuestas no abre en 'Pendientes'")
        return False
    if any(_visible(page, sel, timeout=500) for sel in (Locs.AUDIT_ANY_EVIDENCE_CARD, Locs.AUDIT_QUEUE_EMPTY_TITLE)):
        logger.error("Se ve la cola de evidencias dentro de la pestaña de propuestas")
        return False
    # Cambiar de pestaña actualiza la URL; una pestaña desconocida cae en 'Evidencias'.
    click_robust(page, Locs.audit_tab_with_text(_TAB_EVIDENCE))
    switched = wait_until(
        lambda: "tab=evidencias" in page.url and _tab_selected(page, _TAB_EVIDENCE), page, timeout=_SHORT_TIMEOUT
    )
    if not switched:
        logger.error("Al elegir 'Evidencias' la URL no quedó con tab=evidencias (URL: %s)", page.url)
        return False
    go_to(page, f"{_AUDIT_PATH}?tab=no-existe")
    wait_for_app_ready(page)
    return wait_until(lambda: _tab_selected(page, _TAB_EVIDENCE), page, timeout=_SHORT_TIMEOUT)


def test_00_07_008_checkEmptyAndErrorStates(page: Page) -> bool:
    login_as(page, "admin")

    # Cola de evidencias vacía.
    empty_queue = mock_api_json(page, _QUEUE_URL, _EMPTY_PAGE)
    _open_audit(page, login=False)
    if not _visible(page, Locs.AUDIT_QUEUE_EMPTY_TITLE, timeout=env.DEFAULT_TIMEOUT):
        logger.error("Con la cola vacía no se ve 'No hay evidencias pendientes'")
        return False
    empty_queue.restore()

    # Error al cargar la cola, y Reintentar la recupera.
    failing_queue = mock_api_error(page, _QUEUE_URL, status=500)
    page.reload(wait_until="domcontentloaded")
    wait_for_app_ready(page)
    if not _visible(page, Locs.AUDIT_QUEUE_ERROR_TITLE, timeout=env.DEFAULT_TIMEOUT):
        logger.error("Con error 500 no se ve 'No se pudo cargar la cola de auditoría'")
        return False
    failing_queue.restore()
    click_robust(page, Locs.AUDIT_QUEUE_RETRY)
    queue_recovered = wait_until(
        lambda: _queue_or_error_settled(page) and not _visible(page, Locs.AUDIT_QUEUE_ERROR_TITLE, timeout=200),
        page,
        timeout=env.DEFAULT_TIMEOUT,
    )
    if not queue_recovered:
        logger.error("Reintentar no recuperó la cola de evidencias")
        return False

    # Propuestas: lista vacía.
    empty_proposals = mock_api_json(page, _PROPOSALS_LIST_URL, _EMPTY_PAGE)
    go_to(page, f"{_AUDIT_PATH}?tab=propuestas")
    wait_for_app_ready(page)
    if not _visible(page, Locs.AUDIT_PROPOSALS_EMPTY_TITLE, timeout=env.DEFAULT_TIMEOUT):
        logger.error("Con 0 propuestas no se ve 'No hay propuestas'")
        return False
    empty_proposals.restore()

    # Propuestas: error al cargar, y Reintentar la recupera.
    failing_proposals = mock_api_error(page, _PROPOSALS_LIST_URL, status=500)
    page.reload(wait_until="domcontentloaded")
    wait_for_app_ready(page)
    if not _visible(page, Locs.AUDIT_PROPOSALS_ERROR_TITLE, timeout=env.DEFAULT_TIMEOUT):
        logger.error("Con error 500 no se ve 'No se pudieron cargar las propuestas'")
        return False
    failing_proposals.restore()
    click_robust(page, Locs.AUDIT_PROPOSALS_RETRY)
    recovered = wait_until(
        lambda: not _visible(page, Locs.AUDIT_PROPOSALS_ERROR_TITLE, timeout=200), page, timeout=env.DEFAULT_TIMEOUT
    )
    if not recovered:
        logger.error("Reintentar no recuperó la lista de propuestas")
    return recovered
