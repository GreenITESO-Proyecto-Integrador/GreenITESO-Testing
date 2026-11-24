"""Acciones del módulo 08 · Tienda /store (tests/equipo1/Tienda/test_Tienda.py).

EE = 01: módulo del equipo 1, probado por el equipo 3 (docs/peer-testing-friday.md, caso T3-07).

Usuario: ``store`` (TEST_STORE_EMAIL), propio del módulo. Un canje cambia el saldo y el inventario de
la cuenta y no se puede deshacer, así que no se usa ``student``, que comparten otros módulos en paralelo.

Datos reales vs. mocks:
- 001, 002, 007 leen el catálogo y el saldo reales (solo lectura).
- 003 canjea de verdad el artículo más barato que el usuario aún no tiene. **Es irreversible**: cada
  artículo se canjea una sola vez por cuenta. Si ya no queda ninguno al alcance del saldo, falla con
  "BLOQUEADO" (en el stack desechable, ``ci/stack/up.sh`` le da saldo inicial al usuario ``store``).
- 008 y 009 llaman a la API real: canje repetido y canje sin saldo deben dar 400 sin cambiar nada.
- 004 mockea el perfil (saldo 0) y el inventario: el aviso "Puntos insuficientes" es del cliente.
- 005 usa los datos reales si el saldo alcanza para algún artículo; si no, mockea el perfil. En los dos
  casos el POST de canje queda interceptado, así que cancelar nunca puede canjear de verdad.
- 006 y 010 mockean la lista de canjeables (error 500 + "Reintentar" y catálogo vacío).
"""

import re
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Locator, Page, Response

from src.configs import environment as env
from src.utils.api import api_for_page
from src.utils.common_actions import click_filter_chip, go_to, login_as
from src.utils.helpers import is_on_path, locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import RouteHandle, mock_api_error, mock_api_json

logger = get_logger(__name__)

_ROLE = "store"
_SHORT_TIMEOUT = 5_000
_LONG_TIMEOUT = env.DEFAULT_TIMEOUT

_STORE_PATH = "/store"
_SHOP_PATH = "/shop"
_EXCHANGEABLES_PATH = "/api/v1/exchangeables/"
_INVENTORY_PATH = "/api/v1/exchangeables/my-inventory/"
_PROFILE_PATH = "/api/v1/profile/me/"
_EXCHANGEABLES_GLOB = "**/api/v1/exchangeables/"
_INVENTORY_GLOB = "**/api/v1/exchangeables/my-inventory/"
_PROFILE_GLOB = "**/api/v1/profile/me/"
_REDEEM_GLOB = "**/api/v1/exchangeables/*/redeem/"

# Etiquetas de ExchangeableCard.tsx (THEME se muestra como "Fondo") y chips de CategoryFilterTabs.tsx.
_CATEGORY_LABEL = {"FRAME": "Marco", "BACKGROUND": "Fondo", "THEME": "Fondo"}
_DEFAULT_CATEGORY_LABEL = "Otro"
_FILTER_CHIPS: tuple[tuple[str, frozenset[str] | None], ...] = (
    ("Marcos", frozenset({"FRAME"})),
    ("Fondos", frozenset({"BACKGROUND", "THEME"})),
    ("Otros", None),  # todo lo que no es marco ni fondo
    ("Todos", frozenset()),  # sin filtro
)
_KNOWN_CATEGORIES = frozenset({"FRAME", "BACKGROUND", "THEME"})

_TOAST_SUCCESS = "¡Canje exitoso!"
_TOAST_INSUFFICIENT = "Puntos insuficientes"
_ERROR_ALREADY_OWNED = "Ya posees este cosmético en tu perfil."
_ERROR_INSUFFICIENT = "Puntos disponibles insuficientes para realizar este canje."
_LABEL_AVAILABLE = "Tus puntos disponibles:"
_LABEL_COST = "Costo del canjeable:"
_LABEL_REMAINING = "Puntos restantes tras compra:"

# Estado compartido entre los tests del módulo (corren en orden en el mismo proceso).
_STATE: dict[str, Any] = {}


# --- privadas: datos de la API ----------------------------------------------------------------


def _normalize(text: str | None) -> str:
    return " ".join((text or "").split())


def _catalog(page: Page) -> list[dict[str, Any]]:
    """Active exchangeables as the backend lists them (the UI hides inactive ones too)."""
    items = list(api_for_page(page).pages(_ROLE, _EXCHANGEABLES_PATH))
    return [item for item in items if item.get("is_active", True)]


def _profile(page: Page) -> dict[str, Any]:
    return api_for_page(page).json(_ROLE, "GET", _PROFILE_PATH)


def _inventory(page: Page) -> list[str]:
    body = api_for_page(page).json(_ROLE, "GET", _INVENTORY_PATH)
    return [str(key) for key in body.get("unlocked_cosmetics") or []]


def _points(profile: dict[str, Any]) -> int:
    return int(profile.get("available_points") or 0)


def _cost(item: dict[str, Any]) -> int:
    return int(item.get("points_cost") or 0)


def _matches_chip(item: dict[str, Any], categories: frozenset[str] | None) -> bool:
    category = str(item.get("category") or "").upper()
    if categories is None:
        return category not in _KNOWN_CATEGORIES
    return not categories or category in categories


def _redeem_via_api(page: Page, item_id: str) -> Any:
    return api_for_page(page).call(_ROLE, "POST", f"{_EXCHANGEABLES_PATH}{item_id}/redeem/")


# --- privadas: UI -----------------------------------------------------------------------------


def _visible(page: Page, xpath: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    return locator_has_visible_match(page.locator(xpath), timeout=timeout)


def _is_catalog_get(response: Response) -> bool:
    return response.request.method == "GET" and urlsplit(response.url).path == _EXCHANGEABLES_PATH


def _open_store(page: Page, path: str = _STORE_PATH) -> Response:
    """Sign in as the store user, open `path` and return the catalog response the page consumed."""
    login_as(page, _ROLE)
    with page.expect_response(_is_catalog_get, timeout=_LONG_TIMEOUT) as info:
        go_to(page, path)
    wait_for_app_ready(page)
    if not _visible(page, Locs.STORE_TITLE, timeout=_LONG_TIMEOUT):
        raise RuntimeError(f"No se ve el título 'Tienda de canjeables' en {path}")
    _wait_loaded(page)
    return info.value


def _wait_loaded(page: Page) -> None:
    """Wait until the skeleton is gone and the catalog, the empty state or the error is shown."""

    def settled() -> bool:
        if page.locator(Locs.STORE_LOADING).count():
            return False
        return any(
            page.locator(xpath).count()
            for xpath in (Locs.STORE_CARD, Locs.STORE_EMPTY_TITLE, Locs.STORE_ERROR_TITLE, Locs.STORE_NO_MATCH_TEXT)
        )

    if not wait_until(settled, page, timeout=_LONG_TIMEOUT):
        raise RuntimeError("La tienda no terminó de cargar (sigue el esqueleto o no hay contenido)")


def _read_int(locator: Locator) -> int:
    """Parse the integer shown by `locator` ("1,234 pts", "- 20 pts"); the sign is ignored."""
    text = locator.first.text_content() or ""
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise RuntimeError(f"No hay un número en el texto {text!r}")
    return int(digits)


def _shown_balance(page: Page) -> int:
    return _read_int(page.locator(Locs.STORE_BALANCE))


def _wait_balance(page: Page, expected: int) -> bool:
    return wait_until(lambda: _shown_balance(page) == expected, page, timeout=_SHORT_TIMEOUT)


def _card_names(page: Page) -> list[str]:
    return [_normalize(text) for text in page.locator(Locs.STORE_CARD_NAMES).all_text_contents()]


def _card(page: Page, item: dict[str, Any]) -> Locator:
    card = page.locator(Locs.store_card_with_name(str(item.get("name") or "")))
    if not locator_has_visible_match(card, timeout=_SHORT_TIMEOUT):
        raise RuntimeError(f"No se ve la tarjeta del artículo {item.get('name')!r}")
    return card.first


def _guard_redeem(page: Page) -> RouteHandle:
    """Intercept every redeem POST (answered with 503) so a UI-only test can never redeem for real."""
    return mock_api_error(page, _REDEEM_GLOB, status=503, method="POST")


def _mock_profile_points(page: Page, points: int) -> None:
    """Serve the real profile of the store user with `points` available (states the account can't reach)."""
    body = {**_profile(page), "available_points": points}
    mock_api_json(page, _PROFILE_GLOB, body)


def _toast(page: Page, title: str) -> tuple[bool, str]:
    """Wait for the store toast whose title contains `title`; return (shown, description)."""
    title_locator = page.locator(Locs.STORE_TOAST_TITLE)
    shown = wait_until(lambda: title in (title_locator.first.text_content() or ""), page, timeout=_SHORT_TIMEOUT)
    if not shown:
        return False, ""
    return True, _normalize(page.locator(Locs.STORE_TOAST_DESCRIPTION).first.text_content())


def _pick_affordable(items: list[dict[str, Any]], owned: list[str], points: int) -> dict[str, Any] | None:
    """Cheapest item the user does not own yet and can pay for."""
    candidates = [item for item in items if item.get("key") not in owned and 0 < _cost(item) <= points]
    return min(candidates, key=_cost, default=None)


def _check_dialog(page: Page, item: dict[str, Any], points: int) -> bool:
    """The confirm dialog shows the item and the breakdown available − cost = remaining."""
    if not _visible(page, Locs.STORE_CONFIRM_DIALOG):
        logger.error("No se abrió el diálogo 'Confirmar Canje de Artículo'")
        return False
    name = _normalize(page.locator(Locs.STORE_DIALOG_ITEM_NAME).first.text_content())
    if name != _normalize(item.get("name")):
        logger.error("El diálogo muestra el artículo %r, se esperaba %r", name, item.get("name"))
        return False
    shown = {
        label: _read_int(page.locator(Locs.store_dialog_value(label)))
        for label in (_LABEL_AVAILABLE, _LABEL_COST, _LABEL_REMAINING)
    }
    expected = {_LABEL_AVAILABLE: points, _LABEL_COST: _cost(item), _LABEL_REMAINING: points - _cost(item)}
    if shown != expected:
        logger.error("Desglose del diálogo %s, se esperaba %s", shown, expected)
        return False
    return True


# --- tests ------------------------------------------------------------------------------------


def test_01_08_001_checkBalanceAndCatalog(page: Page) -> bool:
    response = _open_store(page)
    if response.status != 200:
        logger.error("GET %s → %s", _EXCHANGEABLES_PATH, response.status)
        return False
    items, owned, profile = _catalog(page), _inventory(page), _profile(page)
    _STATE["catalog"] = items

    if _shown_balance(page) != _points(profile):
        logger.error("Saldo en pantalla %s, la API dice %s", _shown_balance(page), _points(profile))
        return False

    if not items:
        logger.warning("El catálogo real está vacío: solo se valida el estado vacío")
        return _visible(page, Locs.STORE_EMPTY_TITLE)

    expected_names = sorted(_normalize(item.get("name")) for item in items)
    if sorted(_card_names(page)) != expected_names:
        logger.error("Tarjetas %s, la API tiene %s", sorted(_card_names(page)), expected_names)
        return False

    for item in items:
        card = _card(page, item)
        category = _normalize(card.locator(Locs.STORE_CARD_CATEGORY).first.text_content())
        expected_category = _CATEGORY_LABEL.get(str(item.get("category")).upper(), _DEFAULT_CATEGORY_LABEL)
        if category != expected_category:
            logger.error("%r muestra la categoría %r, se esperaba %r", item["name"], category, expected_category)
            return False
        if item.get("key") in owned:
            redeemed = card.locator(Locs.STORE_CARD_REDEEMED_BUTTON)
            if (
                not redeemed.count()
                or redeemed.first.is_enabled()
                or not card.locator(Locs.STORE_CARD_OWNED_BADGE).count()
            ):
                logger.error("%r ya es del usuario y no aparece como 'Obtenido'/'Canjeado' deshabilitado", item["name"])
                return False
        else:
            button = card.locator(Locs.STORE_CARD_REDEEM_BUTTON)
            if not button.count() or _read_int(button) != _cost(item):
                logger.error("%r no muestra 'Canjear • %s pts'", item["name"], _cost(item))
                return False
    logger.info("Tienda: %s artículos, %s obtenidos, saldo %s", len(items), len(owned), _points(profile))
    return True


def test_01_08_002_checkCategoryFilter(page: Page) -> bool:
    _open_store(page)
    items = _STATE.get("catalog") or _catalog(page)
    if not items:
        raise RuntimeError("El catálogo real está vacío: no hay qué filtrar")

    for chip, categories in _FILTER_CHIPS:
        click_filter_chip(page, Locs.STORE_FILTER_GROUP_LABEL, chip)
        pressed = page.locator(Locs.STORE_FILTER_PRESSED_CHIP)
        if pressed.count() != 1 or _normalize(pressed.first.text_content()) != chip:
            logger.error("Con %r activo, los chips presionados son %s", chip, pressed.all_text_contents())
            return False

        expected = sorted(_normalize(item.get("name")) for item in items if _matches_chip(item, categories))
        if not expected:
            if not _visible(page, Locs.STORE_NO_MATCH_TEXT) or page.locator(Locs.STORE_CARD).count():
                logger.error("Con %r no hay artículos y no se ve 'Ningún artículo coincide…'", chip)
                return False
            continue
        if not wait_until(lambda e=expected: sorted(_card_names(page)) == e, page, timeout=_SHORT_TIMEOUT):
            logger.error("Con %r se ven %s, se esperaba %s", chip, sorted(_card_names(page)), expected)
            return False
        logger.debug("Filtro %r: %s artículos", chip, len(expected))
    return True


def test_01_08_003_checkRedeemWithEnoughPoints(page: Page) -> bool:
    items, owned, before = _catalog(page), _inventory(page), _points(_profile(page))
    item = _pick_affordable(items, owned, before)
    if item is None:
        raise RuntimeError(
            f"BLOQUEADO: el usuario store tiene {before} pts y no queda ningún artículo sin canjear que pueda "
            "pagar. Los canjes no se deshacen: dale saldo a la cuenta o usa el stack desechable (ci/stack)."
        )
    logger.info("Canje real de %r (%s pts) con saldo %s", item["name"], _cost(item), before)

    _open_store(page)
    _card(page, item).locator(Locs.STORE_CARD_REDEEM_BUTTON).click()
    if not _check_dialog(page, item, before):
        return False

    path = f"{_EXCHANGEABLES_PATH}{item['id']}/redeem/"
    with page.expect_response(lambda r: r.request.method == "POST" and urlsplit(r.url).path == path) as info:
        page.locator(Locs.STORE_CONFIRM_BUTTON).click()
    if info.value.status != 201:
        logger.error("POST %s → %s: %s", path, info.value.status, info.value.text()[:300])
        return False
    after = before - _cost(item)
    _STATE["redeemed"] = {**item, "balance_after": after}

    shown, _ = _toast(page, _TOAST_SUCCESS)
    if not shown:
        logger.error("No aparece el aviso '%s'", _TOAST_SUCCESS)
        return False
    if not wait_until(lambda: page.locator(Locs.STORE_CONFIRM_DIALOG).count() == 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("El diálogo de confirmación sigue abierto después del canje")
        return False
    if not _wait_balance(page, after):
        logger.error("El saldo en pantalla es %s, se esperaba %s", _shown_balance(page), after)
        return False
    if not locator_has_visible_match(
        _card(page, item).locator(Locs.STORE_CARD_REDEEMED_BUTTON), timeout=_SHORT_TIMEOUT
    ):
        logger.error("La tarjeta de %r no cambió a 'Canjeado'", item["name"])
        return False

    # Persistencia: después de recargar, la UI y la API siguen mostrando el canje.
    page.reload(wait_until="domcontentloaded")
    _wait_loaded(page)
    if not _wait_balance(page, after):
        logger.error("Tras recargar, el saldo es %s, se esperaba %s", _shown_balance(page), after)
        return False
    if not locator_has_visible_match(
        _card(page, item).locator(Locs.STORE_CARD_REDEEMED_BUTTON), timeout=_SHORT_TIMEOUT
    ):
        logger.error("Tras recargar, %r ya no aparece como 'Canjeado'", item["name"])
        return False
    if _points(_profile(page)) != after or item["key"] not in _inventory(page):
        logger.error("La API no guardó el canje (saldo %s, inventario %s)", _points(_profile(page)), _inventory(page))
        return False
    return True


def test_01_08_004_checkInsufficientPointsBlocked(page: Page) -> bool:
    items = _STATE.get("catalog") or _catalog(page)
    item = next((item for item in items if _cost(item) > 0), None)
    if item is None:
        raise RuntimeError("No hay artículos con costo en el catálogo real")

    guard = _guard_redeem(page)
    _mock_profile_points(page, 0)
    mock_api_json(page, _INVENTORY_GLOB, {"unlocked_cosmetics": []})
    _open_store(page)
    if _shown_balance(page) != 0:
        logger.error("El saldo simulado debía ser 0 y se ve %s", _shown_balance(page))
        return False

    _card(page, item).locator(Locs.STORE_CARD_REDEEM_BUTTON).click()
    shown, description = _toast(page, _TOAST_INSUFFICIENT)
    if not shown:
        logger.error("No aparece el aviso '%s'", _TOAST_INSUFFICIENT)
        return False
    if f"Necesitas {_cost(item)} puntos" not in description or "solo tienes 0 puntos" not in description:
        logger.error("Descripción del aviso inesperada: %r", description)
        return False
    if _visible(page, Locs.STORE_CONFIRM_DIALOG, timeout=1_000):
        logger.error("Se abrió el diálogo de confirmación sin puntos suficientes")
        return False
    if guard.requests:
        logger.error("Se mandó un canje sin puntos suficientes: %s", [r.url for r in guard.requests])
        return False
    return True


def test_01_08_005_checkCancelRedeem(page: Page) -> bool:
    items, owned, real_points = _STATE.get("catalog") or _catalog(page), _inventory(page), _points(_profile(page))
    guard = _guard_redeem(page)  # primero: cancelar nunca debe llegar al backend
    item = _pick_affordable(items, owned, real_points)
    points = real_points
    if item is None:
        item = next((item for item in items if _cost(item) > 0), None)
        if item is None:
            raise RuntimeError("No hay artículos con costo en el catálogo real")
        points = max(_cost(i) for i in items) + 100
        logger.info("El saldo real (%s) no alcanza: se simula un perfil con %s pts", real_points, points)
        _mock_profile_points(page, points)
        mock_api_json(page, _INVENTORY_GLOB, {"unlocked_cosmetics": []})

    _open_store(page)
    card = _card(page, item)
    card.locator(Locs.STORE_CARD_REDEEM_BUTTON).click()
    if not _check_dialog(page, item, points):
        return False

    page.locator(Locs.STORE_CANCEL_BUTTON).click()
    if not wait_until(lambda: page.locator(Locs.STORE_CONFIRM_DIALOG).count() == 0, page, timeout=_SHORT_TIMEOUT):
        logger.error("El diálogo sigue abierto después de 'Cancelar'")
        return False
    if guard.requests:
        logger.error("'Cancelar' mandó un canje: %s", [r.url for r in guard.requests])
        return False
    if _shown_balance(page) != points:
        logger.error("El saldo cambió tras cancelar: %s, se esperaba %s", _shown_balance(page), points)
        return False
    if not card.locator(Locs.STORE_CARD_REDEEM_BUTTON).count():
        logger.error("Tras cancelar, %r ya no muestra 'Canjear'", item["name"])
        return False
    if _points(_profile(page)) != real_points:
        logger.error("El saldo real cambió tras cancelar: %s → %s", real_points, _points(_profile(page)))
        return False
    return True


def test_01_08_006_checkCatalogErrorAndRetry(page: Page) -> bool:
    failing = mock_api_error(page, _EXCHANGEABLES_GLOB, status=500)
    login_as(page, _ROLE)
    go_to(page, _STORE_PATH)
    wait_for_app_ready(page)
    if not _visible(page, Locs.STORE_ERROR_TITLE, timeout=_LONG_TIMEOUT):
        logger.error("Con el catálogo en 500 no se ve 'No se pudieron cargar los canjeables'")
        return False
    if not _visible(page, Locs.STORE_RETRY_BUTTON):
        logger.error("No se ve el botón 'Reintentar'")
        return False

    failing.restore()
    with page.expect_response(_is_catalog_get, timeout=_LONG_TIMEOUT) as info:
        page.locator(Locs.STORE_RETRY_BUTTON).click()
    if info.value.status != 200:
        logger.error("El reintento del catálogo respondió %s", info.value.status)
        return False
    _wait_loaded(page)
    if page.locator(Locs.STORE_ERROR_TITLE).count():
        logger.error("El error sigue visible después de 'Reintentar'")
        return False
    body = info.value.json()
    listed = body.get("results", []) if isinstance(body, dict) else body
    if listed and not _visible(page, Locs.STORE_CARD):
        logger.error("Tras reintentar no se ven las tarjetas del catálogo")
        return False
    return True


def test_01_08_007_checkShopRoute(page: Page) -> bool:
    response = _open_store(page, _SHOP_PATH)
    if not is_on_path(page, _SHOP_PATH):
        logger.error("/shop redirigió a %s", page.url)
        return False
    if response.status != 200:
        logger.error("GET %s desde /shop → %s", _EXCHANGEABLES_PATH, response.status)
        return False
    if not _visible(page, Locs.STORE_BALANCE):
        logger.error("/shop no muestra el saldo de puntos")
        return False
    return True


def test_01_08_008_checkDuplicateRedeemRejected(page: Page) -> bool:
    item = _STATE.get("redeemed")
    if not item:
        raise RuntimeError("TC-08-003 no dejó un artículo canjeado")
    before, owned = _points(_profile(page)), _inventory(page)

    _open_store(page)
    card = _card(page, item)
    redeemed = card.locator(Locs.STORE_CARD_REDEEMED_BUTTON)
    if not redeemed.count() or redeemed.first.is_enabled() or card.locator(Locs.STORE_CARD_REDEEM_BUTTON).count():
        logger.error("%r no aparece como 'Canjeado' deshabilitado", item["name"])
        return False

    response = _redeem_via_api(page, item["id"])
    if response.status != 400:
        logger.error("Canje repetido → %s, se esperaba 400: %s", response.status, response.text()[:300])
        return False
    if (response.json() or {}).get("error") != _ERROR_ALREADY_OWNED:
        logger.error("Error del canje repetido inesperado: %s", response.text()[:300])
        return False
    after = _inventory(page)
    if _points(_profile(page)) != before or after.count(item["key"]) != 1 or len(after) != len(owned):
        logger.error("El canje repetido cambió el saldo o el inventario (%s → %s)", owned, after)
        return False
    return True


def test_01_08_009_checkApiRejectsInsufficientPoints(page: Page) -> bool:
    items, owned, before = _catalog(page), _inventory(page), _points(_profile(page))
    item = next((i for i in sorted(items, key=_cost) if i.get("key") not in owned and _cost(i) > before), None)
    if item is None:
        raise RuntimeError(
            f"BLOQUEADO: con {before} pts no queda ningún artículo sin canjear que cueste más que el saldo"
        )

    response = _redeem_via_api(page, item["id"])
    if response.status != 400:
        logger.error(
            "Canje de %r (%s pts) con %s pts → %s, se esperaba 400", item["name"], _cost(item), before, response.status
        )
        return False
    if (response.json() or {}).get("error") != _ERROR_INSUFFICIENT:
        logger.error("Error del canje sin saldo inesperado: %s", response.text()[:300])
        return False
    if _points(_profile(page)) != before or item["key"] in _inventory(page):
        logger.error("Un canje rechazado cambió el saldo o el inventario")
        return False
    return True


def test_01_08_010_checkEmptyCatalog(page: Page) -> bool:
    mock_api_json(page, _EXCHANGEABLES_GLOB, [])
    _open_store(page)
    if not _visible(page, Locs.STORE_EMPTY_TITLE):
        logger.error("Con el catálogo vacío no se ve 'No hay canjeables disponibles'")
        return False
    if page.locator(Locs.STORE_FILTER_GROUP).count() or page.locator(Locs.STORE_CARD).count():
        logger.error("Con el catálogo vacío se muestran filtros o tarjetas")
        return False
    return True
