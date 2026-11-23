"""Acciones del módulo 12 · Leaderboard (tests/Leaderboard/test_Leaderboard.py).

Cubre TC-12-001 a TC-12-006. EE = 01: módulo del equipo 1, probado por el equipo 3 (docs/peer-testing-friday.md).

Datos reales vs. mocks:
- 001 a 004 leen el ranking real (solo lectura) y no asumen cuántas filas hay.
- 005 a 008 usan ``page.route`` para simular la respuesta de ``/api/v1/rankings/``. Son pruebas de la
  UI con API mockeada, no recorridos integrados: prod no permite forzar 100+ filas, un fallo del
  backend ni un usuario con perfil privado sin tocar datos reales.
- TC-12-005 (perfil privado): el frontend no filtra nada, solo pinta lo que manda el backend. El mock
  verifica eso; que el backend excluya a los privados se prueba en el backend, no aquí.
"""

import json
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, Route

from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import locator_has_visible_match, wait_for_app_ready, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_LOAD_TIMEOUT = 15_000
_ROLE = "student"

_RANKINGS_ROUTE = "**/api/v1/rankings/**"
_USER_RANKINGS_PATH = "/api/v1/rankings/users/"
_PAGE_SIZE = 50  # LEADERBOARD_PAGE_SIZE del frontend

_TAB_GLOBAL = "Clasificación Global"
_TAB_INSTITUTIONAL = "Ranking institucional"
_TAB_PRIVATE_CLAN = "Clanes privados"
_USER_HEADING = "Participante"
_CLAN_HEADING = "Equipo"
_PRIVATE_USER_NAME = "E2E Usuario Privado"

Handler = Callable[[Route], None]


# --- privadas: apertura y lectura --------------------------------------------------------------

def _open_leaderboard(page: Page, *, mock: Handler | None = None) -> None:
    """Sign in, optionally mock the rankings API, open /leaderboard and wait for its title."""
    login_as(page, _ROLE)
    if mock is not None:
        page.route(_RANKINGS_ROUTE, mock)  # antes de navegar para interceptar la primera carga
    go_to(page, "/leaderboard")
    wait_for_app_ready(page)
    page.locator(Locs.LEADERBOARD_TITLE).first.wait_for(state="visible", timeout=_LOAD_TIMEOUT)


def _content_state(page: Page) -> str | None:
    """Return "table", "empty" or "error" once the ranking finished loading, else None."""
    for state, selector in (
        ("table", Locs.LEADERBOARD_TABLE),
        ("empty", Locs.LEADERBOARD_EMPTY_TITLE),
        ("error", Locs.LEADERBOARD_ERROR_TITLE),
    ):
        if locator_has_visible_match(page.locator(selector)):
            return state
    return None


def _wait_for_content(page: Page, *, timeout: int = _LOAD_TIMEOUT) -> str:
    """Wait until the ranking is not loading anymore and return its state; raise on timeout."""
    found: list[str] = []

    def _done() -> bool:
        state = _content_state(page)
        if state:
            found.append(state)
        return bool(state)

    if not wait_until(_done, page, timeout=timeout, poll_ms=150):
        raise RuntimeError(f"El ranking no terminó de cargar en {timeout} ms (URL: {page.url})")
    return found[-1]


def _row_count(page: Page) -> int:
    return page.locator(Locs.LEADERBOARD_ROWS).count()


def _column_texts(page: Page, column: int) -> list[str]:
    return [t.strip() for t in page.locator(f"{Locs.LEADERBOARD_ROWS}/td[{column}]").all_inner_texts()]


def _cell_text(page: Page, row: int, column: int) -> str:
    return page.locator(Locs.leaderboard_cell_with_position(row, column)).first.inner_text(timeout=500).strip()


def _is_tab_selected(page: Page, label: str) -> bool:
    tab = page.locator(Locs.leaderboard_tab_with_text(label)).first
    return tab.get_attribute("aria-selected", timeout=_SHORT_TIMEOUT) == "true"


def _open_tab(page: Page, label: str, ranking_type: str) -> int:
    """Click a tab and return the HTTP status of the rankings request it triggers."""
    with page.expect_response(
        lambda r: "/api/v1/rankings/" in r.url and f"type={ranking_type}" in r.url, timeout=_LOAD_TIMEOUT
    ) as response_info:
        click_robust(page, Locs.leaderboard_tab_with_text(label))
    return response_info.value.status


def _progress_text(page: Page) -> str:
    return page.locator(Locs.LEADERBOARD_PAGER_PROGRESS).first.get_attribute("aria-valuetext", timeout=500) or ""


def _wait_for_page(page: Page, expected: str, first_rank: int) -> bool:
    """Wait until the pager says `expected` and the first row has rank `first_rank`."""
    return wait_until(
        lambda: _progress_text(page) == expected and _cell_text(page, 1, 1) == str(first_rank),
        page,
        timeout=_LOAD_TIMEOUT,
        poll_ms=150,
    )


# --- privadas: mocks de la API ----------------------------------------------------------------

def _fake_rows(total: int) -> list[dict[str, object]]:
    return [
        {"id": f"mock-{i}", "rank": i, "display_name": f"E2E Mock {i}", "avatar_url": "", "total_points": 1000 - i}
        for i in range(1, total + 1)
    ]


def _fulfill_json(route: Route, body: object, *, status: int = 200) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def _paged_mock(total: int) -> Handler:
    """Serve `total` fake rows honoring the limit/offset query of the request."""
    rows = _fake_rows(total)

    def _handler(route: Route) -> None:
        query = parse_qs(urlsplit(route.request.url).query)
        limit = int(query.get("limit", [_PAGE_SIZE])[0])
        offset = int(query.get("offset", [0])[0])
        _fulfill_json(route, {"count": total, "results": rows[offset : offset + limit]})

    return _handler


# --- tests ------------------------------------------------------------------------------------

def test_01_12_001_checkSetUp(page: Page) -> bool:
    """TC-12-001: /leaderboard muestra título y tres pestañas, con Global activa."""
    _open_leaderboard(page)
    labels = [_TAB_GLOBAL, _TAB_INSTITUTIONAL, _TAB_PRIVATE_CLAN]
    for label in labels:
        if not locator_has_visible_match(page.locator(Locs.leaderboard_tab_with_text(label)), timeout=_SHORT_TIMEOUT):
            logger.error("No se ve la pestaña %r", label)
            return False
    if page.locator(Locs.LEADERBOARD_TABS).count() != len(labels):
        logger.error("Se esperaban %s pestañas", len(labels))
        return False
    if not _is_tab_selected(page, _TAB_GLOBAL):
        logger.error("La pestaña %r no está activa por defecto", _TAB_GLOBAL)
        return False
    state = _wait_for_content(page)
    logger.info("Estado inicial del ranking: %s", state)
    return state != "error"


def test_01_12_002_checkDefaultGlobalRanking(page: Page) -> bool:
    """TC-12-001: la clasificación global trae Pos./Participante/Puntos, con posiciones ascendentes."""
    with page.expect_response(
        lambda r: _USER_RANKINGS_PATH in r.url, timeout=_LOAD_TIMEOUT
    ) as response_info:
        _open_leaderboard(page)
    if response_info.value.status != 200:
        logger.error("El ranking global respondió %s", response_info.value.status)
        return False
    if _wait_for_content(page) != "table":
        logger.error("El ranking global no mostró una tabla")
        return False
    headers = [t.strip().lower() for t in page.locator("//main//table/thead//th").all_inner_texts()]
    if headers != ["pos.", _USER_HEADING.lower(), "puntos"]:
        logger.error("Encabezados inesperados: %s", headers)
        return False
    ranks, points = _column_texts(page, 1), _column_texts(page, 3)
    if not ranks or len(ranks) > _PAGE_SIZE:
        logger.error("Número de filas inesperado: %s", len(ranks))
        return False
    if not all(r.isdigit() for r in ranks) or [int(r) for r in ranks] != sorted(int(r) for r in ranks):
        logger.error("Las posiciones no son numéricas y ascendentes: %s", ranks)
        return False
    if not all(p.lstrip("-").isdigit() for p in points):
        logger.error("Hay puntos no numéricos: %s", points)
        return False
    return True


def _check_clan_tab(page: Page, label: str, ranking_type: str) -> bool:
    _open_leaderboard(page)
    _wait_for_content(page)
    status = _open_tab(page, label, ranking_type)
    if status != 200:
        logger.error("type=%s respondió %s", ranking_type, status)
        return False
    state = _wait_for_content(page)
    if state == "error":
        logger.error("La pestaña %r mostró el estado de error", label)
        return False
    if not _is_tab_selected(page, label) or _is_tab_selected(page, _TAB_GLOBAL):
        logger.error("La pestaña %r no quedó como única activa", label)
        return False
    if state == "table":
        heading = page.locator(Locs.LEADERBOARD_NAME_HEADER).first.inner_text().strip()
        if heading.lower() != _CLAN_HEADING.lower():  # el th usa text-transform: uppercase
            logger.error("Encabezado %r, se esperaba %r", heading, _CLAN_HEADING)
            return False
    else:
        logger.warning("El ranking %s está vacío en este ambiente; solo se validó el cambio de pestaña", ranking_type)
    return True


def test_01_12_003_checkInstitutionalRanking(page: Page) -> bool:
    """TC-12-002: la pestaña Ranking institucional pide type=INSTITUTIONAL y muestra equipos."""
    return _check_clan_tab(page, _TAB_INSTITUTIONAL, "INSTITUTIONAL")


def test_01_12_004_checkPrivateClanRanking(page: Page) -> bool:
    """TC-12-003: la pestaña Clanes privados pide type=PRIVATE_CLAN y muestra equipos."""
    return _check_clan_tab(page, _TAB_PRIVATE_CLAN, "PRIVATE_CLAN")


def test_01_12_005_checkPagination(page: Page) -> bool:
    """TC-12-004 (API mockeada): 120 filas son 3 páginas de 50/50/20; cambiar de pestaña regresa a la 1."""
    total = 120
    _open_leaderboard(page, mock=_paged_mock(total))
    if _wait_for_content(page) != "table" or _row_count(page) != _PAGE_SIZE:
        logger.error("La primera página debería tener %s filas (hay %s)", _PAGE_SIZE, _row_count(page))
        return False
    if not _wait_for_page(page, "Página 1 de 3", 1) or not page.locator(Locs.LEADERBOARD_PAGER_PREV).first.is_disabled():
        logger.error("La página 1 debe decir 'Página 1 de 3' con 'Anterior' deshabilitado")
        return False

    click_robust(page, Locs.LEADERBOARD_PAGER_NEXT)
    if not _wait_for_page(page, "Página 2 de 3", 51) or _row_count(page) != _PAGE_SIZE:
        logger.error("La página 2 debe empezar en la posición 51 con 50 filas")
        return False

    click_robust(page, Locs.LEADERBOARD_PAGER_NEXT)
    if not _wait_for_page(page, "Página 3 de 3", 101) or _row_count(page) != total - 2 * _PAGE_SIZE:
        logger.error("La página 3 debe empezar en la posición 101 con 20 filas")
        return False
    if not page.locator(Locs.LEADERBOARD_PAGER_NEXT).first.is_disabled():
        logger.error("'Siguiente' debe estar deshabilitado en la última página")
        return False

    click_robust(page, Locs.LEADERBOARD_PAGER_PREV)
    if not _wait_for_page(page, "Página 2 de 3", 51):
        logger.error("'Anterior' no regresó a la página 2")
        return False

    click_robust(page, Locs.leaderboard_tab_with_text(_TAB_INSTITUTIONAL))
    return _wait_for_page(page, "Página 1 de 3", 1)


def test_01_12_006_checkPrivateUsersNotListed(page: Page) -> bool:
    """TC-12-005 (API mockeada): la tabla muestra exactamente los usuarios que manda la API."""
    public = [
        {"id": f"mock-{i}", "rank": i, "display_name": f"E2E Publico {i}", "avatar_url": "", "total_points": 300 - i}
        for i in range(1, 4)
    ]
    _open_leaderboard(page, mock=lambda route: _fulfill_json(route, {"count": len(public), "results": public}))
    if _wait_for_content(page) != "table" or _row_count(page) != len(public):
        logger.error("Se esperaban %s filas, hay %s", len(public), _row_count(page))
        return False
    if locator_has_visible_match(page.locator(Locs.leaderboard_row_with_name(_PRIVATE_USER_NAME))):
        logger.error("Apareció un usuario que la API no devolvió")
        return False
    return all(
        locator_has_visible_match(page.locator(Locs.leaderboard_row_with_name(str(u["display_name"]))), timeout=_SHORT_TIMEOUT)
        for u in public
    )


def test_01_12_007_checkEmptyState(page: Page) -> bool:
    """TC-12-006 (API mockeada): sin resultados se muestra 'Aún no hay clasificación', sin tabla ni paginador."""
    _open_leaderboard(page, mock=lambda route: _fulfill_json(route, {"count": 0, "results": []}))
    if _wait_for_content(page) != "empty":
        logger.error("No se mostró el estado vacío")
        return False
    return not locator_has_visible_match(page.locator(Locs.LEADERBOARD_TABLE)) and not locator_has_visible_match(
        page.locator(Locs.LEADERBOARD_PAGER)
    )


def test_01_12_008_checkErrorStateAndRetry(page: Page) -> bool:
    """TC-12-006 (API mockeada): un 500 muestra el error con 'Reintentar'; al recuperarse, la tabla aparece."""
    healthy = {"count": 2, "results": _fake_rows(2)}
    failing = {"value": True}

    def _handler(route: Route) -> None:
        if failing["value"]:
            _fulfill_json(route, {"detail": "boom"}, status=500)
        else:
            _fulfill_json(route, healthy)

    _open_leaderboard(page, mock=_handler)
    if _wait_for_content(page) != "error":
        logger.error("No se mostró el estado de error")
        return False
    if not locator_has_visible_match(page.locator(Locs.LEADERBOARD_RETRY_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("Falta el botón 'Reintentar'")
        return False
    failing["value"] = False
    click_robust(page, Locs.LEADERBOARD_RETRY_BUTTON)
    return _wait_for_content(page) == "table" and _row_count(page) == 2
