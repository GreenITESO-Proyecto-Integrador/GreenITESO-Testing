"""Acciones de UI reutilizables entre módulos y equipos (navegar, login, clicks robustos, etc.).

Si una función solo la usa un módulo, va como función privada (_nombre) en su *_actions.py.
"""

from playwright.sync_api import Page

from src.configs import environment as env
from src.utils.logger import get_logger

logger = get_logger(__name__)


def go_to(page: Page, path: str = "/") -> None:
    """Navigate to `path` relative to BASE_URL and wait for the page to settle."""
    url = env.BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    logger.info("Navegando a %s", url)
    page.goto(url, wait_until="domcontentloaded")


def click_when_visible(page: Page, selector: str, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Wait for the first match of `selector` to be visible and click it."""
    target = page.locator(selector).first
    target.wait_for(state="visible", timeout=timeout)
    target.scroll_into_view_if_needed()
    target.click()
