"""Helpers genéricos: chequeos de estado (is_*/has_*), esperas (wait_for_*) y utilidades
que no realizan una acción de negocio. Son independientes de cualquier módulo.
"""

import time
from collections.abc import Callable

import allure
from playwright.sync_api import Locator, Page

from src.utils.logger import get_logger

logger = get_logger(__name__)


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
