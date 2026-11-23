"""Acciones del módulo 03 · Dashboard (tests/Dashboard/test_Dashboard.py).

Módulo de solo lectura: no crea datos. Los TC con datos reales capturan la respuesta que la UI
consumió (capture_json_response) y comparan el DOM contra ese cuerpo, así no hay carrera con los
otros módulos que escriben en paralelo. Los TC 005 y 007 usan mocks (estado vacío y error).
EE = 00 es provisional hasta que se haga el reparto de equipos.
"""

import copy
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from playwright.sync_api import Page

from src.configs import environment as env
from src.utils.api import api_for_page
from src.utils.common_actions import click_filter_chip, go_to, login_as
from src.utils.helpers import locator_has_visible_match, wait_for_app_ready, wait_for_path, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import capture_json_response, mock_api_error, mock_api_json

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_TIMEOUT = env.DEFAULT_TIMEOUT
_PROFILE_PATH = "/api/v1/profile/me/"
_TREND_PATH = "/api/v1/profile/me/impact-trend/"
_CAMPAIGNS_PATH = "/api/v1/campaigns/"
_REGISTER_PATH = "/actions/register"
_STUDENT_ROLE = "student"

# Viewport 1440 px (breakpoint lg): 6 tarjetas por página (hooks/use-campaign-page-size.ts).
_CARDS_PER_PAGE = 6
_MAX_CAMPAIGN_PAGES = 20  # mismo tope que lib/api/campaigns.ts (MAX_PAGES)

_TZ = ZoneInfo("America/Mexico_City")
_ONE_DECIMAL = Decimal("0.1")
# Abreviaturas que devuelve Intl es-MX (mes corto) para el eje X de la tendencia.
_MONTHS_ES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
_TREND_WEEKS = 4
_TREND_CHARTS = 3

_STATUS_GROUP = "Filtrar campañas por estado"
_SCOPE_GROUP = "Filtrar campañas por alcance"
# (grupo, texto del chip, campo del filtro, valor del filtro)
_FILTER_STEPS: tuple[tuple[str, str, str, str], ...] = (
    (_STATUS_GROUP, "Activas", "status", "IN_PROGRESS"),
    (_SCOPE_GROUP, "De clan", "scope", "PRIVATE"),
    (_STATUS_GROUP, "Finalizadas", "status", "FINISHED"),
    (_STATUS_GROUP, "En promoción", "status", "PROMOTION"),
    (_STATUS_GROUP, "Todas", "status", "ALL"),
    (_SCOPE_GROUP, "Todas", "scope", "ALL"),
)


# --- privadas: formato, rutas y lectura del DOM ---------------------------------------------


def _is_path(path: str) -> Callable[[str], bool]:
    """Predicado para capture_json_response: la URL tiene exactamente este path."""
    return lambda url: urlsplit(url).path == path


def _is_participating_list(url: str) -> bool:
    """Predicado para la lista de campañas que pide el Dashboard (participating=true)."""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    # La UI sigue la paginación (page=1, 2, ...): la que cuenta como "página 1" es la primera.
    return (
        parts.path == _CAMPAIGNS_PATH and query.get("participating") == ["true"] and query.get("page", ["1"]) == ["1"]
    )


def _format_number_es_mx(value: Decimal | float | str) -> str:
    """Formatea como Intl es-MX con maximumFractionDigits=1 (redondeo medio hacia arriba, miles con coma)."""
    rounded = Decimal(str(value)).quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)
    text = f"{rounded:,.1f}"
    return text.removesuffix(".0")


def _axis_label(week_start: str) -> str:
    """Etiqueta del eje X ('dd-mmm') a partir de 'YYYY-MM-DD'; la UI la formatea en UTC."""
    _, month, day = week_start.split("-")
    return f"{int(day):02d}-{_MONTHS_ES[int(month) - 1]}"


def _items_of(body: Any) -> list[dict]:
    """Items de una respuesta paginada (dict con results) o de una lista plana."""
    return list(body["results"]) if isinstance(body, dict) else list(body)


def _all_participating(page: Page, body: Any) -> list[dict]:
    """Campañas que renderiza el Dashboard: la página 1 es el cuerpo capturado; el resto, de la API."""
    campaigns = _items_of(body)
    if not isinstance(body, dict) or not body.get("next"):
        return campaigns
    api = api_for_page(page)
    for page_number in range(2, _MAX_CAMPAIGN_PAGES + 1):
        data = api.json(_STUDENT_ROLE, "GET", _CAMPAIGNS_PATH, params={"participating": "true", "page": page_number})
        campaigns.extend(_items_of(data))
        if not data.get("next"):
            break
    return campaigns


def _expected_tiles(profile: dict) -> dict[str, str]:
    """Texto esperado de cada tarjeta de 'Tu impacto' según el cuerpo de profile/me/."""
    metrics = profile["impact_metrics"]
    return {
        "CO₂ evitado": f"{_format_number_es_mx(metrics['co2_kg'])} kg",
        "Agua ahorrada": f"{_format_number_es_mx(metrics['water_liters'])} L",
        "Plástico evitado": f"{_format_number_es_mx(metrics['plastic_kg'])} kg",
        "Puntos totales": _format_number_es_mx(profile["total_points"]),
        "Racha actual": f"{_format_number_es_mx(profile['current_streak'])} días",
    }


def _tile_value(page: Page, label: str) -> str:
    """Texto del valor de la tarjeta de impacto cuyo título es `label` (p. ej. '12.3 kg')."""
    section = page.locator(Locs.DASHBOARD_IMPACT_TITLE).locator("xpath=ancestor::section[1]")
    value = section.locator(f"xpath=.//*[normalize-space(.)='{label}']").first.locator("xpath=following-sibling::p[1]")
    return (value.text_content(timeout=_SHORT_TIMEOUT) or "").strip()


def _safe(read: Callable[[], Any]) -> Any:
    """Ejecuta una lectura del DOM y devuelve None si falla (para usarla dentro de un polling)."""
    try:
        return read()
    except Exception:  # noqa: BLE001
        return None


def _wait_equal(page: Page, read: Callable[[], Any], expected: Any, *, timeout: int = _TIMEOUT) -> bool:
    """Espera (polling) hasta que `read()` regrese `expected`."""
    return wait_until(lambda: _safe(read) == expected, page, timeout=timeout)


def _is_visible(page: Page, xpath: str, *, timeout: int = _SHORT_TIMEOUT) -> bool:
    """True si el primer elemento que coincide con el XPath se ve en `timeout` ms."""
    return locator_has_visible_match(page.locator(xpath), timeout=timeout)


def _texts(page: Page, xpath: str) -> list[str]:
    """Textos (sin espacios de sobra) de todos los elementos que coinciden con el XPath."""
    return [text.strip() for text in page.locator(xpath).all_text_contents()]


def _tick_labels(page: Page) -> list[list[str]]:
    """Etiquetas visibles del eje X de cada gráfica de tendencia, en el orden del DOM."""
    charts = page.locator(Locs.DASHBOARD_TREND_SECTION).locator(Locs.DASHBOARD_TREND_CHART)
    return [
        [text.strip() for text in charts.nth(index).locator(Locs.DASHBOARD_TREND_X_TICK).all_text_contents()]
        for index in range(charts.count())
    ]


def _ticks_match(labels: list[list[str]], weeks: Sequence[str]) -> bool:
    """True when every chart shows its X labels in week order, from `weeks`, ending with the last week.

    Recharts oculta etiquetas cuando no caben (en 1440px suele saltarse la primera semana), así que no se
    exige ver las 4: solo que las visibles sean semanas esperadas, en orden y que esté la semana actual.
    """
    if len(labels) != _TREND_CHARTS:
        return False
    for chart in labels:
        if not chart or chart[-1] != weeks[-1] or any(label not in weeks for label in chart):
            return False
        positions = [weeks.index(label) for label in chart]
        if positions != sorted(set(positions)):
            return False
    return True


def _wait_ticks(page: Page, weeks: Sequence[str]) -> bool:
    if wait_until(lambda: _ticks_match(_tick_labels(page), weeks), page, timeout=_TIMEOUT):
        return True
    logger.error(
        "Eje X: se esperaban semanas de %s (en orden, terminando en %s); se ven %s",
        list(weeks),
        weeks[-1],
        _tick_labels(page),
    )
    return False


def _active_groups(campaigns: list[dict]) -> list[dict]:
    """Campañas que muestra 'Misiones activas': IN_PROGRESS, inscritas y con misiones."""
    return [
        campaign
        for campaign in campaigns
        if campaign.get("status") == "IN_PROGRESS"
        and campaign.get("is_participant") is True
        and campaign.get("missions")
    ]


def _matches(campaign: dict, filters: dict[str, str]) -> bool:
    """Si la campaña pasa los filtros de estado y alcance de 'Mis campañas'."""
    return (filters["status"] == "ALL" or campaign.get("status") == filters["status"]) and (
        filters["scope"] == "ALL" or campaign.get("scope") == filters["scope"]
    )


def _check_visible_cards(page: Page, campaigns: list[dict], matching: list[dict]) -> bool:
    """Compara las tarjetas visibles (página 1) con las campañas que pasan el filtro."""
    if not campaigns:
        ok = _is_visible(page, Locs.DASHBOARD_EMPTY_CAMPAIGNS, timeout=_TIMEOUT)
    elif not matching:
        ok = _is_visible(page, Locs.DASHBOARD_NO_FILTER_MATCH, timeout=_TIMEOUT)
    else:
        expected = [campaign["title"] for campaign in matching[:_CARDS_PER_PAGE]]
        ok = _wait_equal(page, lambda: _texts(page, Locs.DASHBOARD_MY_CAMPAIGN_CARD_TITLE), expected)
        if ok and len(matching) > _CARDS_PER_PAGE:
            ok = _is_visible(page, Locs.DASHBOARD_CAMPAIGNS_PAGINATION)
    if not ok:
        logger.error("Las tarjetas de 'Mis campañas' no coinciden con el filtro (%s coincidencias)", len(matching))
    return ok


def _zero_profile(profile: dict) -> dict:
    """Copia del perfil real con todos los totales en cero (cuenta nueva, conserva la identidad)."""
    zeroed = copy.deepcopy(profile)
    zeroed["total_points"] = 0
    zeroed["available_points"] = 0
    zeroed["current_streak"] = 0
    zeroed["impact_metrics"] = {"co2_kg": "0.000", "water_liters": "0.000", "plastic_kg": "0.000"}
    zeroed["finished_campaigns"] = []
    zeroed["badges"] = []
    return zeroed


def _zero_trend() -> list[dict]:
    """Cuatro semanas (lunes, oldest first) en cero, como la respuesta de impact-trend."""
    today = datetime.now(_TZ).date()
    current_week = today - timedelta(days=today.weekday())
    weeks = [current_week - timedelta(weeks=offset) for offset in range(_TREND_WEEKS - 1, -1, -1)]
    return [
        {"week_start": week.isoformat(), "co2_kg": "0.000", "water_liters": "0.000", "plastic_kg": "0.000"}
        for week in weeks
    ]


# --- tests ----------------------------------------------------------------------------------


def test_00_03_001_checkImpactMetrics(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    profile: dict = capture_json_response(page, _is_path(_PROFILE_PATH), lambda: go_to(page, "/"))
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_IMPACT_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve la sección 'Tu impacto'")
        return False
    ok = True
    for label, expected in _expected_tiles(profile).items():
        read = partial(_tile_value, page, label)
        if not _wait_equal(page, read, expected):
            logger.error("Tarjeta '%s': se muestra '%s', se esperaba '%s'", label, _safe(read), expected)
            ok = False
        else:
            logger.info("Tarjeta '%s' = %s", label, expected)
    return ok


def test_00_03_002_checkImpactTrend(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    points: list[dict] = capture_json_response(page, _is_path(_TREND_PATH), lambda: go_to(page, "/"))
    wait_for_app_ready(page)
    if len(points) != _TREND_WEEKS:
        logger.error("impact-trend devolvió %s semanas, se esperaban %s", len(points), _TREND_WEEKS)
        return False
    if not _is_visible(page, Locs.DASHBOARD_TREND_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve el título 'Tendencia (últimas 4 semanas)'")
        return False
    trend = page.locator(Locs.DASHBOARD_TREND_SECTION)
    if not _wait_equal(page, lambda: trend.locator(Locs.DASHBOARD_TREND_CHART).count(), _TREND_CHARTS):
        logger.error("Se esperaban %s gráficas de tendencia", _TREND_CHARTS)
        return False
    weeks = [_axis_label(point["week_start"]) for point in points]
    if not _wait_ticks(page, weeks):
        return False
    logger.info("Tendencia: semanas %s", weeks)
    return True


def test_00_03_003_checkActiveMissions(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    body = capture_json_response(page, _is_participating_list, lambda: go_to(page, "/"))
    wait_for_app_ready(page)
    groups = _active_groups(_all_participating(page, body))
    if not groups:
        logger.info("Sin misiones activas: se revisa el estado vacío")
        return _is_visible(page, Locs.DASHBOARD_NO_ACTIVE_MISSIONS, timeout=_TIMEOUT)

    expected_titles = [campaign["title"] for campaign in groups]
    if not _wait_equal(page, lambda: _texts(page, Locs.DASHBOARD_ACTIVE_GROUP_TITLES), expected_titles):
        logger.error("Campañas de 'Misiones activas': se esperaban %s", expected_titles)
        return False

    for index, campaign in enumerate(groups):
        container = page.locator(Locs.DASHBOARD_ACTIVE_GROUP_TITLES).nth(index).locator("xpath=..")
        text = container.text_content(timeout=_SHORT_TIMEOUT) or ""
        progress = {item["mission"]: item for item in campaign.get("user_mission_progress") or []}
        for mission in campaign["missions"]:
            action = mission["action"]
            expected_bits = [
                action["name"],
                f"Meta: {mission['target_count']} veces",
                f"+{action['points']} pts",
            ]
            if mission["id"] in progress:
                current = progress[mission["id"]]["current_count"]
                expected_bits.append(f"{current}/{mission['target_count']}")
            missing = [bit for bit in expected_bits if bit not in text]
            if missing:
                logger.error("Misión '%s' de '%s': faltan %s", action["name"], campaign["title"], missing)
                return False

    first_mission = groups[0]["missions"][0]
    page.locator(Locs.button_with_aria("Registrar acción")).first.click()
    try:
        wait_for_path(page, _REGISTER_PATH)
    except RuntimeError as exc:
        logger.error("'Registrar acción' no navegó al registro: %s", exc)
        return False
    action_param = parse_qs(urlsplit(page.url).query).get("action", [])
    if action_param != [first_mission["action"]["code"]]:
        logger.error("La URL %s no lleva action=%s", page.url, first_mission["action"]["code"])
        return False
    return True


def test_00_03_004_checkMyCampaignsFilter(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    body = capture_json_response(page, _is_participating_list, lambda: go_to(page, "/"))
    wait_for_app_ready(page)
    campaigns = _all_participating(page, body)
    if not _is_visible(page, Locs.DASHBOARD_MY_CAMPAIGNS_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve la sección 'Mis campañas'")
        return False

    filters = {"status": "ALL", "scope": "ALL"}
    for group_label, chip_text, field, value in _FILTER_STEPS:
        click_filter_chip(page, group_label, chip_text)
        filters[field] = value
        matching = [campaign for campaign in campaigns if _matches(campaign, filters)]
        logger.info("Filtro %s=%s (%s): %s coincidencias", field, value, chip_text, len(matching))
        if not _check_visible_cards(page, campaigns, matching):
            return False
    return True


def test_00_03_005_checkNewUserEmptyStates(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    profile = api_for_page(page).json(_STUDENT_ROLE, "GET", _PROFILE_PATH)
    mock_api_json(page, f"**{_PROFILE_PATH}", _zero_profile(profile))
    trend = _zero_trend()
    mock_api_json(page, f"**{_TREND_PATH}", trend)
    mock_api_json(page, f"**{_CAMPAIGNS_PATH}**", {"results": [], "next": None})

    go_to(page, "/")
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_IMPACT_TITLE, timeout=_TIMEOUT):
        logger.error("El usuario nuevo no ve 'Tu impacto'")
        return False

    ok = True
    for label, expected in _expected_tiles(_zero_profile(profile)).items():
        if not _wait_equal(page, partial(_tile_value, page, label), expected):
            logger.error("Tarjeta '%s' en cero: se esperaba '%s'", label, expected)
            ok = False

    if not _wait_ticks(page, [_axis_label(point["week_start"]) for point in trend]):
        logger.error("Tendencia en cero: el eje X no coincide")
        ok = False

    if not _is_visible(page, Locs.DASHBOARD_EMPTY_CAMPAIGNS, timeout=_TIMEOUT):
        logger.error("No se ve el estado vacío 'Aún no participas en campañas'")
        ok = False
    join_link = page.locator(Locs.DASHBOARD_JOIN_CAMPAIGN_LINK).first
    if not _is_visible(page, Locs.DASHBOARD_JOIN_CAMPAIGN_LINK, timeout=_TIMEOUT):
        logger.error("No se ve el enlace 'Unirme a una campaña'")
        ok = False
    elif join_link.get_attribute("href") != "/campaigns":
        logger.error("'Unirme a una campaña' apunta a %s", join_link.get_attribute("href"))
        ok = False
    if not _is_visible(page, Locs.DASHBOARD_NO_ACTIVE_MISSIONS, timeout=_TIMEOUT):
        logger.error("No se ve el estado vacío 'No tienes misiones activas'")
        ok = False
    return ok


def test_00_03_006_checkAdminSimpleDashboard(page: Page) -> bool:
    login_as(page, "admin")
    go_to(page, "/")
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_ADMIN_TITLE, timeout=_TIMEOUT):
        logger.error("El admin no ve el dashboard simple 'Dashboard'")
        return False
    for label, xpath in (
        ("Tu impacto", Locs.DASHBOARD_IMPACT_TITLE),
        ("Tendencia", Locs.DASHBOARD_TREND_TITLE),
        ("Mis campañas", Locs.DASHBOARD_MY_CAMPAIGNS_TITLE),
    ):
        if page.locator(xpath).count() > 0:
            logger.error("El admin no debería ver la sección '%s'", label)
            return False
    return True


def test_00_03_007_checkProfileLoadError(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    handle = mock_api_error(page, f"**{_PROFILE_PATH}", status=500)
    go_to(page, "/")
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_PROFILE_ERROR_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve el error 'No se pudo cargar tu impacto'")
        return False
    if not handle.requests:
        logger.error("El mock de profile/me/ no interceptó ninguna petición")
        return False
    # Un fallo en un bloque no tira las demás secciones del dashboard.
    if not _is_visible(page, Locs.DASHBOARD_TREND_TITLE, timeout=_TIMEOUT):
        logger.error("La tendencia dejó de mostrarse por el fallo de profile/me/")
        return False

    handle.restore()
    page.locator(Locs.DASHBOARD_PROFILE_ERROR_RETRY).first.click()
    if not _is_visible(page, Locs.DASHBOARD_IMPACT_TITLE, timeout=_TIMEOUT):
        logger.error("Tras 'Reintentar' no carga 'Tu impacto'")
        return False
    return True


def test_00_03_008_checkTrendLoadError(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    handle = mock_api_error(page, f"**{_TREND_PATH}", status=500)
    go_to(page, "/")
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_TREND_ERROR_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve el error 'No se pudo cargar tu tendencia'")
        return False
    if not handle.requests:
        logger.error("El mock de impact-trend no interceptó ninguna petición")
        return False
    if not _is_visible(page, Locs.DASHBOARD_IMPACT_TITLE, timeout=_TIMEOUT):
        logger.error("El perfil dejó de mostrarse por el fallo de impact-trend")
        return False

    handle.restore()
    page.locator(Locs.DASHBOARD_TREND_ERROR_RETRY).first.click()
    if not _is_visible(page, Locs.DASHBOARD_TREND_TITLE, timeout=_TIMEOUT):
        logger.error("Tras 'Reintentar' no carga la tendencia")
        return False
    return True


def test_00_03_009_checkCampaignsLoadError(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    handle = mock_api_error(page, _is_participating_list, status=500)
    go_to(page, "/")
    wait_for_app_ready(page)
    if not _is_visible(page, Locs.DASHBOARD_CAMPAIGNS_ERROR_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve el error de 'Mis campañas'")
        return False
    if not _is_visible(page, Locs.DASHBOARD_MISSIONS_ERROR_TITLE, timeout=_TIMEOUT):
        logger.error("No se ve el error de 'Misiones activas'")
        return False
    if not handle.requests:
        logger.error("El mock de campañas participantes no interceptó ninguna petición")
        return False

    handle.restore()
    page.locator(Locs.DASHBOARD_CAMPAIGNS_RETRY).first.click()
    recovered = wait_until(
        lambda: page.locator(Locs.DASHBOARD_CAMPAIGNS_ERROR_TITLE).count() == 0
        and (
            page.locator(Locs.DASHBOARD_MY_CAMPAIGN_CARD).count() > 0
            or locator_has_visible_match(page.locator(Locs.DASHBOARD_EMPTY_CAMPAIGNS), timeout=200)
            or locator_has_visible_match(page.locator(Locs.DASHBOARD_NO_FILTER_MATCH), timeout=200)
        ),
        page,
        timeout=_TIMEOUT,
    )
    if not recovered:
        logger.error("El error de campañas siguió visible después de reintentar")
        return False
    return True


def test_00_03_010_checkCampaignDetail(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    body = capture_json_response(page, _is_participating_list, lambda: go_to(page, "/"))
    wait_for_app_ready(page)
    campaigns = _all_participating(page, body)
    if not campaigns:
        logger.info("Sin campañas participantes: el detalle no puede abrirse")
        return _is_visible(page, Locs.DASHBOARD_EMPTY_CAMPAIGNS, timeout=_TIMEOUT)

    campaign = campaigns[0]
    campaign_id = str(campaign["id"])
    title = str(campaign["title"])
    detail_path = f"/api/v1/campaigns/{campaign_id}/"
    card = page.locator(Locs.DASHBOARD_MY_CAMPAIGN_CARD).first
    if not _is_visible(page, Locs.DASHBOARD_MY_CAMPAIGN_CARD, timeout=_TIMEOUT):
        logger.error("No se encuentra ninguna tarjeta dentro de 'Mis campañas'")
        return False

    detail = capture_json_response(
        page,
        lambda url: urlsplit(url).path == detail_path,
        lambda: card.click(),
    )
    if not _is_visible(page, Locs.DASHBOARD_CAMPAIGN_DETAIL_DIALOG, timeout=_TIMEOUT):
        logger.error("No se abrió el diálogo de detalle de la campaña")
        return False
    dialog_text = page.locator(Locs.DASHBOARD_CAMPAIGN_DETAIL_DIALOG).text_content(timeout=_SHORT_TIMEOUT) or ""
    expected_title = str(detail.get("title", title))
    if expected_title not in dialog_text:
        logger.error("El detalle no muestra el título '%s'", expected_title)
        return False
    if "Misiones" not in dialog_text:
        logger.error("El detalle no muestra la sección 'Misiones'")
        return False
    return True


def test_00_03_011_checkReloadPersistence(page: Page) -> bool:
    login_as(page, _STUDENT_ROLE)
    capture_json_response(page, _is_path(_PROFILE_PATH), lambda: go_to(page, "/"))
    wait_for_app_ready(page)

    reloaded_profile: dict = capture_json_response(page, _is_path(_PROFILE_PATH), lambda: page.reload())
    wait_for_app_ready(page)
    reloaded_expected = _expected_tiles(reloaded_profile)
    for label, expected_value in reloaded_expected.items():
        if not _wait_equal(page, partial(_tile_value, page, label), expected_value):
            logger.error("Después de recargar, '%s' no conserva '%s'", label, expected_value)
            return False
    if not _is_visible(page, Locs.DASHBOARD_TREND_TITLE, timeout=_TIMEOUT):
        logger.error("La tendencia no reaparece después de recargar")
        return False
    if not _is_visible(page, Locs.DASHBOARD_MY_CAMPAIGNS_TITLE, timeout=_TIMEOUT):
        logger.error("'Mis campañas' no reaparece después de recargar")
        return False
    return True


def test_00_03_012_checkMobileLayout(page: Page) -> bool:
    page.set_viewport_size({"width": 390, "height": 844})
    login_as(page, _STUDENT_ROLE)
    go_to(page, "/")
    wait_for_app_ready(page)
    for label, xpath in (
        ("Tu impacto", Locs.DASHBOARD_IMPACT_TITLE),
        ("Tendencia", Locs.DASHBOARD_TREND_TITLE),
        ("Mis campañas", Locs.DASHBOARD_MY_CAMPAIGNS_TITLE),
        ("Misiones activas", Locs.DASHBOARD_ACTIVE_MISSIONS_TITLE),
    ):
        if not _is_visible(page, xpath, timeout=_TIMEOUT):
            logger.error("En móvil no se ve la sección '%s'", label)
            return False
    has_horizontal_overflow = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    if has_horizontal_overflow:
        logger.error("El dashboard presenta desbordamiento horizontal en 390px")
        return False
    return True
