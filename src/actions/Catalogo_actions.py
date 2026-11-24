"""Acciones del módulo 05 · Catálogo de acciones (tests/equipo1/Catalogo/test_Catalogo.py).

Cubre TC-05-001 a TC-05-004 (plan) y 005 a 009 (extras de la suite completa). EE = 01: módulo del equipo 1.

Datos reales vs. mocks:
- 001 lee el catálogo real de ``/api/v1/actions/`` (solo lectura) y no asume cuántas acciones hay.
- 002 a 004 mockean ``/api/v1/actions/`` con ``page.route``: prod no permite forzar una acción sin
  impacto calibrado, un fallo del backend ni una descripción larga sin tocar datos reales.
- TC-05-004: la descripción larga se recorta (line-clamp) y el botón 'Ver más' la expande.
"""

from typing import Any

from playwright.sync_api import Page

from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import is_login_page, locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import mock_api_error, mock_api_json

logger = get_logger(__name__)

_LOAD_TIMEOUT = 15_000
_SHORT_TIMEOUT = 5_000
_ROLE = "student"
_IS_CLIPPED_JS = "el => el.scrollHeight > el.clientHeight + 1"
_CATALOG_ROUTE = "**/api/v1/actions/"
_NO_IMPACT_TEXT = "Impacto ambiental pendiente de calibrar"
_LONG_DESCRIPTION = " ".join(f"Segmento{i} de una descripción muy larga para la acción." for i in range(1, 41))


# --- privadas ----------------------------------------------------------------------------------

def _action(
    code: str,
    name: str,
    *,
    description: str = "Descripción de prueba E2E.",
    co2: float = 1.5,
    water: float = 0,
    plastic: float = 0,
    points: int = 10,
    daily_limit: int = 2,
    validation: str = "NONE",
    active: bool = True,
) -> dict[str, Any]:
    return {
        "id": f"e2e-{code}",
        "code": code,
        "category": {"id": "e2e-cat", "code": "RECYCLING", "name": "Reciclaje", "description": "", "icon": "recycle"},
        "name": name,
        "description": description,
        "points": points,
        "daily_limit": daily_limit,
        "validation_type": validation,
        "co2_kg_factor": co2,
        "water_liters_factor": water,
        "plastic_kg_factor": plastic,
        "is_active": active,
    }


def _open_catalog(page: Page) -> None:
    """Sign in, open /actions and wait for its title."""
    go_to(page, "/actions")
    wait_for_app_ready(page)
    page.locator(Locs.CATALOG_TITLE).first.wait_for(state="visible", timeout=_LOAD_TIMEOUT)


def _wait_for_state(page: Page) -> str:
    """Wait until the catalog stops loading and return "cards", "empty" or "error"."""
    found: list[str] = []

    def _done() -> bool:
        for state, selector in (
            ("cards", Locs.CATALOG_CARD),
            ("empty", Locs.CATALOG_EMPTY_TITLE),
            ("error", Locs.CATALOG_ERROR_TITLE),
        ):
            if locator_has_visible_match(page.locator(selector)):
                found.append(state)
                return True
        return False

    if not wait_until(_done, page, timeout=_LOAD_TIMEOUT, poll_ms=150):
        raise RuntimeError(f"El catálogo no terminó de cargar en {_LOAD_TIMEOUT} ms (URL: {page.url})")
    return found[-1]


# --- públicas: una por test --------------------------------------------------------------------

def test_01_05_001_checkCatalogCards(page: Page) -> bool:
    """TC-05-001: /actions muestra tarjetas con nombre y puntos."""
    login_as(page, _ROLE)
    _open_catalog(page)
    state = _wait_for_state(page)
    if state != "cards":
        raise RuntimeError(f"Se esperaban tarjetas y el catálogo quedó en '{state}'")
    cards = page.locator(Locs.CATALOG_CARD).count()
    titles = [t.strip() for t in page.locator(Locs.CATALOG_CARD_TITLE).all_inner_texts()]
    points = page.locator(Locs.CATALOG_CARD_POINTS).count()
    logger.info("Catálogo: %s tarjetas, %s con puntos", cards, points)
    return cards > 0 and len(titles) == cards and all(titles) and points >= cards


def test_01_05_002_checkNoImpactNotice(page: Page) -> bool:
    """TC-05-002: una acción sin factores de impacto muestra el aviso de calibración."""
    login_as(page, _ROLE)
    body = [_action("E2E_NO_IMPACT", "E2E Sin impacto", co2=0), _action("E2E_IMPACT", "E2E Con impacto")]
    mock_api_json(page, _CATALOG_ROUTE, body)
    _open_catalog(page)
    if _wait_for_state(page) != "cards":
        return False
    notices = page.locator(Locs.CATALOG_NO_IMPACT_NOTICE)
    only_one = notices.count() == 1
    right_card = "E2E Sin impacto" in notices.first.inner_text()
    return only_one and right_card and _NO_IMPACT_TEXT in notices.first.inner_text()


def test_01_05_003_checkErrorAndRetry(page: Page) -> bool:
    """TC-05-003: si el catálogo falla se ve el error; 'Reintentar' recupera las tarjetas."""
    login_as(page, _ROLE)
    handle = mock_api_error(page, _CATALOG_ROUTE, status=500)
    _open_catalog(page)
    if _wait_for_state(page) != "error":
        return False
    handle.restore()
    mock_api_json(page, _CATALOG_ROUTE, [_action("E2E_RETRY", "E2E Tras reintento")])
    click_robust(page, Locs.CATALOG_RETRY_BUTTON)
    if _wait_for_state(page) != "cards":
        return False
    return "E2E Tras reintento" in page.locator(Locs.CATALOG_CARD_TITLE).first.inner_text()


def test_01_05_004_checkLongDescriptionExpanded(page: Page) -> bool:
    """TC-05-004: una descripción larga sale recortada y 'Ver más' la expande completa."""
    login_as(page, _ROLE)
    mock_api_json(page, _CATALOG_ROUTE, [_action("E2E_LONG", "E2E Descripción larga", description=_LONG_DESCRIPTION)])
    _open_catalog(page)
    if _wait_for_state(page) != "cards":
        return False
    card = page.locator(Locs.CATALOG_CARD).first
    paragraph = card.locator(Locs.CATALOG_CARD_DESCRIPTION).first
    toggle = card.locator(Locs.CATALOG_CARD_EXPAND_BUTTON).first
    clipped = bool(paragraph.evaluate(_IS_CLIPPED_JS))
    toggle.click(timeout=_SHORT_TIMEOUT)
    expanded = wait_until(lambda: not paragraph.evaluate(_IS_CLIPPED_JS), page, timeout=_SHORT_TIMEOUT)
    full_text = paragraph.inner_text().strip() == _LONG_DESCRIPTION
    collapse = card.locator(Locs.CATALOG_CARD_COLLAPSE_BUTTON)
    return clipped and expanded and full_text and locator_has_visible_match(collapse)


def test_01_05_005_checkCardDetails(page: Page) -> bool:
    """TC-05-005: la tarjeta muestra puntos, límite diario, etiqueta de evidencia y factores de impacto."""
    login_as(page, _ROLE)
    photo = _action("E2E_PHOTO", "E2E Con foto", points=25, daily_limit=3, validation="PHOTO", co2=2.5, water=40, plastic=0.5)
    plain = _action("E2E_PLAIN", "E2E Sin evidencia", points=5, daily_limit=1)
    mock_api_json(page, _CATALOG_ROUTE, [photo, plain])
    _open_catalog(page)
    if _wait_for_state(page) != "cards":
        return False
    card_photo = page.locator(Locs.catalog_card_with_name("E2E Con foto")).first.inner_text()
    card_plain = page.locator(Locs.catalog_card_with_name("E2E Sin evidencia")).first.inner_text()
    photo_ok = all(t in card_photo for t in ("25 pts", "FOTO", "Límite 3/día", "2.5 kg", "40 L", "0.5 kg", "Plástico"))
    plain_ok = all(t in card_plain for t in ("5 pts", "SIN EVIDENCIA", "Límite 1/día"))
    return photo_ok and plain_ok


def test_01_05_006_checkEmptyCatalog(page: Page) -> bool:
    """TC-05-006: un catálogo vacío muestra 'No hay acciones activas' y ninguna tarjeta."""
    login_as(page, _ROLE)
    mock_api_json(page, _CATALOG_ROUTE, [])
    _open_catalog(page)
    return _wait_for_state(page) == "empty" and page.locator(Locs.CATALOG_CARD).count() == 0


def test_01_05_007_checkInactiveActionsHidden(page: Page) -> bool:
    """TC-05-007: las acciones inactivas no aparecen en el catálogo."""
    login_as(page, _ROLE)
    mock_api_json(
        page,
        _CATALOG_ROUTE,
        [_action("E2E_ON", "E2E Activa"), _action("E2E_OFF", "E2E Inactiva", active=False)],
    )
    _open_catalog(page)
    if _wait_for_state(page) != "cards":
        return False
    titles = [t.strip() for t in page.locator(Locs.CATALOG_CARD_TITLE).all_inner_texts()]
    return titles == ["E2E Activa"]


def test_01_05_008_checkMalformedPayload(page: Page) -> bool:
    """TC-05-008: un payload sin acciones válidas se trata como error (no como catálogo vacío)."""
    login_as(page, _ROLE)
    mock_api_json(page, _CATALOG_ROUTE, [{"id": "", "name": "", "points": 0}])
    _open_catalog(page)
    return _wait_for_state(page) == "error" and page.locator(Locs.CATALOG_CARD).count() == 0


def test_01_05_009_checkRequiresSession(page: Page) -> bool:
    """TC-05-009: sin sesión, /actions no muestra el catálogo (ruta protegida)."""
    go_to(page, "/actions")
    on_login = wait_until(lambda: is_login_page(page), page, timeout=_LOAD_TIMEOUT)
    return on_login and not locator_has_visible_match(page.locator(Locs.CATALOG_TITLE))
