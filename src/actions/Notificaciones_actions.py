"""Acciones del módulo 10 · Notificaciones (tests/Notificaciones/test_Notificaciones.py).

Las notificaciones de prueba salen de un flujo real que solo toca cuentas de prueba: S propone una
campaña con el marcador de la corrida (API) y A la rechaza (API). El rechazo notifica solo al autor
(CAMPAIGN_REJECTED). Nunca se aprueba una propuesta, porque eso notificaría a todos los usuarios.
Las aserciones se acotan a las notificaciones cuyo mensaje cita el título marcado, porque otros
módulos pueden notificar a S en paralelo.
EE = 00 es provisional hasta que se haga el reparto de equipos.
"""

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from playwright.sync_api import Locator, Page, WebSocket

from src.utils.api import ApiClient, api_for_page
from src.utils.common_actions import go_to, login_as
from src.utils.helpers import locator_has_visible_match, wait_for_app_ready, wait_for_path, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import capture_json_response, fake_notifications_socket, mock_api_error, mock_api_json
from src.utils.test_data import run_id, unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_LONG_TIMEOUT = 15_000
_NOTIFICATIONS_PATH = "/api/v1/notifications/"
_NOTIFICATIONS_GLOB = "**/api/v1/notifications/"
_NOTIFICATION_DETAIL_GLOB = "**/api/v1/notifications/*/"
_UNREAD_COUNT_PATH = "/api/v1/notifications/unread-count/"
_PROPOSALS_PATH = "/api/v1/campaigns/proposals/"
_ACTIONS_PATH = "/api/v1/actions/"
_TZ = ZoneInfo("America/Mexico_City")
_REJECTION_REASON = "Rechazo de prueba E2E para notificaciones"
_ALL_READ_TEXT = "Estás al día."
_EMPTY_PAGE: dict[str, Any] = {"count": 0, "next": None, "previous": None, "results": [], "unread_count": 0}
_BADGE_TITLE = "¡Nueva insignia desbloqueada!"
_BADGE_NAMES = ("Guardián del agua", "Héroe del reciclaje")
# Usuario de prueba que intenta tocar las notificaciones de S (TC-10-009); no es admin a propósito.
_OTHER_USER_ROLE = "leader"

# Estado compartido por los tests del módulo (mismo proceso, en orden): títulos N1..N3 y marcador.
_STATE: dict[str, Any] = {}


# --- privadas: datos vía API ----------------------------------------------------------------


def _active_action_id(api: ApiClient) -> str:
    body = api.json("student", "GET", _ACTIONS_PATH)
    items = body.get("results", []) if isinstance(body, dict) else body
    if not items:
        raise RuntimeError("El catálogo de acciones está vacío; no se puede armar una misión")
    return str(items[0]["id"])


def _campaign_dates(*, days: int = 3) -> tuple[str, str]:
    """Start tomorrow at 09:00 and end `days` later, in America/Mexico_City (ISO with offset)."""
    tomorrow = datetime.now(_TZ).date() + timedelta(days=1)
    start = datetime.combine(tomorrow, dtime(9, 0), tzinfo=_TZ)
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


def _find_api_notification(api: ApiClient, title: str) -> dict[str, Any] | None:
    """Return the student's notification whose message quotes `title`, or None."""
    needle = f'"{title}"'
    for item in api.pages("student", _NOTIFICATIONS_PATH):
        if needle in str(item.get("message", "")):
            return item
    return None


def _is_read_in_api(api: ApiClient, title: str) -> bool:
    item = _find_api_notification(api, title)
    return bool(item and item.get("is_read"))


def _propose_and_reject(api: ApiClient) -> str:
    """Make S propose a marked campaign and A reject it, so only S gets CAMPAIGN_REJECTED.

    Never approves: an approval would notify every user. Returns the marked title.
    """
    title = unique_name("Propuesta rechazo", max_length=50)
    start, end = _campaign_dates()
    proposal = api.json(
        "student",
        "POST",
        _PROPOSALS_PATH,
        data={
            "title": title,
            "description": unique_name("Descripción", max_length=100),
            "start_date": start,
            "end_date": end,
            "missions": [{"action_id": _active_action_id(api), "target_count": 1}],
        },
        expected=(201,),
    )
    api.json(
        "admin",
        "POST",
        f"{_PROPOSALS_PATH}{proposal['id']}/reject/",
        data={"rejection_reason": _REJECTION_REASON},
    )
    logger.info("Propuesta %s rechazada", title)
    return title


def _create_rejected_proposal_notification(page: Page, api: ApiClient) -> str:
    """Propose + reject and wait until the notification shows up in S's API list."""
    title = _propose_and_reject(api)
    if not wait_until(lambda: _find_api_notification(api, title) is not None, page, timeout=_LONG_TIMEOUT, poll_ms=300):
        raise RuntimeError(f"La notificación de {title!r} no llegó a S en {_LONG_TIMEOUT} ms")
    return title


def _ensure_setup(page: Page, api: ApiClient) -> None:
    """Create the three notifications N1..N3 once per run (idempotent inside the module)."""
    if _STATE.get("titles"):
        return
    titles = [_create_rejected_proposal_notification(page, api) for _ in range(3)]
    _STATE.update({"marker": run_id(), "titles": titles})
    logger.info("Notificaciones de prueba listas: %s", titles)


def _is_notifications_list(url: str) -> bool:
    return urlsplit(url).path == _NOTIFICATIONS_PATH


def _badge_notification(badge_name: str) -> dict[str, Any]:
    """A BADGE_EARNED payload exactly as the backend sends it (template: Obtuviste la insignia "X".)."""
    return {
        "id": str(uuid.uuid4()),
        "title": _BADGE_TITLE,
        "message": f'Obtuviste la insignia "{badge_name}".',
        "notification_type": "BADGE_EARNED",
        "is_read": False,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _is_badge_patch_for(request: Any, notification_id: str) -> bool:
    if request.method != "PATCH" or notification_id not in request.url:
        return False
    try:
        return json.loads(request.post_data or "{}") == {"is_read": True}
    except ValueError:
        return False


# --- privadas: UI ----------------------------------------------------------------------------


def _card(page: Page, title: str) -> Locator:
    """The notification card whose message quotes `title` (the quotes avoid prefix collisions)."""
    return page.locator(Locs.NOTIFICATIONS_ITEM).filter(has_text=f'"{title}"')


def _card_visible(page: Page, title: str, *, timeout: int) -> bool:
    return locator_has_visible_match(_card(page, title), timeout=timeout)


def _wait_list_ready(page: Page) -> bool:
    wait_for_app_ready(page)
    if not locator_has_visible_match(page.locator(Locs.NOTIFICATIONS_TITLE), timeout=_LONG_TIMEOUT):
        logger.error("No se ve el título 'Notificaciones' en %s", page.url)
        return False
    return True


def _open_notifications_page(page: Page) -> bool:
    go_to(page, "/notifications")
    return _wait_list_ready(page)


def _subtitle_text(page: Page) -> str | None:
    subtitle = page.locator(Locs.NOTIFICATIONS_SUBTITLE).first
    if subtitle.count() == 0:
        return None
    return (subtitle.text_content() or "").strip()


def _subtitle_unread(page: Page) -> int | None:
    """Parse the unread count out of the subtitle ("Estás al día." means 0)."""
    text = _subtitle_text(page)
    if text == _ALL_READ_TEXT:
        return 0
    match = re.fullmatch(r"Tienes (\d+) notificaciones sin leer\.", text or "")
    return int(match.group(1)) if match else None


def _badge_unread(page: Page) -> int:
    """Read the count from the navbar bell badge (0 when the badge is not rendered)."""
    badge = page.locator(Locs.NOTIFICATIONS_BELL_BADGE).first
    if badge.count() == 0:
        return 0
    match = re.search(r"(\d+) notificaciones sin leer", badge.get_attribute("aria-label") or "")
    return int(match.group(1)) if match else 0


def _wait_subtitle_unread(page: Page, expected: int, *, timeout: int = _LONG_TIMEOUT) -> bool:
    return wait_until(lambda: _subtitle_unread(page) == expected, page, timeout=timeout)


def _counter_dropped(page: Page, api: ApiClient, before: int) -> bool:
    shown = _subtitle_unread(page)
    if shown is None:
        return False
    return shown == before - 1 or shown == api.json("student", "GET", _UNREAD_COUNT_PATH)["unread_count"]


def _visible_text(scope: Locator, text: str, *, timeout: int) -> bool:
    return locator_has_visible_match(scope.get_by_text(text, exact=True), timeout=timeout)


def _record_socket_frames(ws: WebSocket, frames: list[str]) -> None:
    if "/ws/notifications/" in ws.url:
        ws.on("framereceived", lambda payload: frames.append(str(payload)))


# --- tests ----------------------------------------------------------------------------------


def test_00_10_001_checkNotificationsList(page: Page) -> bool:
    api = api_for_page(page)
    _ensure_setup(page, api)
    login_as(page, "student")
    body = capture_json_response(page, _is_notifications_list, lambda: go_to(page, "/notifications"))
    if not _wait_list_ready(page):
        return False

    titles = _STATE["titles"]
    missing = [title for title in titles if not _card_visible(page, title, timeout=_LONG_TIMEOUT)]
    if missing:
        logger.error("No se ven las notificaciones de prueba: %s", missing)
        return False

    expected = int(body["unread_count"])
    if not _wait_subtitle_unread(page, expected):
        # Otro módulo pudo notificar a S entre la lectura y el render: vale si la UI ya coincide con el servidor.
        fresh = api.json("student", "GET", _UNREAD_COUNT_PATH)["unread_count"]
        if _subtitle_unread(page) != fresh:
            logger.error("El contador muestra %s y el servidor dice %s", _subtitle_text(page), fresh)
            return False
        logger.warning("El contador cambió entre la lectura (%s) y el render (%s)", expected, fresh)

    shown = _subtitle_unread(page)
    if shown is None:
        logger.error("El subtítulo no tiene el formato esperado: %s", _subtitle_text(page))
        return False
    if not wait_until(lambda: _badge_unread(page) == shown, page, timeout=_SHORT_TIMEOUT):
        logger.error("El globo del navbar muestra %s y la lista %s", _badge_unread(page), shown)
        return False
    return True


def test_00_10_002_checkMarkAsRead(page: Page) -> bool:
    api = api_for_page(page)
    login_as(page, "student")
    if not _open_notifications_page(page):
        return False

    title = _STATE["titles"][0]
    card = _card(page, title)
    if not locator_has_visible_match(card, timeout=_LONG_TIMEOUT):
        logger.error("No se ve la notificación %s", title)
        return False
    before = _subtitle_unread(page)
    if not before:
        logger.error("Se esperaban notificaciones sin leer antes de marcar, subtítulo: %s", _subtitle_text(page))
        return False

    card.get_by_role("button", name="Marcar como leída").click()
    if not wait_until(
        lambda: card.get_by_role("button", name="Marcar como leída").count() == 0, page, timeout=_SHORT_TIMEOUT
    ):
        logger.error("El botón 'Marcar como leída' sigue visible después de marcarla")
        return False
    if not wait_until(lambda: _is_read_in_api(api, title), page, timeout=_LONG_TIMEOUT):
        logger.error("La API no marcó como leída la notificación %s", title)
        return False
    # Otro módulo pudo notificar a S durante la prueba: vale bajar exactamente 1 o coincidir con el servidor.
    if not wait_until(lambda: _counter_dropped(page, api, before), page, timeout=_LONG_TIMEOUT):
        logger.error("El contador no bajó de %s: %s", before, _subtitle_text(page))
        return False
    return True


def test_00_10_003_checkMarkAllAsRead(page: Page) -> bool:
    api = api_for_page(page)
    login_as(page, "student")
    if not _open_notifications_page(page):
        return False

    mark_all = page.locator(Locs.button_with_text("Marcar todo")).first
    if not locator_has_visible_match(mark_all, timeout=_LONG_TIMEOUT):
        logger.error("No se ve el botón 'Marcar todo'")
        return False
    mark_all.click()

    if not wait_until(lambda: _subtitle_text(page) == _ALL_READ_TEXT, page, timeout=_SHORT_TIMEOUT):
        logger.error("Después de 'Marcar todo' el subtítulo es %s", _subtitle_text(page))
        return False
    if not wait_until(lambda: page.locator(Locs.NOTIFICATIONS_BELL_BADGE).count() == 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("El globo del navbar sigue visible después de 'Marcar todo'")
        return False

    unread = api.json("student", "GET", _UNREAD_COUNT_PATH)["unread_count"]
    if unread != 0:
        # Pudo llegar una notificación nueva en paralelo: se revisa que las marcadas sí estén leídas.
        logger.warning("El servidor reporta %s sin leer tras 'Marcar todo' (posible carrera con otro módulo)", unread)
        if not all(_is_read_in_api(api, title) for title in _STATE["titles"]):
            logger.error("Alguna notificación de prueba sigue sin leer en la API")
            return False
    return True


def test_00_10_004_checkDeleteNotification(page: Page) -> bool:
    api = api_for_page(page)
    login_as(page, "student")
    if not _open_notifications_page(page):
        return False

    title, survivor = _STATE["titles"][1], _STATE["titles"][2]
    card = _card(page, title)
    if not locator_has_visible_match(card, timeout=_LONG_TIMEOUT):
        logger.error("No se ve la notificación %s para eliminar", title)
        return False
    # Espera la respuesta del DELETE: si se recarga antes, la petición podría abortarse.
    with page.expect_response(
        lambda response: response.request.method == "DELETE" and _NOTIFICATIONS_PATH in response.url,
        timeout=_LONG_TIMEOUT,
    ) as delete_info:
        card.get_by_role("button", name="Eliminar notificación").click()
    if not delete_info.value.ok:
        logger.error("DELETE de la notificación respondió %s", delete_info.value.status)
        return False
    if not wait_until(lambda: _card(page, title).count() == 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("La notificación eliminada sigue en la lista")
        return False

    page.reload(wait_until="domcontentloaded")
    if not _wait_list_ready(page):
        return False
    if not _card_visible(page, survivor, timeout=_LONG_TIMEOUT):
        logger.error("Después de recargar no llegó la lista (falta %s)", survivor)
        return False
    if _card(page, title).count() != 0:
        logger.error("La notificación eliminada reapareció después de recargar")
        return False
    if _find_api_notification(api, title) is not None:
        logger.error("La API sigue devolviendo la notificación eliminada")
        return False
    return True


def test_00_10_005_checkRealtimeNotification(page: Page) -> bool:
    api = api_for_page(page)
    frames: list[str] = []
    page.on("websocket", lambda ws: _record_socket_frames(ws, frames))
    login_as(page, "student")
    go_to(page, "/notifications")
    if not _wait_list_ready(page):
        return False
    if not wait_until(lambda: any('"auth.ok"' in frame for frame in frames), page, timeout=_LONG_TIMEOUT):
        logger.error("El socket real de notificaciones no se autenticó (auth.ok)")
        return False

    # Marca la página: si hubiera recarga, la bandera desaparece.
    page.evaluate("() => { window.__e2eLoaded = true; }")
    # No espera a la API: el aviso dura 6 s y hay que verlo en cuanto llega por el socket.
    title = _propose_and_reject(api)

    toast = page.locator(Locs.NOTIFICATIONS_TOAST).filter(has_text=f'"{title}"')
    if not locator_has_visible_match(toast, timeout=_LONG_TIMEOUT):
        logger.error("No apareció el aviso en tiempo real para %s", title)
        return False
    if not _visible_text(toast, "Tu propuesta fue rechazada", timeout=_SHORT_TIMEOUT):
        logger.error("El aviso no muestra 'Tu propuesta fue rechazada'")
        return False
    if not _card_visible(page, title, timeout=_LONG_TIMEOUT):
        logger.error("La notificación no apareció en la lista sin recargar")
        return False
    if page.evaluate("() => window.__e2eLoaded === true") is not True:
        logger.error("La página se recargó: la notificación no llegó por el socket")
        return False
    return True


def test_00_10_006_checkEmptyState(page: Page) -> bool:
    fake_notifications_socket(page)  # aísla la prueba de avisos reales de otros módulos
    mock_api_json(page, _NOTIFICATIONS_GLOB, _EMPTY_PAGE)
    login_as(page, "student")
    if not _open_notifications_page(page):
        return False
    if not locator_has_visible_match(page.locator(Locs.NOTIFICATIONS_EMPTY_TEXT), timeout=_LONG_TIMEOUT):
        logger.error("No se ve 'No tienes notificaciones.'")
        return False
    if _subtitle_text(page) != _ALL_READ_TEXT:
        logger.error("Con la lista vacía el subtítulo debe ser 'Estás al día.', es: %s", _subtitle_text(page))
        return False
    if page.locator(Locs.NOTIFICATIONS_BELL_BADGE).count() != 0:
        logger.error("Con cero sin leer no debe haber globo en el navbar")
        return False
    return True


def test_00_10_007_checkLoadError(page: Page) -> bool:
    fake_notifications_socket(page)  # aísla la prueba de avisos reales de otros módulos
    mock_api_error(page, _NOTIFICATIONS_GLOB)
    login_as(page, "student")
    if not _open_notifications_page(page):
        return False
    if not locator_has_visible_match(page.locator(Locs.NOTIFICATIONS_ERROR_ALERT), timeout=_LONG_TIMEOUT):
        logger.error("No se ve el aviso 'No se pudieron cargar las notificaciones.'")
        return False
    if page.locator(Locs.NOTIFICATIONS_EMPTY_TEXT).count() != 0:
        logger.error("Con error no debe mostrarse el estado vacío")
        return False
    return True


def test_00_10_008_checkBadgeCelebration(page: Page) -> bool:
    socket = fake_notifications_socket(page, unread=0)
    list_mock = mock_api_json(page, _NOTIFICATIONS_GLOB, _EMPTY_PAGE)
    patches = mock_api_json(page, _NOTIFICATION_DETAIL_GLOB, {}, method="PATCH")
    login_as(page, "student")
    go_to(page, "/notifications")
    if not _wait_list_ready(page):
        return False
    if not wait_until(lambda: socket.connected, page, timeout=_LONG_TIMEOUT):
        logger.error("El socket falso de notificaciones no se conectó")
        return False

    # El socket recarga la lista al autenticarse (auth.ok); si el push llegara antes, la recarga lo borraría.
    if not wait_until(lambda: len(list_mock.requests) >= 2, page, timeout=_LONG_TIMEOUT):
        logger.error("La app no recargó la lista tras autenticar el socket")
        return False

    first, second = _badge_notification(_BADGE_NAMES[0]), _badge_notification(_BADGE_NAMES[1])
    socket.push(first)
    socket.push(second)

    dialog = page.locator(Locs.NOTIFICATIONS_BADGE_DIALOG)
    if not locator_has_visible_match(dialog, timeout=_LONG_TIMEOUT):
        logger.error("No se abrió la celebración de la insignia")
        return False
    if not locator_has_visible_match(page.locator(Locs.element_with_test_id("confetti")), timeout=_SHORT_TIMEOUT):
        logger.error("No se ve el confeti de la celebración")
        return False
    if not _visible_text(dialog, "¡Insignia desbloqueada!", timeout=_SHORT_TIMEOUT):
        logger.error("Falta el título '¡Insignia desbloqueada!'")
        return False
    if not _visible_text(dialog, _BADGE_NAMES[0], timeout=_SHORT_TIMEOUT):
        logger.error("Falta el nombre de la primera insignia: %s", _BADGE_NAMES[0])
        return False
    if not _visible_text(dialog, "Tienes 1 insignia más por ver", timeout=_SHORT_TIMEOUT):
        logger.error("Falta el aviso de la cola 'Tienes 1 insignia más por ver'")
        return False

    dialog.get_by_role("button", name="Siguiente").first.click()
    if not _visible_text(dialog, _BADGE_NAMES[1], timeout=_LONG_TIMEOUT):
        logger.error("'Siguiente' no mostró la segunda insignia: %s", _BADGE_NAMES[1])
        return False

    dialog.get_by_role("link", name="Ver mis insignias").first.click()
    wait_for_path(page, "/profile")
    if not wait_until(
        lambda: any(_is_badge_patch_for(request, second["id"]) for request in patches.requests),
        page,
        timeout=_SHORT_TIMEOUT,
    ):
        logger.error("No se mandó el PATCH is_read=true de la insignia al abrir el perfil")
        return False
    return True


def test_00_10_009_checkCannotTouchOthersNotification(page: Page) -> bool:
    api = api_for_page(page)
    title = _create_rejected_proposal_notification(page, api)
    notification = _find_api_notification(api, title)
    if notification is None or notification.get("is_read"):
        raise RuntimeError(f"La notificación de {title!r} no quedó sin leer para S")
    detail_path = f"{_NOTIFICATIONS_PATH}{notification['id']}/"

    # El backend filtra por dueño, así que para otro usuario la notificación "no existe" (404, no 403).
    for method, data in (("PATCH", {"is_read": True}), ("DELETE", None)):
        status = api.call(_OTHER_USER_ROLE, method, detail_path, data=data).status
        if status != 404:
            logger.error("%s de la notificación de S como %s → %s, se esperaba 404", method, _OTHER_USER_ROLE, status)
            return False
    others = {str(item.get("id")) for item in api.pages(_OTHER_USER_ROLE, _NOTIFICATIONS_PATH)}
    if str(notification["id"]) in others:
        logger.error("La notificación de S aparece en la lista de %s", _OTHER_USER_ROLE)
        return False

    stored = _find_api_notification(api, title)
    if stored is None or stored.get("is_read"):
        logger.error("La notificación de S cambió tras los intentos de %s: %s", _OTHER_USER_ROLE, stored)
        return False

    login_as(page, "student")
    if not _open_notifications_page(page):
        return False
    card = _card(page, title)
    if not locator_has_visible_match(card, timeout=_LONG_TIMEOUT):
        logger.error("S ya no ve su notificación %s", title)
        return False
    if not locator_has_visible_match(card.get_by_role("button", name="Marcar como leída"), timeout=_SHORT_TIMEOUT):
        logger.error("La notificación de S ya no aparece como no leída en la UI")
        return False
    return True
