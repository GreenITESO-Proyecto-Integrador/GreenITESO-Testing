"""Fixtures globales de pytest + Playwright."""

import allure
import pytest
from playwright.sync_api import Page

from src.configs import environment as env
from src.utils.logger import get_logger, setup_file_logging

logger = get_logger(__name__)


def pytest_configure(config: pytest.Config) -> None:
    setup_file_logging()
    env.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# --- Configuración de pytest-playwright (browser, headless, base_url) ---

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, "headless": env.HEADLESS, "slow_mo": env.SLOW_MO}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "base_url": env.BASE_URL, "viewport": {"width": 1440, "height": 900}}


@pytest.fixture
def page(page: Page) -> Page:
    page.set_default_timeout(env.DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(env.NAVIGATION_TIMEOUT)
    return page


# --- Screenshot + adjunto en Allure cuando falla un test ---

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    page = item.funcargs.get("page")
    if page is None:
        return
    try:
        path = env.SCREENSHOTS_DIR / f"{item.name}.png"
        page.screenshot(path=str(path), full_page=True)
        allure.attach.file(str(path), name=item.name, attachment_type=allure.attachment_type.PNG)
        logger.error("Test %s falló; screenshot en %s", item.name, path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo tomar screenshot de %s: %s", item.name, exc)
