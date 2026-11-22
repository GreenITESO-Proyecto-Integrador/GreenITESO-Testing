"""Acciones del módulo 09 · Muro social /feed (tests/Feed/test_Feed.py).

TC-09-001 crea la publicación compartida de A (SHARED_EVIDENCE) que usan 001 y 009.
Las publicaciones con imagen (003, 004, 006) son de solo `full`: suben archivos reales a prod.
Cada publicación lleva un texto único con el marcador de la corrida (`unique_name`), y la
limpieza de test_data.py la borra al terminar.
"""

import struct
import zlib
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page, Request, Response

from src.configs import environment as env
from src.utils.api import api_for_page
from src.utils.common_actions import accept_next_dialog, go_to, login_as
from src.utils.helpers import locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.test_data import unique_name

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_LONG_TIMEOUT = env.DEFAULT_TIMEOUT
_FEED_PATH = "/feed"
_FEED_API_PATH = "/api/v1/feed/"
_UPLOAD_API_PATH = "/api/v1/uploads/"
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_DEFAULT_AUTHOR = "Usuario GreenITESO"
_CONFIRM_DELETE_TEXT = "¿Estás seguro de que deseas eliminar esta publicación?"
_EDITED_SUFFIX = " editado"
# Imagen estable servida por la propia app (public/ del frontend); el backend acepta cualquier URL.
_STABLE_IMAGE_URL = f"{env.BASE_URL.rstrip('/')}/logo-greeniteso.svg"

# Estado compartido entre los tests del módulo (todos corren en el mismo proceso, en orden).
_STATE: dict[str, Any] = {}


# --- privadas: datos de prueba --------------------------------------------------------------


def _png_bytes() -> bytes:
    """Build a valid 1x1 red PNG in memory (zlib + struct, sin dependencias)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8 bits, RGB
    idat = zlib.compress(b"\x00\xff\x00\x00")  # filtro 0 + un píxel rojo
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _png_file(name: str = "evidencia.png") -> dict[str, Any]:
    return {"name": name, "mimeType": "image/png", "buffer": _png_bytes()}


def _oversized_png_file() -> dict[str, Any]:
    """PNG con encabezado válido y relleno hasta 5 MB + 1 byte (el cliente lo rechaza por tamaño)."""
    head = _png_bytes()
    padding = b"\x00" * (_MAX_IMAGE_BYTES + 1 - len(head))
    return {"name": "evidencia-grande.png", "mimeType": "image/png", "buffer": head + padding}


def _text_file() -> dict[str, Any]:
    return {"name": "nota.txt", "mimeType": "text/plain", "buffer": b"Esto no es una imagen."}


# --- privadas: UI ---------------------------------------------------------------------------


def _within(card: Locator, xpath: str) -> Locator:
    """Scope a page-level XPath (starting with //) to `card`."""
    return card.locator(f"xpath=.{xpath}")


def _post_card(page: Page, content: str) -> Locator:
    """Card of the post whose text is exactly `content` (content is unique per test)."""
    return page.get_by_text(content, exact=True).locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]")


def _wait_card(page: Page, content: str, *, timeout: int = _LONG_TIMEOUT) -> Locator:
    card = _post_card(page, content)
    if not locator_has_visible_match(card, timeout=timeout):
        raise RuntimeError(f"No se ve la publicación con el texto {content!r} en /feed")
    return card


def _visible(page: Page, xpath: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(page.locator(xpath), timeout=timeout)


def _visible_in(card: Locator, xpath: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(_within(card, xpath), timeout=timeout)


def _open_feed(page: Page) -> None:
    """Log in as the student, open /feed and wait for the composer to be ready."""
    login_as(page, "student")
    go_to(page, _FEED_PATH)
    wait_for_app_ready(page)
    if not _visible(page, Locs.FEED_CONTENT_TEXTAREA, timeout=_LONG_TIMEOUT):
        raise RuntimeError("No se ve el formulario de publicación en /feed")


def _open_image_section(page: Page) -> None:
    page.locator(Locs.FEED_ADD_IMAGE_BUTTON).click()
    if not _visible(page, Locs.FEED_UPLOAD_MODE_BUTTON):
        raise RuntimeError("No se abrió la sección de imagen del formulario")


def _fill_content(page: Page, content: str) -> None:
    page.locator(Locs.FEED_CONTENT_TEXTAREA).fill(content)


def _is_feed_post(response: Response) -> bool:
    return response.request.method == "POST" and urlsplit(response.url).path == _FEED_API_PATH


def _is_upload(response: Response) -> bool:
    return response.request.method == "POST" and urlsplit(response.url).path == _UPLOAD_API_PATH


def _submit_post(page: Page) -> dict[str, Any]:
    """Click 'Publicar' and return the body of the created post (201 expected)."""
    with page.expect_response(_is_feed_post) as info:
        page.locator(Locs.FEED_PUBLISH_BUTTON).click()
    response = info.value
    if response.status != 201:
        raise RuntimeError(f"POST /api/v1/feed/ → {response.status}: {response.text()[:300]}")
    return response.json()


def _submit_post_with_upload(page: Page) -> tuple[dict[str, Any], dict[str, Any]]:
    """Click 'Publicar' with a file selected; return (upload body, created post body)."""
    with page.expect_response(_is_upload) as upload_info, page.expect_response(_is_feed_post) as post_info:
        page.locator(Locs.FEED_PUBLISH_BUTTON).click()
    upload, post = upload_info.value, post_info.value
    if upload.status != 200:
        raise RuntimeError(f"POST /api/v1/uploads/ → {upload.status}: {upload.text()[:300]}")
    if post.status != 201:
        raise RuntimeError(f"POST /api/v1/feed/ → {post.status}: {post.text()[:300]}")
    return upload.json(), post.json()


def _wait_form_cleared(page: Page) -> bool:
    return wait_until(
        lambda: page.locator(Locs.FEED_CONTENT_TEXTAREA).input_value() == "", page, timeout=_SHORT_TIMEOUT
    )


def _record_writes(page: Page, *paths: str) -> list[str]:
    """Record the POSTs to `paths`, to prove that nothing reached the server."""
    sent: list[str] = []

    def on_request(request: Request) -> None:
        if request.method == "POST" and urlsplit(request.url).path in paths:
            sent.append(request.url)

    page.on("request", on_request)
    return sent


def _expected_author_name(author: dict[str, Any] | None) -> str:
    """Mirror the author name of FeedPost.tsx: display_name, nickname, full name, then the default."""
    author = author or {}
    full_name = " ".join(part for part in (author.get("first_name"), author.get("last_name")) if part).strip()
    return (
        (author.get("display_name") or "").strip()
        or (author.get("nickname") or "").strip()
        or full_name
        or _DEFAULT_AUTHOR
    )


def _check_image_served(page: Page, url: str) -> bool:
    """The uploaded image must be served (the endpoint redirects to storage when deployed)."""
    response = page.request.get(url)
    content_type = response.headers.get("content-type", "")
    if not response.ok or not content_type.startswith("image/"):
        logger.error("La imagen %s no se sirve: %s %s", url, response.status, content_type)
        return False
    return True


def _image_loaded(img: Locator) -> bool:
    """Tell whether the <img> finished loading with a real image (a broken one has naturalWidth 0)."""
    return bool(img.first.evaluate("el => el.complete && el.naturalWidth > 0"))


def _create_post_via_api(page: Page, role: str, label: str) -> dict[str, Any]:
    """Create a SHARED_EVIDENCE post with the API (setup of tests that need a post that already exists)."""
    content = unique_name(label)
    return api_for_page(page).json(
        role,
        "POST",
        _FEED_API_PATH,
        data={"content": content, "post_type": "SHARED_EVIDENCE"},
        expected=(201,),
    )


# --- tests ----------------------------------------------------------------------------------


def test_00_09_001_checkViewPosts(page: Page) -> bool:
    shared = _create_post_via_api(page, "admin", "Feed compartida de A")
    _STATE["shared_post"] = {"id": shared["id"], "content": shared["content"], "author": shared.get("author")}
    logger.info("Publicación de A creada para el módulo: id=%s", shared["id"])

    _open_feed(page)
    if not _visible(page, Locs.FEED_TITLE, timeout=_LONG_TIMEOUT):
        logger.error("No se ve el título 'Muro Social'")
        return False
    if not _visible(page, Locs.FEED_POST_CONTENT, timeout=_LONG_TIMEOUT):
        logger.error("El muro no muestra ninguna publicación")
        return False

    card = _wait_card(page, shared["content"])
    author_text = (_within(card, Locs.FEED_POST_AUTHOR).first.text_content() or "").strip()
    expected = _expected_author_name(shared.get("author"))
    if author_text != expected:
        logger.error("Autor en la tarjeta %r, se esperaba %r", author_text, expected)
        return False
    return True


def test_00_09_002_checkTextOnlyPost(page: Page) -> bool:
    _open_feed(page)
    publish = page.locator(Locs.FEED_PUBLISH_BUTTON)
    if not _visible(page, Locs.FEED_PUBLISH_BUTTON):
        logger.error("No se ve el botón 'Publicar'")
        return False
    if publish.is_enabled():
        logger.error("'Publicar' está habilitado con el texto vacío")
        return False

    page.locator(Locs.FEED_CONTENT_TEXTAREA).fill("   ")
    if publish.is_enabled():
        logger.error("'Publicar' está habilitado con solo espacios")
        return False

    content = unique_name("Feed texto 002")
    _fill_content(page, content)
    if not wait_until(publish.is_enabled, page, timeout=_SHORT_TIMEOUT):
        logger.error("'Publicar' no se habilita con texto")
        return False

    created = _submit_post(page)
    if created.get("content") != content:
        logger.error("La API regresó otro contenido: %r", created.get("content"))
        return False
    _STATE["student_post"] = {"id": created["id"], "content": content}

    if not _wait_form_cleared(page):
        logger.error("El formulario no se limpió después de publicar")
        return False
    first_post = page.locator(Locs.FEED_POST_CONTENT).first
    if not wait_until(lambda: (first_post.text_content() or "").strip() == content, page, timeout=_SHORT_TIMEOUT):
        logger.error("La publicación nueva no quedó primero en el muro")
        return False
    return True


def test_00_09_003_checkImageFromFile(page: Page) -> bool:
    _open_feed(page)
    _open_image_section(page)
    page.locator(Locs.FEED_UPLOAD_MODE_BUTTON).click()
    page.locator(Locs.FEED_FILE_INPUT).set_input_files(files=[_png_file()])
    if not _visible(page, Locs.FEED_IMAGE_PREVIEW):
        logger.error("No aparece la previsualización de la imagen")
        return False

    content = unique_name("Feed imagen archivo 003")
    _fill_content(page, content)
    upload, created = _submit_post_with_upload(page)
    image_url = created.get("image_url") or ""
    if not image_url or image_url != upload.get("url"):
        logger.error("image_url %r no coincide con la subida %r", image_url, upload.get("url"))
        return False
    if _UPLOAD_API_PATH not in urlsplit(image_url).path:
        logger.error("La URL de la imagen no está bajo %s: %s", _UPLOAD_API_PATH, image_url)
        return False
    if not _check_image_served(page, image_url):
        return False

    card = _wait_card(page, content)
    img = _within(card, Locs.FEED_POST_IMAGE)
    if not locator_has_visible_match(img, timeout=_LONG_TIMEOUT):
        logger.error("La publicación no muestra la imagen 'Evidencia'")
        return False
    if not wait_until(lambda: _image_loaded(img), page, timeout=_LONG_TIMEOUT):
        logger.error("La imagen subida no se pudo cargar en el navegador: %s", image_url)
        return False
    if img.get_attribute("src") != image_url:
        logger.error("src de la imagen %r, se esperaba %r", img.get_attribute("src"), image_url)
        return False

    stored = api_for_page(page).json("student", "GET", f"{_FEED_API_PATH}{created['id']}/")
    if stored.get("image_url") != image_url:
        logger.error("La API no guardó image_url: %r", stored.get("image_url"))
        return False
    return True


def test_00_09_004_checkImageByUrl(page: Page) -> bool:
    _open_feed(page)
    _open_image_section(page)
    page.locator(Locs.FEED_URL_MODE_BUTTON).click()
    if not _visible(page, Locs.FEED_URL_INPUT):
        logger.error("No aparece el campo de URL de la imagen")
        return False
    page.locator(Locs.FEED_URL_INPUT).fill(_STABLE_IMAGE_URL)

    content = unique_name("Feed imagen URL 004")
    _fill_content(page, content)
    created = _submit_post(page)
    if created.get("image_url") != _STABLE_IMAGE_URL:
        logger.error("image_url %r, se esperaba %r", created.get("image_url"), _STABLE_IMAGE_URL)
        return False

    card = _wait_card(page, content)
    img = _within(card, Locs.FEED_POST_IMAGE)
    if not locator_has_visible_match(img, timeout=_LONG_TIMEOUT):
        logger.error("La publicación no muestra la imagen por URL")
        return False
    if not wait_until(lambda: _image_loaded(img), page, timeout=_LONG_TIMEOUT):
        logger.error("La imagen por URL no se pudo cargar en el navegador: %s", _STABLE_IMAGE_URL)
        return False
    return img.get_attribute("src") == _STABLE_IMAGE_URL


def test_00_09_005_checkInvalidFileRejected(page: Page) -> bool:
    _open_feed(page)
    sent = _record_writes(page, _FEED_API_PATH, _UPLOAD_API_PATH)
    _open_image_section(page)

    page.locator(Locs.FEED_FILE_INPUT).set_input_files(files=[_text_file()])
    if not _visible(page, Locs.FEED_FORMAT_ERROR):
        logger.error("Un .txt no muestra 'Formato no soportado'")
        return False

    page.locator(Locs.FEED_FILE_INPUT).set_input_files(files=[_oversized_png_file()])
    if not _visible(page, Locs.FEED_SIZE_ERROR):
        logger.error("Un archivo de más de 5 MB no muestra el error de tamaño")
        return False

    if page.locator(Locs.FEED_IMAGE_PREVIEW).count():
        logger.error("Se muestra previsualización para un archivo rechazado")
        return False
    if sent:
        logger.error("Un archivo rechazado llegó al servidor: %s", sent)
        return False
    return True


def test_00_09_006_checkRemoveImageBeforePosting(page: Page) -> bool:
    _open_feed(page)
    sent = _record_writes(page, _UPLOAD_API_PATH)  # el POST del propio post sí se espera
    _open_image_section(page)
    page.locator(Locs.FEED_FILE_INPUT).set_input_files(files=[_png_file("quitar.png")])
    if not _visible(page, Locs.FEED_IMAGE_PREVIEW):
        logger.error("No aparece la previsualización antes de quitarla")
        return False

    page.locator(Locs.FEED_REMOVE_IMAGE_BUTTON).click()
    if not wait_until(lambda: page.locator(Locs.FEED_IMAGE_PREVIEW).count() == 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("La previsualización sigue visible después de quitar la imagen")
        return False
    if not _visible(page, Locs.FEED_DROPZONE_HINT):
        logger.error("No vuelve la zona para subir archivo")
        return False

    content = unique_name("Feed sin imagen 006")
    _fill_content(page, content)
    created = _submit_post(page)
    if created.get("image_url"):
        logger.error("La API guardó una imagen que se había quitado: %r", created.get("image_url"))
        return False

    card = _wait_card(page, content)
    if _within(card, Locs.FEED_POST_IMAGE).count():
        logger.error("La publicación muestra una imagen que se había quitado")
        return False
    if sent:
        logger.error("Se subió una imagen que se había quitado: %s", sent)
        return False
    return True


def test_00_09_007_checkEditOwnPost(page: Page) -> bool:
    own = _STATE.get("student_post")
    if not own:
        raise RuntimeError("TC-09-002 no dejó una publicación propia de S para editar")

    _open_feed(page)
    card = _wait_card(page, own["content"])
    _within(card, Locs.FEED_EDIT_POST_BUTTON).click()
    if not _visible(page, Locs.FEED_EDIT_TEXTAREA):
        logger.error("No se abrió el editor de la publicación")
        return False

    new_content = own["content"] + _EDITED_SUFFIX
    page.locator(Locs.FEED_EDIT_TEXTAREA).fill(new_content)
    path = f"{_FEED_API_PATH}{own['id']}/"
    with page.expect_response(lambda r: r.request.method == "PATCH" and urlsplit(r.url).path == path) as info:
        page.locator(Locs.FEED_SAVE_EDIT_BUTTON).click()
    if info.value.status != 200:
        logger.error("PATCH %s → %s", path, info.value.status)
        return False

    updated_card = _wait_card(page, new_content)
    if not _visible_in(updated_card, Locs.FEED_EDITED_LABEL):
        logger.error("La publicación no muestra '(Editado)'")
        return False
    stored = api_for_page(page).json("student", "GET", path)
    if stored.get("content") != new_content:
        logger.error("La API tiene otro contenido: %r", stored.get("content"))
        return False
    own["content"] = new_content
    return True


def test_00_09_008_checkDeleteOwnPost(page: Page) -> bool:
    post = _create_post_via_api(page, "student", "Feed borrar 008")
    _open_feed(page)
    card = _wait_card(page, post["content"])

    messages = accept_next_dialog(page)
    _within(card, Locs.FEED_DELETE_POST_BUTTON).click()
    gone = wait_until(lambda: _post_card(page, post["content"]).count() == 0, page, timeout=_LONG_TIMEOUT)
    if not gone:
        logger.error("La publicación sigue en el muro después de eliminarla")
        return False
    if not messages or messages[0] != _CONFIRM_DELETE_TEXT:
        logger.error("Mensaje de confirmación inesperado: %s", messages)
        return False

    response = api_for_page(page).call("student", "GET", f"{_FEED_API_PATH}{post['id']}/")
    if response.status != 404:
        logger.error("GET de la publicación borrada → %s, se esperaba 404", response.status)
        return False
    return True


def test_00_09_009_checkNoEditOnOthersPosts(page: Page) -> bool:
    shared = _STATE.get("shared_post")
    if not shared:
        raise RuntimeError("TC-09-001 no dejó la publicación de A")

    api = api_for_page(page)
    if str(api.user_id("student")) == str((shared.get("author") or {}).get("id")):
        raise RuntimeError("La cuenta de S es el autor de la publicación de A: la prueba no aplica")

    _open_feed(page)
    card = _wait_card(page, shared["content"])
    for label, xpath in (("Editar", Locs.FEED_EDIT_POST_BUTTON), ("Eliminar", Locs.FEED_DELETE_POST_BUTTON)):
        if _within(card, xpath).count():
            logger.error("Aparece el botón '%s' en una publicación de otro autor", label)
            return False
    return True
