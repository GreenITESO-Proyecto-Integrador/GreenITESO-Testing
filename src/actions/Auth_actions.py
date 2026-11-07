"""Acciones del módulo 01 · Autenticación y sesión (tests/Auth/test_Auth.py).

TC-01-002 y TC-01-003 necesitan el login real de Microsoft y se quedan como pruebas manuales.
EE = 00 es provisional hasta que se haga el reparto de equipos.
"""

from collections.abc import Sequence

from playwright.sync_api import Page

from src.utils.common_actions import go_to, login_as, logout
from src.utils.helpers import (
    current_path,
    is_on_path,
    locator_has_visible_match,
    wait_for_app_ready,
    wait_for_path,
)
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_PROTECTED_PATHS = ("/profile", "/campaigns", "/store")
_UNKNOWN_PATH = "/ruta-que-no-existe"


# --- privadas -------------------------------------------------------------------------------

def _all_visible(page: Page, selectors: Sequence[str], *, timeout: int) -> bool:
    missing = [s for s in selectors if not locator_has_visible_match(page.locator(s), timeout=timeout)]
    for selector in missing:
        logger.error("No se ve: %s", selector)
    return not missing


def _expect_redirect_to_login(page: Page, path: str) -> bool:
    go_to(page, path)
    try:
        wait_for_path(page, "/login")
    except RuntimeError as exc:
        logger.error("%s no redirigió a /login: %s", path, exc)
        return False
    if not locator_has_visible_match(page.locator(Locs.LOGIN_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("%s llegó a /login pero no se ve la tarjeta de login", path)
        return False
    logger.info("%s → /login", path)
    return True


# --- tests ----------------------------------------------------------------------------------

def test_00_01_001_checkLoginScreen(page: Page) -> bool:
    go_to(page, "/login")
    if not _all_visible(
        page,
        [Locs.LOGIN_BRAND, Locs.LOGIN_TITLE, Locs.LOGIN_BUTTON, Locs.LOGIN_INSTITUTIONAL_NOTICE],
        timeout=_SHORT_TIMEOUT,
    ):
        return False
    if not page.locator(Locs.LOGIN_BUTTON).first.is_enabled():
        logger.error("El botón de login está deshabilitado")
        return False
    if locator_has_visible_match(page.locator(Locs.LOGIN_NOT_CONFIGURED_ALERT)):
        logger.error("Se muestra el aviso 'Microsoft login no está configurado'")
        return False
    return True


def test_00_01_004_checkProtectedRouteRedirect(page: Page) -> bool:
    results = [_expect_redirect_to_login(page, path) for path in _PROTECTED_PATHS]
    return all(results)


def test_00_01_005_checkAuditBlockedForStudent(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/audit")
    if not _all_visible(
        page,
        [Locs.ACCESS_DENIED_TITLE, Locs.ACCESS_DENIED_BADGE, Locs.ACCESS_DENIED_BACK_BUTTON],
        timeout=_SHORT_TIMEOUT * 2,
    ):
        return False
    if not is_on_path(page, "/audit"):
        logger.error("Se esperaba seguir en /audit, la URL es %s", page.url)
        return False
    return True


def test_00_01_006_checkLogout(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/")
    wait_for_app_ready(page)
    logout(page)
    wait_for_path(page, "/login")
    if not locator_has_visible_match(page.locator(Locs.LOGIN_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("Después de cerrar sesión no se ve la pantalla de login")
        return False
    # La sesión no debe regresar al navegar de nuevo a una ruta protegida.
    return _expect_redirect_to_login(page, "/profile")


def test_00_01_007_checkSessionPersistsOnReload(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/profile")
    wait_for_app_ready(page)
    page.reload(wait_until="domcontentloaded")
    wait_for_app_ready(page)
    if not is_on_path(page, "/profile"):
        logger.error("Después de recargar la URL es %s, se esperaba /profile", current_path(page))
        return False
    return locator_has_visible_match(page.locator(Locs.PROFILE_NAME_TITLE), timeout=_SHORT_TIMEOUT * 2)


def test_00_01_008_checkUnknownRouteShowsDashboard(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, _UNKNOWN_PATH)
    wait_for_app_ready(page)
    if not locator_has_visible_match(page.locator(Locs.DASHBOARD_IMPACT_TITLE), timeout=_SHORT_TIMEOUT * 2):
        logger.error("La ruta desconocida no muestra el Dashboard ('Tu impacto')")
        return False
    return is_on_path(page, _UNKNOWN_PATH)
