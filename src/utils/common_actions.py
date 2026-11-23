"""Acciones de UI reutilizables entre módulos y equipos (navegar, login, clicks robustos, etc.).

Si una función solo la usa un módulo, va como función privada (_nombre) en su *_actions.py.
"""

import time

from playwright.sync_api import Dialog, Page

from src.configs import environment as env
from src.utils.auth import AuthUser, get_session, inject_session
from src.utils.helpers import locator_has_visible_match
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)


def login_as(page: Page, role: str = "student", *, email: str | None = None, skip_tour: bool = True) -> AuthUser:
    """Inject a real backend session for a test user before the page loads; call it before go_to."""
    target = email or env.TEST_USERS[role]
    session = get_session(page.request, target)
    inject_session(page, session, skip_tour=skip_tour)
    logger.info("Sesión inyectada para %s (rol %s)", target, session["user"]["role"])
    return session["user"]


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


def click_robust(page: Page, selector: str, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Click the first visible match of `selector`, retrying until `timeout`, then with force and JS."""
    target = page.locator(selector).first
    deadline = time.monotonic() + timeout / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            target.wait_for(state="visible", timeout=1_000)
            target.click(timeout=1_000)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            page.wait_for_timeout(150)
    try:
        logger.debug("click_robust: reintento con force=True en %s", selector)
        target.click(force=True, timeout=1_000)
        return
    except Exception as exc:  # noqa: BLE001
        last_error = exc
    logger.debug("click_robust: último recurso, click por JS en %s", selector)
    if target.count() and target.evaluate("el => { el.click(); return true; }"):
        return
    raise RuntimeError(f"No se pudo dar clic en {selector}") from last_error


def open_user_menu(page: Page, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Open the navbar user menu ("Menú de usuario")."""
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        click_robust(page, Locs.USER_MENU_BUTTON, timeout=timeout)
        if locator_has_visible_match(page.locator("//*[@role='menu']"), timeout=1_000):
            return
        logger.debug("open_user_menu: el menú no abrió, reintentando")
    raise RuntimeError("El menú de usuario no se abrió")


def logout(page: Page, *, timeout: int = env.DEFAULT_TIMEOUT) -> None:
    """Sign out through the user menu ("Cerrar sesión")."""
    open_user_menu(page, timeout=timeout)
    click_robust(page, Locs.menuitem_with_text("Cerrar sesión"), timeout=timeout)
    logger.info("Sesión cerrada desde el menú de usuario")


def accept_next_dialog(page: Page) -> list[str]:
    """Accept the next native dialog (confirm/alert); the returned list receives its message."""
    messages: list[str] = []

    def _accept(dialog: Dialog) -> None:
        messages.append(dialog.message)
        dialog.accept()

    page.once("dialog", _accept)
    return messages


def dismiss_next_dialog(page: Page) -> list[str]:
    """Dismiss (cancel) the next native dialog; the returned list receives its message."""
    messages: list[str] = []

    def _dismiss(dialog: Dialog) -> None:
        messages.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", _dismiss)
    return messages


def click_filter_chip(page: Page, group_label: str, chip_text: str, *, timeout: int = 5_000) -> None:
    """Click a filter chip inside the group `group_label` and wait until it reports aria-pressed=true."""
    chip = page.get_by_role("group", name=group_label, exact=True).get_by_role(
        "button", name=chip_text, exact=True
    )
    chip.first.wait_for(state="visible", timeout=timeout)
    chip.first.click()
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if chip.first.get_attribute("aria-pressed") == "true":
            logger.debug("Chip %r del grupo %r activo", chip_text, group_label)
            return
        page.wait_for_timeout(100)
    raise RuntimeError(f"El chip {chip_text!r} del grupo {group_label!r} no quedó activo")


def close_success_banner(page: Page, *, timeout: int = 5_000) -> None:
    """Close the success banner by its "Cerrar aviso" button."""
    click_robust(page, Locs.button_with_aria("Cerrar aviso"), timeout=timeout)
    logger.debug("Aviso de éxito cerrado")
