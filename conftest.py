"""Fixtures globales de pytest + Playwright."""

import time

import allure
import pytest
from playwright.sync_api import Page

from src.configs import environment as env
from src.utils import test_data
from src.utils.logger import get_logger, setup_file_logging

logger = get_logger(__name__)

_RUN_ID_KEY = "e2e_run_id"
_STARTED_AT = pytest.StashKey[float]()


def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def _cleanup_enabled(config: pytest.Config) -> bool:
    return env.E2E_CLEANUP and not config.option.collectonly and not config.option.help


class _XdistRunId:
    """Hand the controller's run marker to every xdist worker (only registered if xdist is active)."""

    def pytest_configure_node(self, node) -> None:
        node.workerinput[_RUN_ID_KEY] = test_data.run_id()


def pytest_configure(config: pytest.Config) -> None:
    setup_file_logging()
    env.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Un solo marcador de datos de prueba por corrida, igual en el controlador y en los workers.
    if _is_xdist_worker(config):
        test_data.set_run_id(config.workerinput[_RUN_ID_KEY])
        return
    test_data.set_run_id(test_data.new_run_id())
    if config.pluginmanager.hasplugin("xdist"):
        config.pluginmanager.register(_XdistRunId(), "e2e-xdist-run-id")
    config.stash[_STARTED_AT] = time.time()
    logger.info("Marcador de datos de prueba: %s", test_data.run_id())
    if _cleanup_enabled(config):
        # Antes de que arranquen los workers: guarda los perfiles y limpia corridas viejas.
        test_data.prepare_run()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if _is_xdist_worker(config) or not _cleanup_enabled(config):
        return
    summary = test_data.cleanup_run(test_data.run_id(), started_at=config.stash[_STARTED_AT])
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"Limpieza E2E ({summary['marker']}): {summary['done'] or 'nada que limpiar'}")
        for failure in summary["failed"]:
            reporter.write_line(f"  no se pudo {failure}", yellow=True)


# --- Configuración de pytest-playwright (browser, headless, base_url) ---

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # .env da los defaults; --headed / --slowmo en la línea de comandos tienen prioridad.
    return {"headless": env.HEADLESS, "slow_mo": env.SLOW_MO, **browser_type_launch_args}


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
