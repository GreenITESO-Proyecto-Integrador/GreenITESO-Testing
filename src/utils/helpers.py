"""Helpers genéricos: chequeos de estado (is_*/has_*), esperas (wait_for_*) y utilidades
que no realizan una acción de negocio. Son independientes de cualquier módulo.
"""

import time
from collections.abc import Callable
from urllib.parse import urlsplit

import allure
from playwright.sync_api import Locator, Page

from src.configs import environment as env
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SETTLE_TIMEOUT = 5_000


def assert_action(action: Callable[[Page], bool], page: Page) -> None:
    """Run a module action and fail the test with a clear message if it returns False."""
    name = getattr(action, "__name__", str(action))
    with allure.step(name):
        result = action(page)
    assert result, f"La acción '{name}' regresó {result!r}"


def locator_has_visible_match(locator: Locator, *, timeout: int = 200) -> bool:
    """Return True when any element matched by `locator` becomes visible within `timeout` ms."""
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


def wait_until(condition: Callable[[], bool], page: Page, *, timeout: int = 10_000, poll_ms: int = 200) -> bool:
    """Poll `condition` until it returns True or `timeout` ms elapse."""
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        try:
            if condition():
                return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("wait_until: la condición lanzó %s", exc)
        page.wait_for_timeout(poll_ms)
    return False


def current_path(page: Page) -> str:
    """Return the path of the page's current URL (without query or fragment)."""
    return urlsplit(page.url).path


def is_on_path(page: Page, path: str) -> bool:
    """Return True when the page's current path is exactly `path`."""
    return current_path(page).rstrip("/") == path.rstrip("/")


def is_login_page(page: Page, *, timeout: int = 200) -> bool:
    """Return True when the login card is shown."""
    return locator_has_visible_match(page.locator(Locs.LOGIN_BUTTON), timeout=timeout)


def is_authenticated_layout(page: Page, *, timeout: int = 200) -> bool:
    """Return True when the app layout with the signed-in user menu is shown."""
    return locator_has_visible_match(page.locator(Locs.USER_MENU_BUTTON), timeout=timeout)


def wait_for_path(page: Page, path: str, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Wait until the page's path is `path`; raise RuntimeError otherwise."""
    if not wait_until(lambda: is_on_path(page, path), page, timeout=timeout):
        raise RuntimeError(f"La URL no llegó a {path} en {timeout} ms (actual: {page.url})")


def wait_for_app_ready(page: Page, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Wait for the signed-in layout; fail fast if the app went to login or shows the onboarding gate."""
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if locator_has_visible_match(page.locator(Locs.ONBOARDING_DIALOG)):
            raise RuntimeError(
                "Se muestra 'Completa tu perfil': el usuario de prueba no tiene clan institucional. "
                "Completa el onboarding una vez a mano con esa cuenta."
            )
        if is_on_path(page, "/login") or is_login_page(page):
            raise RuntimeError("La app mandó a /login: la sesión inyectada no fue aceptada.")
        if is_authenticated_layout(page):
            # El gate de onboarding se abre después de una llamada a la API: dale chance de aparecer.
            try:
                page.wait_for_load_state("networkidle", timeout=_SETTLE_TIMEOUT)
            except Exception:  # noqa: BLE001
                logger.debug("wait_for_app_ready: la red no se calmó en %s ms", _SETTLE_TIMEOUT)
            if locator_has_visible_match(page.locator(Locs.ONBOARDING_DIALOG)):
                continue
            return
        page.wait_for_timeout(150)
    raise RuntimeError(f"El layout con sesión no apareció en {timeout} ms (URL: {page.url})")
