import allure
import pytest

from src.actions import LoginInstitucionalFront_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_201_checkLoginPageIsClean")
@allure.description("Login front: /login no pide correo ni contraseña, no muestra errores ni llama al backend al abrir")
def test_00_01_201_checkLoginPageIsClean(page):
    assert_action(actions.test_00_01_201_checkLoginPageIsClean, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_202_checkMicrosoftRedirectTarget")
@allure.description("Login front: El botón manda a Microsoft con el client_id, regresa a /login y no lleva secretos")
def test_00_01_202_checkMicrosoftRedirectTarget(page):
    assert_action(actions.test_00_01_202_checkMicrosoftRedirectTarget, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_203_checkMicrosoftRedirectUsesPkce")
@allure.description("Login front: El salto a Microsoft usa código + PKCE (S256) y pide User.Read")
def test_00_01_203_checkMicrosoftRedirectUsesPkce(page):
    assert_action(actions.test_00_01_203_checkMicrosoftRedirectUsesPkce, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_204_checkSessionOnlyRoutesRedirect")
@allure.description("Login front: Sin sesión, /clans y /admin/users mandan a /login")
def test_00_01_204_checkSessionOnlyRoutesRedirect(page):
    assert_action(actions.test_00_01_204_checkSessionOnlyRoutesRedirect, page)
