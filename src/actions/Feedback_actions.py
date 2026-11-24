"""Acciones del módulo 16 · Feedback (tests/Feedback/test_Feedback.py).

Cubre el buzón de comentarios del estudiante (/feedback) y su API (/api/v1/feedback/): formulario y
validaciones, envío con y sin captura, historial, acceso a la captura, filtros y respuesta del admin.

Reglas de seguridad (estas pruebas corren contra prod por default):

- **Lo creado no se puede borrar.** Ni el usuario ni el admin tienen DELETE de feedback (el admin solo cambia
  `status` y `admin_notes`), así que ``cleanup_run`` no puede limpiarlo. Por eso todo envío lleva el marcador
  de la corrida (``unique_name``), y los tests que crean datos van solo en `full`.
- **Límite de 10 envíos por hora y usuario** (``feedback_submit`` en settings/base.py; cuenta todos los POST,
  también los que terminan en 400). Por corrida: `student` hace 2 POST (los dos envíos por la UI) y `leader`
  hace 5 (los rechazos de la API, que no crean nada). Nadie más envía feedback, así que el límite no se
  comparte con otros módulos. Si el backend responde 429, la prueba falla con el tiempo de espera.
- El admin solo modifica (PATCH) los dos envíos marcados que creó este módulo.
- Los mocks se usan solo para estados que las cuentas reales no alcanzan (error del servidor + "Reintentar",
  historial vacío y fallo al enviar); ninguno llega al backend, así que no gastan límite.

Los tests corren en orden dentro del mismo proceso; el estado compartido vive en `_STATE`.
EE = 00 es provisional hasta que se haga el reparto de equipos.
"""

import re
import struct
import time
import uuid
import zlib
from typing import Any

from playwright.sync_api import APIResponse, Page

from src.configs import environment as env
from src.utils.api import api_for_page
from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import is_login_page, is_on_path, locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import mock_api_error, mock_api_json
from src.utils.test_data import unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_FEEDBACK_PATH = "/api/v1/feedback/"
_MINE_PATH = "/api/v1/feedback/mine/"
_MINE_URL = re.compile(r"/api/v1/feedback/mine/")
_CREATE_URL = re.compile(r"/api/v1/feedback/$")
_MAX_SUBJECT = 120
_MAX_MESSAGE = 1000
_MIN_MESSAGE = 10
_MAX_FILE_BYTES = 5 * 1024 * 1024
_VALID_MESSAGE = "Mensaje de prueba E2E con más de diez caracteres."
_THANKS_TEXT = "¡Gracias por tus comentarios!"
_ADMIN_REPLY_TITLE = "Respuesta del equipo GreenITESO:"
_BAD_TYPE_ERROR = "Formato no soportado. Usa imágenes JPG, PNG o WebP."
_TOO_BIG_ERROR = "El archivo excede el tamaño máximo permitido de 5 MB."
_EMPTY_PAGE = {"count": 0, "next": None, "previous": None, "results": []}

# Estado compartido entre los tests del módulo: asuntos/mensajes marcados y los ids de lo que se creó.
_STATE: dict[str, Any] = {}


# --- privadas: datos y API ------------------------------------------------------------------

def _make_png(size: int = 8) -> bytes:
    """Build a valid solid-green PNG in memory (JPG/PNG/WEBP up to 5 MB are accepted as a screenshot)."""

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


def _file(name: str, mime: str, content: bytes) -> dict[str, Any]:
    return {"name": name, "mimeType": mime, "buffer": content}


def _expect_status(response: APIResponse, expected: int, label: str) -> bool:
    if response.status == expected:
        logger.info("%s → %s", label, response.status)
        return True
    logger.error("%s → %s (se esperaba %s): %s", label, response.status, expected, response.text()[:200])
    return False


def _post(page: Page, role: str, *, data: dict | None = None, multipart: dict | None = None) -> APIResponse:
    """POST a feedback as `role`; a 429 means the 10-per-hour limit of that user was reached."""
    response = api_for_page(page).call(role, "POST", _FEEDBACK_PATH, data=data, multipart=multipart)
    if response.status == 429:
        wait = response.headers.get("retry-after", "?")
        raise RuntimeError(
            f"POST {_FEEDBACK_PATH} como {role} → 429: límite de 10 envíos por hora y usuario; reintenta en {wait} s"
        )
    return response


def _find_mine(page: Page, role: str, subject: str) -> dict | None:
    """Return the feedback of `role` whose subject is `subject` (newest first), or None."""
    for item in api_for_page(page).pages(role, _MINE_PATH):
        if item.get("subject") == subject:
            return item
    return None


def _rejects_with(page: Page, label: str, field: str, *, data: dict) -> bool:
    """POST an invalid payload as `leader` and expect 400 with an error on `field`."""
    response = _post(page, "leader", data=data)
    if not _expect_status(response, 400, label):
        return False
    if field not in response.json():
        logger.error("%s: el 400 no menciona el campo %r: %s", label, field, response.text()[:200])
        return False
    return True


def _ids_in_list(page: Page, params: dict) -> set[str]:
    """Ids of the first 100 submissions the admin sees with `params` (newest first)."""
    response = api_for_page(page).call("admin", "GET", _FEEDBACK_PATH, params={**params, "page_size": 100})
    if response.status != 200:
        raise RuntimeError(f"GET {_FEEDBACK_PATH} {params} → {response.status}: {response.text()[:200]}")
    return {item["id"] for item in response.json()["results"]}


def _state_ready(*keys: str) -> bool:
    missing = [key for key in keys if key not in _STATE]
    if missing:
        logger.error("Falta estado de tests anteriores: %s", missing)
    return not missing


# --- privadas: UI ---------------------------------------------------------------------------

def _open_feedback(page: Page, role: str = "student") -> None:
    """Sign in as `role`, open /feedback and wait for the form."""
    login_as(page, role)
    go_to(page, "/feedback")
    wait_for_app_ready(page)
    page.locator(Locs.FEEDBACK_TITLE).wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)


def _visible(page: Page, selector: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(page.locator(selector), timeout=timeout)


def _fill_form(page: Page, subject: str, message: str) -> None:
    page.locator(Locs.FEEDBACK_SUBJECT_INPUT).fill(subject)
    page.locator(Locs.FEEDBACK_MESSAGE_INPUT).fill(message)


def _submit_enabled(page: Page) -> bool:
    return page.locator(Locs.FEEDBACK_SUBMIT).is_enabled()


def _select_category(page: Page, label: str) -> None:
    click_robust(page, Locs.feedback_category_with_label(label))


def _select_rating(page: Page, value: int) -> None:
    click_robust(page, Locs.feedback_rating_with_value(value))


def _is_checked(page: Page, selector: str) -> bool:
    return page.locator(selector).first.get_attribute("aria-checked") == "true"


def _attach(page: Page, name: str, mime: str, content: bytes) -> None:
    page.locator(Locs.FEEDBACK_FILE_INPUT).set_input_files(_file(name, mime, content))


def _submit(page: Page) -> None:
    """Click "Enviar comentario" once the form lets it."""
    if not wait_until(lambda: _submit_enabled(page), page, timeout=_SHORT_TIMEOUT):
        raise RuntimeError("El botón 'Enviar comentario' sigue deshabilitado con un formulario válido")
    click_robust(page, Locs.FEEDBACK_SUBMIT)


def _thanks_visible(page: Page) -> bool:
    return _visible(page, Locs.alert_with_text(_THANKS_TEXT), timeout=env.DEFAULT_TIMEOUT)


def _card(page: Page, subject: str):  # noqa: ANN202 - Locator
    return page.locator(Locs.feedback_card_with_subject(subject))


def _card_has_text(page: Page, subject: str, text: str) -> bool:
    card = _card(page, subject)
    return locator_has_visible_match(card.get_by_text(text, exact=True), timeout=_SHORT_TIMEOUT)


def _error_text_visible(page: Page, text: str) -> bool:
    return locator_has_visible_match(page.get_by_text(text, exact=True), timeout=_SHORT_TIMEOUT)


def _history_count_matches(page: Page, count: int) -> bool:
    heading = page.locator(Locs.FEEDBACK_HISTORY_TITLE)
    return wait_until(lambda: f"({count})" in heading.inner_text(), page, timeout=_SHORT_TIMEOUT)


def _y_of(page: Page, subject: str) -> float:
    box = _card(page, subject).first.bounding_box()
    if box is None:
        raise RuntimeError(f"La tarjeta {subject!r} no tiene posición en la página")
    return box["y"]


# --- 000 · setup ----------------------------------------------------------------------------

def test_00_16_000_checkSetUp(page: Page) -> bool:
    """Check the test sessions exist and prepare the marked subjects used by the module."""
    api = api_for_page(page)
    missing = [role for role in ("student", "admin", "leader") if role not in api.tokens]
    if missing:
        logger.error("Faltan sesiones de prueba: %s", missing)
        return False
    response = api.call("student", "GET", _MINE_PATH)
    if not _expect_status(response, 200, "GET feedback/mine (student)"):
        return False
    _STATE.clear()
    _STATE["subject_a"] = unique_name("Feedback error", max_length=_MAX_SUBJECT)
    _STATE["message_a"] = unique_name("Mensaje del error reportado por E2E", max_length=_MAX_MESSAGE)
    _STATE["subject_b"] = unique_name("Feedback idea", max_length=_MAX_SUBJECT)
    _STATE["message_b"] = unique_name("Mensaje de la idea con captura de E2E", max_length=_MAX_MESSAGE)
    logger.info("Setup de Feedback listo: %s / %s", _STATE["subject_a"], _STATE["subject_b"])
    return True


# --- 001-006 · formulario (sin enviar nada) ---------------------------------------------------

def test_00_16_001_checkOpenFeedbackPage(page: Page) -> bool:
    """Check /feedback shows the form (5 categories, 5 ratings), the history and a disabled submit."""
    _open_feedback(page)
    checks = {
        "título": _visible(page, Locs.FEEDBACK_TITLE),
        "historial": _visible(page, Locs.FEEDBACK_HISTORY_TITLE),
        "5 categorías": page.locator(Locs.FEEDBACK_CATEGORY_OPTIONS).count() == 5,
        "5 calificaciones": page.locator(Locs.FEEDBACK_RATING_OPTIONS).count() == 5,
        "categoría por defecto (Idea o mejora)": _is_checked(page, Locs.feedback_category_with_label("Idea o mejora")),
        "sin calificación": not any(_is_checked(page, Locs.feedback_rating_with_value(n)) for n in range(1, 6)),
        "envío deshabilitado": not _submit_enabled(page),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


def test_00_16_002_checkSubmitDisabledUntilValid(page: Page) -> bool:
    """Check the submit button follows the subject (1-120) and message (10-1000) limits."""
    _open_feedback(page)
    results: dict[str, bool] = {}

    _fill_form(page, "Asunto de prueba", "corto")
    results["mensaje corto deshabilitado"] = not _submit_enabled(page)
    results["aviso de caracteres que faltan"] = locator_has_visible_match(
        page.get_by_text(re.compile(r"Escribe al menos 10 caracteres \(5\s+más\)")), timeout=_SHORT_TIMEOUT
    )

    _fill_form(page, "Asunto de prueba", _VALID_MESSAGE)
    results["válido habilitado"] = _submit_enabled(page)

    _fill_form(page, "   ", _VALID_MESSAGE)
    results["asunto en blanco deshabilitado"] = not _submit_enabled(page)

    _fill_form(page, "Asunto de prueba", "x" * _MAX_MESSAGE)
    results["mensaje de 1000 habilitado"] = _submit_enabled(page)

    _fill_form(page, "Asunto de prueba", "x" * (_MAX_MESSAGE + 1))
    results["mensaje de 1001 deshabilitado"] = not _submit_enabled(page)
    results["contador en 1001 / 1000"] = locator_has_visible_match(
        page.get_by_text(re.compile(r"1001 / 1000")), timeout=_SHORT_TIMEOUT
    )

    results["asunto con maxlength 120"] = page.locator(Locs.FEEDBACK_SUBJECT_INPUT).get_attribute("maxlength") == str(
        _MAX_SUBJECT
    )
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


def test_00_16_003_checkClearForm(page: Page) -> bool:
    """Check "Limpiar formulario" empties subject, message and rating, and disables itself."""
    _open_feedback(page)
    if page.locator(Locs.FEEDBACK_CLEAR).is_enabled():
        logger.error("'Limpiar formulario' debería estar deshabilitado con el formulario vacío")
        return False
    _fill_form(page, "Asunto para limpiar", _VALID_MESSAGE)
    _select_rating(page, 3)
    click_robust(page, Locs.FEEDBACK_CLEAR)
    checks = {
        "asunto vacío": page.locator(Locs.FEEDBACK_SUBJECT_INPUT).input_value() == "",
        "mensaje vacío": page.locator(Locs.FEEDBACK_MESSAGE_INPUT).input_value() == "",
        "sin calificación": not _visible(page, Locs.FEEDBACK_RATING_CLEAR, timeout=1_000),
        "botón deshabilitado": wait_until(lambda: not page.locator(Locs.FEEDBACK_CLEAR).is_enabled(), page),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


def test_00_16_004_checkRatingToggle(page: Page) -> bool:
    """Check a rating can be picked, switched, unpicked by clicking it again and cleared with its link."""
    _open_feedback(page)
    option_4 = Locs.feedback_rating_with_value(4)
    _select_rating(page, 4)
    results = {
        "4 seleccionada": _is_checked(page, option_4),
        "etiqueta '4 - Muy buena'": locator_has_visible_match(
            page.get_by_text("4 - Muy buena", exact=True), timeout=_SHORT_TIMEOUT
        ),
    }
    _select_rating(page, 2)
    results["cambia a 2"] = _is_checked(page, Locs.feedback_rating_with_value(2)) and not _is_checked(page, option_4)
    _select_rating(page, 2)
    results["segundo clic la quita"] = not _is_checked(page, Locs.feedback_rating_with_value(2))
    _select_rating(page, 5)
    click_robust(page, Locs.FEEDBACK_RATING_CLEAR)
    results["'Quitar calificación'"] = not any(
        _is_checked(page, Locs.feedback_rating_with_value(n)) for n in range(1, 6)
    )
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


def test_00_16_005_checkInvalidFileTypeRejected(page: Page) -> bool:
    """Check a non-image attachment shows the format error and keeps the submit disabled."""
    _open_feedback(page)
    _attach(page, "notas.txt", "text/plain", b"esto no es una imagen")
    shown = _error_text_visible(page, _BAD_TYPE_ERROR)
    _fill_form(page, "Asunto de prueba", _VALID_MESSAGE)
    return all(
        (
            shown,
            not _visible(page, Locs.FEEDBACK_FILE_PREVIEW, timeout=1_000),
            not _submit_enabled(page),
        )
    )


def test_00_16_006_checkOversizedFileRejected(page: Page) -> bool:
    """Check an image over 5 MB shows the size error and keeps the submit disabled."""
    _open_feedback(page)
    oversized = _make_png() + b"\x00" * _MAX_FILE_BYTES
    _attach(page, "enorme.png", "image/png", oversized)
    shown = _error_text_visible(page, _TOO_BIG_ERROR)
    _fill_form(page, "Asunto de prueba", _VALID_MESSAGE)
    return all(
        (
            shown,
            not _visible(page, Locs.FEEDBACK_FILE_PREVIEW, timeout=1_000),
            not _submit_enabled(page),
        )
    )


# --- 007-009 · envío por la UI y historial (crean datos) -------------------------------------

def test_00_16_007_checkSubmitFeedback(page: Page) -> bool:
    """Submit a bug report with a rating from the UI; it resets the form and shows up in the history."""
    if not _state_ready("subject_a", "message_a"):
        return False
    subject, message = _STATE["subject_a"], _STATE["message_a"]
    _open_feedback(page)
    _select_category(page, "Error técnico")
    _select_rating(page, 4)
    _fill_form(page, subject, message)
    _submit(page)

    if not _thanks_visible(page):
        logger.error("No apareció el mensaje de agradecimiento (¿límite de envíos o error del servidor?)")
        return False
    card = _card(page, subject)
    checks = {
        "formulario vacío": page.locator(Locs.FEEDBACK_SUBJECT_INPUT).input_value() == ""
        and page.locator(Locs.FEEDBACK_MESSAGE_INPUT).input_value() == "",
        "tarjeta en el historial": locator_has_visible_match(card.first, timeout=_SHORT_TIMEOUT),
        "categoría": _card_has_text(page, subject, "Error técnico"),
        "calificación": _card_has_text(page, subject, "★ 4/5"),
        "estado Recibido": _card_has_text(page, subject, "Recibido"),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron en la UI: %s", failed)
        return False

    stored = _find_mine(page, "student", subject)
    if stored is None:
        logger.error("El envío no aparece en GET feedback/mine/")
        return False
    _STATE["id_a"] = stored["id"]
    api_ok = (
        stored["category"] == "BUG"
        and stored["rating"] == 4
        and stored["status"] == "OPEN"
        and stored["message"] == message.strip()
        and stored["has_screenshot"] is False
    )
    if not api_ok:
        logger.error("El envío guardado no coincide con lo capturado: %s", stored)
        return False
    total = api_for_page(page).json("student", "GET", _MINE_PATH)["count"]
    return _history_count_matches(page, total)


def test_00_16_008_checkSubmitFeedbackWithScreenshot(page: Page) -> bool:
    """Submit an idea with a screenshot (no rating): preview, remove, re-attach, send and open it from the history."""
    if not _state_ready("subject_b", "message_b"):
        return False
    subject, message = _STATE["subject_b"], _STATE["message_b"]
    png = _make_png()
    _open_feedback(page)
    _select_category(page, "Idea o mejora")
    _fill_form(page, subject, message)

    _attach(page, "e2e-captura.png", "image/png", png)
    preview = {
        "vista previa": _visible(page, Locs.FEEDBACK_FILE_PREVIEW),
        "nombre del archivo": locator_has_visible_match(
            page.get_by_text("e2e-captura.png", exact=True), timeout=_SHORT_TIMEOUT
        ),
    }
    click_robust(page, Locs.FEEDBACK_REMOVE_FILE)
    preview["'Quitar' elimina la vista previa"] = not _visible(page, Locs.FEEDBACK_FILE_PREVIEW, timeout=1_000)
    _attach(page, "e2e-captura.png", "image/png", png)
    preview["se puede adjuntar de nuevo"] = _visible(page, Locs.FEEDBACK_FILE_PREVIEW)
    failed = [name for name, ok in preview.items() if not ok]
    if failed:
        logger.error("Fallaron antes de enviar: %s", failed)
        return False

    _submit(page)
    if not _thanks_visible(page):
        logger.error("No apareció el mensaje de agradecimiento (¿límite de envíos o error del servidor?)")
        return False
    if _visible(page, Locs.FEEDBACK_FILE_PREVIEW, timeout=1_000):
        logger.error("La vista previa debía limpiarse después de enviar")
        return False

    card = _card(page, subject)
    button = card.get_by_role("button", name=re.compile("Ver captura adjunta", re.IGNORECASE))
    if not locator_has_visible_match(button, timeout=env.DEFAULT_TIMEOUT):
        logger.error("La tarjeta no ofrece 'Ver captura adjunta'")
        return False
    button.first.click()
    image = page.get_by_role("img", name=f"Captura adjunta de {subject}")
    if not locator_has_visible_match(image, timeout=env.DEFAULT_TIMEOUT):
        logger.error("El diálogo no mostró la captura")
        return False
    if not wait_until(lambda: image.first.evaluate("el => el.naturalWidth") > 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("La captura del diálogo no cargó")
        return False
    page.keyboard.press("Escape")
    if not wait_until(lambda: not image.first.is_visible(), page, timeout=_SHORT_TIMEOUT):
        logger.error("El diálogo de la captura no se cerró con Escape")
        return False

    stored = _find_mine(page, "student", subject)
    if stored is None:
        logger.error("El envío no aparece en GET feedback/mine/")
        return False
    _STATE["id_b"] = stored["id"]
    if not (stored["category"] == "IDEA" and stored["rating"] is None and stored["has_screenshot"] is True):
        logger.error("El envío guardado no coincide con lo capturado: %s", stored)
        return False
    response = api_for_page(page).call("student", "GET", f"{_FEEDBACK_PATH}{stored['id']}/screenshot/")
    return _expect_status(response, 200, "GET screenshot (autor)") and response.headers.get(
        "content-type", ""
    ).startswith("image/")


def test_00_16_009_checkHistoryPersistsAfterReload(page: Page) -> bool:
    """Check both submissions survive a reload, newest first, with their rating and status."""
    if not _state_ready("subject_a", "subject_b"):
        return False
    subject_a, subject_b = _STATE["subject_a"], _STATE["subject_b"]
    _open_feedback(page)
    if not (
        locator_has_visible_match(_card(page, subject_a).first, timeout=env.DEFAULT_TIMEOUT)
        and locator_has_visible_match(_card(page, subject_b).first, timeout=env.DEFAULT_TIMEOUT)
    ):
        logger.error("El historial no muestra los dos envíos después de recargar")
        return False
    checks = {
        "calificación del primero": _card_has_text(page, subject_a, "★ 4/5"),
        "estado del primero": _card_has_text(page, subject_a, "Recibido"),
        "captura del segundo": locator_has_visible_match(
            _card(page, subject_b).get_by_role("button", name=re.compile("Ver captura adjunta", re.IGNORECASE)),
            timeout=_SHORT_TIMEOUT,
        ),
        "más reciente primero": _y_of(page, subject_b) < _y_of(page, subject_a),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


# --- 010-014 · API (permisos y validaciones) --------------------------------------------------

def test_00_16_010_checkApiRejectsInvalidPayload(page: Page) -> bool:
    """Check the API answers 400 for a short message, a blank subject, an unknown category and a rating of 6."""
    message = unique_name("Mensaje inválido de E2E", max_length=_MAX_MESSAGE)
    subject = unique_name("Asunto inválido", max_length=_MAX_SUBJECT)
    # Se manda con `leader` (cuenta sin otros envíos) para no gastar el límite de `student`.
    results = (
        _rejects_with(page, "mensaje corto", "message", data={"subject": subject, "message": "corto"}),
        _rejects_with(page, "asunto en blanco", "subject", data={"subject": "   ", "message": message}),
        _rejects_with(
            page, "categoría desconocida", "category", data={"subject": subject, "message": message, "category": "NOPE"}
        ),
        _rejects_with(page, "calificación 6", "rating", data={"subject": subject, "message": message, "rating": 6}),
    )
    return all(results)


def test_00_16_011_checkApiRejectsInvalidScreenshot(page: Page) -> bool:
    """Check the API answers 400 when the screenshot is not a JPG, PNG or WEBP image."""
    response = _post(
        page,
        "leader",
        multipart={
            "subject": unique_name("Captura inválida", max_length=_MAX_SUBJECT),
            "message": unique_name("Mensaje con captura inválida de E2E", max_length=_MAX_MESSAGE),
            "screenshot": _file("notas.txt", "text/plain", b"esto no es una imagen"),
        },
    )
    return _expect_status(response, 400, "POST con captura de texto") and "screenshot" in response.json()


def test_00_16_012_checkFeedbackIsPrivateToAuthor(page: Page) -> bool:
    """Check "mine" lists the author's submissions with their email and hides them from other users."""
    if not _state_ready("id_a", "id_b"):
        return False
    api = api_for_page(page)
    own = list(api.pages("student", _MINE_PATH))
    own_ids = {item["id"] for item in own}
    others = {item["id"] for item in api.pages("leader", _MINE_PATH)}
    student_email = env.TEST_USERS["student"].lower()
    checks = {
        "el autor ve sus dos envíos": {_STATE["id_a"], _STATE["id_b"]} <= own_ids,
        "los envíos son de su email": all(item.get("user_email", "").lower() == student_email for item in own),
        "otro usuario no los ve": not ({_STATE["id_a"], _STATE["id_b"]} & others),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed


def test_00_16_013_checkScreenshotAccessControl(page: Page) -> bool:
    """Check only the author and an admin read a screenshot; others get 403, missing ones 404, no token 401."""
    if not _state_ready("id_a", "id_b"):
        return False
    api = api_for_page(page)
    with_shot = f"{_FEEDBACK_PATH}{_STATE['id_b']}/screenshot/"
    without_shot = f"{_FEEDBACK_PATH}{_STATE['id_a']}/screenshot/"
    unknown = f"{_FEEDBACK_PATH}{uuid.uuid4()}/screenshot/"

    author = api.call("student", "GET", with_shot)
    admin = api.call("admin", "GET", with_shot)
    anonymous = page.request.get(env.API_BASE_URL.rstrip("/") + with_shot)
    checks = (
        _expect_status(author, 200, "captura: autor"),
        author.headers.get("content-type", "").startswith("image/"),
        "no-store" in author.headers.get("cache-control", ""),
        _expect_status(admin, 200, "captura: admin"),
        _expect_status(api.call("leader", "GET", with_shot), 403, "captura: otro usuario"),
        _expect_status(anonymous, 401, "captura: sin token"),
        _expect_status(api.call("student", "GET", without_shot), 404, "captura: envío sin captura"),
        _expect_status(api.call("student", "GET", unknown), 404, "captura: id inexistente"),
    )
    return all(checks)


def test_00_16_014_checkAdminListAndFilters(page: Page) -> bool:
    """Check the admin lists the submissions, filters by category and status, and gets 400/404 on bad input."""
    if not _state_ready("id_a", "id_b"):
        return False
    api = api_for_page(page)
    id_a, id_b = _STATE["id_a"], _STATE["id_b"]
    detail = api.call("admin", "GET", f"{_FEEDBACK_PATH}{id_a}/")
    checks = (
        {id_a, id_b} <= _ids_in_list(page, {}),
        id_a in _ids_in_list(page, {"category": "BUG"}) and id_b not in _ids_in_list(page, {"category": "BUG"}),
        id_b in _ids_in_list(page, {"category": "IDEA"}) and id_a not in _ids_in_list(page, {"category": "IDEA"}),
        {id_a, id_b} <= _ids_in_list(page, {"status": "OPEN"}),
        not ({id_a, id_b} & _ids_in_list(page, {"status": "RESOLVED"})),
        _expect_status(api.call("admin", "GET", _FEEDBACK_PATH, params={"category": "NOPE"}), 400, "categoría inválida"),
        _expect_status(api.call("admin", "GET", _FEEDBACK_PATH, params={"status": "NOPE"}), 400, "estado inválido"),
        _expect_status(detail, 200, "detalle como admin")
        and detail.json().get("user_email", "").lower() == env.TEST_USERS["student"].lower(),
        _expect_status(api.call("admin", "GET", f"{_FEEDBACK_PATH}{uuid.uuid4()}/"), 404, "detalle inexistente"),
        _expect_status(api.call("student", "GET", f"{_FEEDBACK_PATH}{id_a}/"), 403, "detalle como estudiante"),
    )
    if not all(checks):
        logger.error("Resultados de cada chequeo: %s", checks)
    return all(checks)


# --- 015 · respuesta del admin ----------------------------------------------------------------

def test_00_16_015_checkAdminUpdateReachesStudent(page: Page) -> bool:
    """Check the admin changes status and notes of a submission and the student sees both in the history."""
    if not _state_ready("id_a", "subject_a"):
        return False
    api = api_for_page(page)
    path = f"{_FEEDBACK_PATH}{_STATE['id_a']}/"
    note = unique_name("Gracias por avisar, ya lo revisamos", max_length=500)

    api_checks = (
        _expect_status(
            api.call("admin", "PATCH", path, data={"status": "NOPE"}), 400, "PATCH con estado inválido"
        ),
        _expect_status(
            api.call("student", "PATCH", path, data={"status": "RESOLVED"}), 403, "PATCH como estudiante"
        ),
    )
    if not all(api_checks):
        return False
    response = api.call("admin", "PATCH", path, data={"status": "RESOLVED", "admin_notes": note})
    if not _expect_status(response, 200, "PATCH como admin"):
        return False
    body = response.json()
    if body.get("status") != "RESOLVED" or body.get("admin_notes") != note:
        logger.error("El PATCH no devolvió lo guardado: %s", body)
        return False
    if _STATE["id_a"] not in _ids_in_list(page, {"status": "RESOLVED"}):
        logger.error("El filtro status=RESOLVED no incluye el envío actualizado")
        return False

    _open_feedback(page)
    subject = _STATE["subject_a"]
    card = _card(page, subject)
    checks = {
        "tarjeta": locator_has_visible_match(card.first, timeout=env.DEFAULT_TIMEOUT),
        "estado Resuelto": _card_has_text(page, subject, "Resuelto"),
        "título de la respuesta": _card_has_text(page, subject, _ADMIN_REPLY_TITLE),
        "texto de la respuesta": locator_has_visible_match(card.get_by_text(note, exact=True), timeout=_SHORT_TIMEOUT),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron en la UI del estudiante: %s", failed)
    return not failed


# --- 016 · sin sesión -------------------------------------------------------------------------

def test_00_16_016_checkAnonymousIsRedirectedToLogin(page: Page) -> bool:
    """Check a signed-out visitor is sent to login and the API answers 401 without a token."""
    go_to(page, "/feedback")
    redirected = wait_until(
        lambda: is_on_path(page, "/login") or is_login_page(page), page, timeout=env.DEFAULT_TIMEOUT
    )
    base = env.API_BASE_URL.rstrip("/")
    checks = (
        redirected,
        _expect_status(page.request.get(base + _MINE_PATH), 401, "GET mine sin token"),
        _expect_status(
            page.request.post(
                base + _FEEDBACK_PATH,
                data={"subject": "Sin sesión", "message": "Este envío no debe crearse nunca."},
            ),
            401,
            "POST sin token",
        ),
    )
    return all(checks)


# --- 017-019 · estados que las cuentas reales no alcanzan (mocks) -----------------------------

def test_00_16_017_checkHistoryErrorAndRetry(page: Page) -> bool:
    """Check a failing history shows the error with "Reintentar" and recovers once the server answers."""
    login_as(page, "student")
    failing = mock_api_error(page, _MINE_URL, status=500)
    go_to(page, "/feedback")
    wait_for_app_ready(page)
    page.locator(Locs.FEEDBACK_TITLE).wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)

    retry = page.get_by_role("button", name="Reintentar")
    error_alert = page.get_by_role("alert").filter(has=retry)
    if not (
        locator_has_visible_match(error_alert.first, timeout=env.DEFAULT_TIMEOUT)
        and locator_has_visible_match(retry.first, timeout=_SHORT_TIMEOUT)
    ):
        logger.error("No apareció el error del historial con 'Reintentar'")
        return False

    failing.restore()
    retry.first.click()
    deadline = time.monotonic() + env.DEFAULT_TIMEOUT / 1000
    while time.monotonic() < deadline:
        if not retry.first.is_visible():
            return True
        page.wait_for_timeout(150)
    logger.error("'Reintentar' sigue visible después de que el servidor respondió")
    return False


def test_00_16_018_checkHistoryEmptyState(page: Page) -> bool:
    """Check a user without submissions sees the empty state and a zero counter."""
    login_as(page, "student")
    mock_api_json(page, _MINE_URL, _EMPTY_PAGE)
    go_to(page, "/feedback")
    wait_for_app_ready(page)
    page.locator(Locs.FEEDBACK_TITLE).wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)
    return _visible(page, Locs.FEEDBACK_HISTORY_EMPTY, timeout=env.DEFAULT_TIMEOUT) and _history_count_matches(page, 0)


def test_00_16_019_checkSubmitErrorKeepsForm(page: Page) -> bool:
    """Check a failed submit shows an error banner and keeps what the user typed (the POST never reaches the backend)."""
    login_as(page, "student")
    failing = mock_api_error(page, _CREATE_URL, status=500, method="POST")
    go_to(page, "/feedback")
    wait_for_app_ready(page)
    page.locator(Locs.FEEDBACK_TITLE).wait_for(state="visible", timeout=env.DEFAULT_TIMEOUT)

    subject = unique_name("Envío que falla", max_length=_MAX_SUBJECT)
    _fill_form(page, subject, _VALID_MESSAGE)
    _submit(page)
    banner_shown = locator_has_visible_match(page.get_by_role("alert").first, timeout=env.DEFAULT_TIMEOUT)
    checks = {
        "se envió una petición": wait_until(lambda: bool(failing.requests), page, timeout=_SHORT_TIMEOUT),
        "banner de error": banner_shown,
        "sin agradecimiento": not _visible(page, Locs.alert_with_text(_THANKS_TEXT), timeout=500),
        "conserva el asunto": page.locator(Locs.FEEDBACK_SUBJECT_INPUT).input_value() == subject,
        "conserva el mensaje": page.locator(Locs.FEEDBACK_MESSAGE_INPUT).input_value() == _VALID_MESSAGE,
        "puede reintentar": wait_until(lambda: _submit_enabled(page), page, timeout=_SHORT_TIMEOUT),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.error("Fallaron: %s", failed)
    return not failed
