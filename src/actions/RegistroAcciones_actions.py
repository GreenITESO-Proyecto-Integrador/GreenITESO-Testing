"""Acciones del módulo 06 · Registro de acciones /actions/register (tests/equipo1/RegistroAcciones/).

EE = 01: módulo del equipo 1 ("Actions, points"), probado por el equipo 3 (docs/peer-testing-friday.md, T3-02/T3-05).

Usuario: ``actions`` (TEST_ACTIONS_EMAIL), propio del módulo. Registrar cambia sus puntos y gasta su cupo
diario por acción, así que no se usa ``student`` (lo comparten 9 módulos en paralelo) ni ``store`` o
``campaign_leader`` (Auditoría gasta con ellos el cupo de la acción con foto).

Datos reales vs. mocks:
- 001 registra de verdad una acción SIN EVIDENCIA (se aprueba y suma puntos) y 002 una con FOTO (queda
  pendiente de auditoría y aparece en /audit para los admins). 006 llena por API el cupo diario de la acción
  de 001 y luego intenta registrarla desde la UI. La limpieza de la corrida rechaza todos esos registros
  (revierte los puntos), pero **no libera el cupo del día**: el backend cuenta también los rechazados.
  Cada corrida elige acciones con cupo; si ya no queda ninguna, el test falla con "BLOQUEADO".
- 003, 004, 005, 007 y 008 solo validan el formulario: el POST de registro queda interceptado (503), así
  que, aunque la validación del cliente fallara, nunca se registra nada de verdad.
"""

from collections import Counter
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.sync_api import Page, Response

from src.configs import environment as env
from src.utils.api import ApiClient, api_for_page
from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import is_on_path, locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import RouteHandle, mock_api_error
from src.utils.test_data import make_png

logger = get_logger(__name__)

_ROLE = "actions"
_SHORT_TIMEOUT = 5_000
_LONG_TIMEOUT = env.DEFAULT_TIMEOUT
_MX_TZ = ZoneInfo("America/Mexico_City")  # el backend cuenta el límite diario por día local

_REGISTER_PATH = "/actions/register"
_ACTIONS_PATH = "/api/v1/actions/"
_LOGS_PATH = "/api/v1/action-logs/"
_MINE_PATH = "/api/v1/action-logs/mine/"
_PROFILE_PATH = "/api/v1/profile/me/"
_LOGS_POST_GLOB = "**/api/v1/action-logs/"

_MAX_EVIDENCE_BYTES = 5 * 1024 * 1024  # MAX_EVIDENCE_FILE_BYTES del frontend
_MAX_FILL = 10  # registros extra que 006 acepta hacer por API para llegar al límite diario

# Textos de pages/ActionLogForm, lib/action-log-form.ts y lib/api/errors.ts
_SUMMARY_APPROVED = "Los puntos ya se acreditaron."
_SUMMARY_PENDING = "Quedó pendiente de auditoría. Los puntos se acreditan cuando se apruebe la evidencia."
_ERROR_SELECT_ACTION = "Selecciona una acción del catálogo."
_ERROR_PHOTO_REQUIRED = "Esta acción requiere evidencia fotográfica."
_ERROR_TOO_BIG = "La evidencia no puede superar 5 MB."
_ERROR_DAILY_LIMIT = "Ya alcanzaste el límite diario de esta acción."
_PLACEHOLDER_OPTION = "Selecciona una acción"

# Estado compartido entre los tests del módulo (corren en orden en el mismo proceso).
_STATE: dict[str, Any] = {}


# --- privadas: datos de la API ----------------------------------------------------------------


def _catalog(api: ApiClient) -> list[dict[str, Any]]:
    """Active catalog actions, as the form lists them."""
    items = [item for item in api.pages(_ROLE, _ACTIONS_PATH) if item.get("id") and item.get("is_active", True)]
    if not items:
        raise RuntimeError("El catálogo de acciones está vacío")
    return items


def _of_type(items: list[dict[str, Any]], validation: str) -> list[dict[str, Any]]:
    return [item for item in items if str(item.get("validation_type") or "").upper() == validation]


def _today_counts(api: ApiClient) -> Counter[str]:
    """How many logs the user submitted today (Mexico City day) per action id, rejected ones included."""
    today = datetime.now(_MX_TZ).date()
    counts: Counter[str] = Counter()
    for log in api.pages(_ROLE, _MINE_PATH):
        created = datetime.fromisoformat(str(log.get("created_at")))
        action_id = str((log.get("action") or {}).get("id") or "")
        if action_id and created.astimezone(_MX_TZ).date() == today:
            counts[action_id] += 1
    return counts


def _remaining(action: dict[str, Any], counts: Counter[str]) -> int:
    return int(action.get("daily_limit") or 0) - counts[str(action["id"])]


def _pick_with_quota(api: ApiClient, validation: str) -> dict[str, Any]:
    """Action of `validation` type the user can still register today; the one with least quota left first.

    Así 006 llena el cupo de la acción de 001 con los menos registros posibles.
    """
    candidates = _of_type(_catalog(api), validation)
    if not candidates:
        raise RuntimeError(f"BLOQUEADO: el catálogo no tiene acciones con validación {validation}")
    counts = _today_counts(api)
    with_quota = [item for item in candidates if _remaining(item, counts) > 0]
    if not with_quota:
        raise RuntimeError(
            f"BLOQUEADO: el usuario {_ROLE} ya agotó hoy el límite diario de todas las acciones {validation} "
            "(la limpieza rechaza los registros pero no libera el cupo). Repite mañana o usa el stack desechable."
        )
    return min(with_quota, key=lambda item: (_remaining(item, counts), int(item.get("daily_limit") or 0)))


def _any_of_type(api: ApiClient, validation: str) -> dict[str, Any]:
    """Any action of `validation` type (for form-only tests that never submit)."""
    items = _of_type(_catalog(api), validation)
    if not items:
        raise RuntimeError(f"BLOQUEADO: el catálogo no tiene acciones con validación {validation}")
    return items[0]


def _points(api: ApiClient) -> tuple[int, int]:
    """(available_points, total_points) of the user."""
    profile = api.json(_ROLE, "GET", _PROFILE_PATH)
    return int(profile.get("available_points") or 0), int(profile.get("total_points") or 0)


def _my_log(api: ApiClient, log_id: str) -> dict[str, Any] | None:
    return next((log for log in api.pages(_ROLE, _MINE_PATH) if str(log.get("id")) == log_id), None)


def _register_via_api(api: ApiClient, action_id: str) -> int:
    """Register a no-evidence action through the API and return the HTTP status."""
    response = api.call(
        _ROLE, "POST", _LOGS_PATH, data={"action_id": action_id, "idempotency_key": str(uuid4())}
    )
    return response.status


# --- privadas: UI -----------------------------------------------------------------------------


def _visible(page: Page, selector: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(page.locator(selector), timeout=timeout)


def _text(page: Page, selector: str) -> str:
    return " ".join((page.locator(selector).first.text_content(timeout=_SHORT_TIMEOUT) or "").split())


def _open_form(page: Page, path: str = _REGISTER_PATH) -> None:
    """Sign in as the actions user, open the form and wait until the catalog fills the selector."""
    login_as(page, _ROLE)
    go_to(page, path)
    wait_for_app_ready(page)
    if not _visible(page, Locs.REGISTER_TITLE, timeout=_LONG_TIMEOUT):
        raise RuntimeError(f"No se ve el título 'Registrar acción' en {path}")
    select = page.locator(Locs.REGISTER_ACTION_SELECT).first

    def loaded() -> bool:
        if _visible(page, Locs.REGISTER_CATALOG_ERROR_SECTION, timeout=100):
            raise RuntimeError("El formulario muestra 'No se pudo cargar el catálogo'")
        return select.is_enabled() and select.locator("option").count() > 1

    if not wait_until(loaded, page, timeout=_LONG_TIMEOUT):
        raise RuntimeError("El selector de acciones no cargó el catálogo")


def _selected_value(page: Page) -> str:
    return page.locator(Locs.REGISTER_ACTION_SELECT).first.input_value(timeout=_SHORT_TIMEOUT)


def _select_action(page: Page, action: dict[str, Any]) -> None:
    """Choose `action` in the selector (by value; by its label as a fallback)."""
    select = page.locator(Locs.REGISTER_ACTION_SELECT).first
    action_id = str(action["id"])
    try:
        select.select_option(value=action_id, timeout=_SHORT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        logger.debug("select_option por valor falló (%s); se intenta por etiqueta", exc)
        select.select_option(label=f"{action['name']} · {action['points']} pts", timeout=_SHORT_TIMEOUT)
    if not wait_until(lambda: _selected_value(page) == action_id, page, timeout=_SHORT_TIMEOUT):
        raise RuntimeError(f"No se pudo elegir la acción {action['name']!r} en el selector")


def _attach(page: Page, name: str, buffer: bytes) -> None:
    page.locator(Locs.REGISTER_EVIDENCE_INPUT).first.set_input_files(
        {"name": name, "mimeType": "image/png", "buffer": buffer}
    )


def _evidence_file_count(page: Page) -> int:
    return int(page.locator(Locs.REGISTER_EVIDENCE_INPUT).first.evaluate("el => el.files.length"))


def _is_log_post(response: Response) -> bool:
    return response.request.method == "POST" and response.url.split("?")[0].endswith(_LOGS_PATH)


def _submit(page: Page) -> Response:
    """Click 'Registrar' and return the POST response of the registration."""
    with page.expect_response(_is_log_post, timeout=_LONG_TIMEOUT) as info:
        click_robust(page, Locs.REGISTER_SUBMIT_BUTTON)
    return info.value


def _guard_submit(page: Page) -> RouteHandle:
    """Intercept every registration POST (answered with 503) so a form-only test never registers for real."""
    return mock_api_error(page, _LOGS_POST_GLOB, status=503, method="POST")


def _click_submit_expecting_validation(page: Page, error_selector: str, expected: str, guard: RouteHandle) -> bool:
    """Click 'Registrar', expect the field error `expected` and confirm no POST left the browser."""
    click_robust(page, Locs.REGISTER_SUBMIT_BUTTON)
    if not wait_until(lambda: _visible(page, error_selector, timeout=100), page, timeout=_SHORT_TIMEOUT):
        logger.error("No apareció el error de validación %r", expected)
        return False
    shown = _text(page, error_selector)
    if shown != expected:
        logger.error("Error de validación %r, se esperaba %r", shown, expected)
        return False
    if guard.requests:
        logger.error("El formulario mandó el registro aunque no era válido: %s", [r.url for r in guard.requests])
        return False
    if _visible(page, Locs.REGISTER_SUCCESS_SECTION, timeout=200):
        logger.error("Apareció 'Acción registrada' con un formulario inválido")
        return False
    return True


# --- tests ------------------------------------------------------------------------------------


def test_01_06_001_checkRegisterWithoutEvidence(page: Page) -> bool:
    api = api_for_page(page)
    action = _pick_with_quota(api, "NONE")
    before_available, before_total = _points(api)
    logger.info("Registro real de %r (%s pts) con saldo %s", action["name"], action["points"], before_available)

    _open_form(page)
    _select_action(page, action)
    if _visible(page, Locs.REGISTER_EVIDENCE_INPUT, timeout=500):
        logger.error("Una acción SIN EVIDENCIA muestra el campo de evidencia")
        return False

    response = _submit(page)
    if response.status != 201:
        logger.error("POST %s → %s: %s", _LOGS_PATH, response.status, response.text()[:300])
        return False
    body = response.json()
    _STATE["none_action"] = action

    if not _visible(page, Locs.REGISTER_SUCCESS_SECTION, timeout=_LONG_TIMEOUT):
        logger.error("No apareció 'Acción registrada'")
        return False
    summary = _text(page, Locs.REGISTER_SUCCESS_SECTION)
    if _SUMMARY_APPROVED not in summary or f"{action['name']} · {action['points']} pts" not in summary:
        logger.error("Resumen inesperado: %r", summary)
        return False

    log = _my_log(api, str(body.get("log_id")))
    if not log or log.get("status") != "APPROVED":
        logger.error("El registro %s no quedó APPROVED en la API: %s", body.get("log_id"), log)
        return False
    points = int(action["points"])
    after_available, after_total = _points(api)
    if (after_available, after_total) != (before_available + points, before_total + points):
        logger.error(
            "Puntos (disponibles, totales) %s → %s; se esperaba +%s",
            (before_available, before_total),
            (after_available, after_total),
            points,
        )
        return False
    return True


def test_01_06_002_checkRegisterWithPhotoPendingAudit(page: Page) -> bool:
    api = api_for_page(page)
    action = _pick_with_quota(api, "PHOTO")
    before = _points(api)
    logger.info("Registro real con foto de %r (queda pendiente de auditoría)", action["name"])

    _open_form(page)
    _select_action(page, action)
    if not _visible(page, Locs.REGISTER_EVIDENCE_INPUT):
        logger.error("Una acción con FOTO no muestra el campo de evidencia")
        return False
    _attach(page, "e2e-evidencia.png", make_png())

    response = _submit(page)
    if response.status != 201:
        logger.error("POST %s con foto → %s: %s", _LOGS_PATH, response.status, response.text()[:300])
        return False
    body = response.json()

    if not _visible(page, Locs.REGISTER_SUCCESS_SECTION, timeout=_LONG_TIMEOUT):
        logger.error("No apareció 'Acción registrada'")
        return False
    summary = _text(page, Locs.REGISTER_SUCCESS_SECTION)
    if _SUMMARY_PENDING not in summary:
        logger.error("Resumen inesperado: %r", summary)
        return False

    log = _my_log(api, str(body.get("log_id")))
    if not log or log.get("status") != "PENDING_AUDIT" or not log.get("has_evidence"):
        logger.error("El registro %s no quedó PENDING_AUDIT con evidencia: %s", body.get("log_id"), log)
        return False
    if _points(api) != before:
        logger.error("Una evidencia pendiente cambió los puntos: %s → %s", before, _points(api))
        return False
    return True


def test_01_06_003_checkActionRequired(page: Page) -> bool:
    guard = _guard_submit(page)
    _open_form(page)
    if _selected_value(page) != "":
        logger.error("El selector no empieza en %r", _PLACEHOLDER_OPTION)
        return False
    if not _click_submit_expecting_validation(page, Locs.REGISTER_ACTION_ERROR, _ERROR_SELECT_ACTION, guard):
        return False
    invalid = page.locator(Locs.REGISTER_ACTION_SELECT).first.get_attribute("aria-invalid")
    if invalid != "true":
        logger.error("El selector no quedó marcado como inválido (aria-invalid=%r)", invalid)
        return False
    return True


def test_01_06_004_checkPhotoRequired(page: Page) -> bool:
    action = _any_of_type(api_for_page(page), "PHOTO")
    guard = _guard_submit(page)
    _open_form(page)
    _select_action(page, action)
    if not _visible(page, Locs.REGISTER_EVIDENCE_INPUT):
        logger.error("Una acción con FOTO no muestra el campo de evidencia")
        return False
    return _click_submit_expecting_validation(page, Locs.REGISTER_EVIDENCE_ERROR, _ERROR_PHOTO_REQUIRED, guard)


def test_01_06_005_checkPhotoOverSizeLimit(page: Page) -> bool:
    action = _any_of_type(api_for_page(page), "PHOTO")
    guard = _guard_submit(page)
    _open_form(page)
    _select_action(page, action)
    big = make_png(min_bytes=_MAX_EVIDENCE_BYTES + 1)
    _attach(page, "e2e-evidencia-grande.png", big)
    if _evidence_file_count(page) != 1:
        logger.error("No se adjuntó la imagen de %s bytes", len(big))
        return False
    return _click_submit_expecting_validation(page, Locs.REGISTER_EVIDENCE_ERROR, _ERROR_TOO_BIG, guard)


def test_01_06_006_checkDailyLimitMessage(page: Page) -> bool:
    action = _STATE.get("none_action")
    if not action:
        raise RuntimeError("TC-06-001 no dejó una acción registrada")
    api = api_for_page(page)
    action_id = str(action["id"])

    missing = _remaining(action, _today_counts(api))
    if missing > _MAX_FILL:
        raise RuntimeError(
            f"BLOQUEADO: llegar al límite de {action['name']!r} necesita {missing} registros más (máximo {_MAX_FILL})"
        )
    logger.info("Se llena por API el cupo de %r: faltan %s registros", action["name"], missing)
    for _ in range(missing):
        status = _register_via_api(api, action_id)
        if status == 429:
            break
        if status != 201:
            raise RuntimeError(f"No se pudo llenar el cupo diario: POST {_LOGS_PATH} → {status}")

    before_points, before_count = _points(api), _today_counts(api)[action_id]
    _open_form(page)
    _select_action(page, action)
    response = _submit(page)
    if response.status != 429:
        logger.error("Con el cupo lleno, POST %s → %s (se esperaba 429)", _LOGS_PATH, response.status)
        return False
    if not _visible(page, Locs.REGISTER_SUBMIT_ERROR_SECTION, timeout=_LONG_TIMEOUT):
        logger.error("No apareció 'No se pudo registrar la acción'")
        return False
    message = _text(page, Locs.REGISTER_SUBMIT_ERROR_SECTION)
    if _ERROR_DAILY_LIMIT not in message:
        logger.error("Mensaje de error %r, se esperaba %r", message, _ERROR_DAILY_LIMIT)
        return False
    if _visible(page, Locs.REGISTER_SUCCESS_SECTION, timeout=200):
        logger.error("Apareció 'Acción registrada' aunque el registro fue rechazado")
        return False
    if _points(api) != before_points or _today_counts(api)[action_id] != before_count:
        logger.error("Un registro rechazado por límite diario cambió los puntos o creó un registro")
        return False
    return True


def test_01_06_007_checkPreselectFromUrl(page: Page) -> bool:
    action = _catalog(api_for_page(page))[0]
    _guard_submit(page)
    for key in ("code", "id"):
        value = str(action.get(key) or "")
        if not value:
            logger.warning("La acción %r no tiene %s; se omite esa variante", action["name"], key)
            continue
        path = f"{_REGISTER_PATH}?action={value}"
        _open_form(page, path)
        if not is_on_path(page, _REGISTER_PATH):
            logger.error("%s redirigió a %s", path, page.url)
            return False
        if not wait_until(lambda: _selected_value(page) == str(action["id"]), page, timeout=_SHORT_TIMEOUT):
            logger.error("Con ?action=<%s> el selector trae %r, se esperaba %r", key, _selected_value(page), action["id"])
            return False
        logger.info("?action=<%s> preselecciona %r", key, action["name"])
    return True


def test_01_06_008_checkClearForm(page: Page) -> bool:
    action = _any_of_type(api_for_page(page), "PHOTO")
    guard = _guard_submit(page)
    _open_form(page)
    _select_action(page, action)
    _attach(page, "e2e-evidencia.png", make_png())
    if _evidence_file_count(page) != 1:
        logger.error("No se adjuntó la imagen antes de limpiar")
        return False

    click_robust(page, Locs.REGISTER_CLEAR_BUTTON)
    if not wait_until(lambda: _selected_value(page) == "", page, timeout=_SHORT_TIMEOUT):
        logger.error("Tras 'Limpiar' el selector trae %r, se esperaba %r", _selected_value(page), _PLACEHOLDER_OPTION)
        return False
    if _visible(page, Locs.REGISTER_EVIDENCE_INPUT, timeout=500):
        logger.error("Tras 'Limpiar' sigue visible el campo de evidencia")
        return False

    # La imagen se quitó de verdad: al volver a elegir la acción, el campo aparece vacío.
    _select_action(page, action)
    if _evidence_file_count(page) != 0:
        logger.error("Tras 'Limpiar' la imagen sigue adjunta")
        return False
    if guard.requests:
        logger.error("'Limpiar' mandó un registro: %s", [r.url for r in guard.requests])
        return False
    return True
