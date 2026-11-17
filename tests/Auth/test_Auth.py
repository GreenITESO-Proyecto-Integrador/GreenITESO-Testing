import allure
import pytest

from src.actions import Auth_actions as actions
from src.utils.helpers import assert_action

# TC-01-002 y TC-01-003 (login real con Microsoft) son manuales y no se declaran aquí.


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_001_checkLoginScreen")
@allure.description("Auth: La pantalla de login muestra el título, el botón de Microsoft habilitado y el aviso institucional")
def test_00_01_001_checkLoginScreen(page):
    assert_action(actions.test_00_01_001_checkLoginScreen, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_004_checkProtectedRouteRedirect")
@allure.description("Auth: Sin sesión, /profile, /campaigns y /store redirigen a /login")
def test_00_01_004_checkProtectedRouteRedirect(page):
    assert_action(actions.test_00_01_004_checkProtectedRouteRedirect, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_005_checkAuditBlockedForStudent")
@allure.description("Auth: Un usuario no admin ve 'Acceso Restringido' (403) en /audit")
def test_00_01_005_checkAuditBlockedForStudent(page):
    assert_action(actions.test_00_01_005_checkAuditBlockedForStudent, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_006_checkLogout")
@allure.description("Auth: Cerrar sesión manda a /login y la sesión no regresa al abrir una ruta protegida")
def test_00_01_006_checkLogout(page):
    assert_action(actions.test_00_01_006_checkLogout, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_007_checkSessionPersistsOnReload")
@allure.description("Auth: La sesión se mantiene al recargar /profile")
def test_00_01_007_checkSessionPersistsOnReload(page):
    assert_action(actions.test_00_01_007_checkSessionPersistsOnReload, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_008_checkUnknownRouteShowsDashboard")
@allure.description("Auth: Una ruta desconocida muestra el Dashboard dentro del layout")
def test_00_01_008_checkUnknownRouteShowsDashboard(page):
    assert_action(actions.test_00_01_008_checkUnknownRouteShowsDashboard, page)
