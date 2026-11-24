import allure
import pytest

from src.actions import LoginInstitucionalBack_actions as actions
from src.configs import environment as env
from src.utils.helpers import assert_action

# Usan el proveedor mock del backend (mock:<correo>), que solo existe en el stack local o el de CI.
pytestmark = pytest.mark.skipif(env.AUTH_MODE != "mock", reason="requiere AUTH_MODE=mock (backend con login mock)")


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_101_checkFirstLoginCreatesUser")
@allure.description("Login back: El primer login crea la cuenta como STUDENT y regresa access y refresh")
def test_00_01_101_checkFirstLoginCreatesUser(page):
    assert_action(actions.test_00_01_101_checkFirstLoginCreatesUser, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_102_checkSecondLoginReusesUser")
@allure.description("Login back: El segundo login (aun con el correo en mayúsculas) reusa la misma cuenta")
def test_00_01_102_checkSecondLoginReusesUser(page):
    assert_action(actions.test_00_01_102_checkSecondLoginReusesUser, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_103_checkOtherDomainsRejected")
@allure.description("Login back: Correos fuera de @iteso.mx (otro dominio o subdominio) dan 403 DOMAIN_NOT_ALLOWED")
def test_00_01_103_checkOtherDomainsRejected(page):
    assert_action(actions.test_00_01_103_checkOtherDomainsRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_104_checkInvalidRequestsRejected")
@allure.description("Login back: Un id_token demasiado largo da 400 y uno inválido da 401")
def test_00_01_104_checkInvalidRequestsRejected(page):
    assert_action(actions.test_00_01_104_checkInvalidRequestsRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_105_checkDirectoryDataApplied")
@allure.description("Login back: Copia los nombres del directorio, un 'Profesor' es STAFF y no baja sin puesto")
def test_00_01_105_checkDirectoryDataApplied(page):
    assert_action(actions.test_00_01_105_checkDirectoryDataApplied, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_106_checkAdminNeverDemoted")
@allure.description("Login back: El login nunca le quita el rol ADMIN a una cuenta")
def test_00_01_106_checkAdminNeverDemoted(page):
    assert_action(actions.test_00_01_106_checkAdminNeverDemoted, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_01_107_checkSelfDeactivatedAccountReactivates")
@allure.description("Login back: Una cuenta que se desactivó sola se reactiva al volver a entrar")
def test_00_01_107_checkSelfDeactivatedAccountReactivates(page):
    assert_action(actions.test_00_01_107_checkSelfDeactivatedAccountReactivates, page)


# --- Hallazgos: afirman el comportamiento correcto y hoy fallan (xfail estricto). Cuando se
# arregle el problema el test pasa, pytest lo marca como XPASS(strict) y hay que quitar el xfail.

@pytest.mark.full
@pytest.mark.xfail(strict=True, reason="Hallazgo 1 (alta): el login recalcula el rol y pisa el que puso el admin")
@pytest.mark.dependency(name="test_00_01_151_checkAdminAssignedRoleSurvivesLogin")
@allure.description("Login back (hallazgo): El rol STAFF que asignó un admin sobrevive al siguiente login")
def test_00_01_151_checkAdminAssignedRoleSurvivesLogin(page):
    assert_action(actions.test_00_01_151_checkAdminAssignedRoleSurvivesLogin, page)


@pytest.mark.full
@pytest.mark.xfail(strict=True, reason="Hallazgo 2 (media): la regla de rol busca 'Profesor' dentro del puesto")
@pytest.mark.dependency(name="test_00_01_152_checkStudentAssistantIsStudent")
@allure.description("Login back (hallazgo): 'Alumno Asistente de Profesor' queda como STUDENT")
def test_00_01_152_checkStudentAssistantIsStudent(page):
    assert_action(actions.test_00_01_152_checkStudentAssistantIsStudent, page)


@pytest.mark.full
@pytest.mark.xfail(strict=True, reason="Hallazgo 5 (baja): el filtro de dominio solo revisa la última @")
@pytest.mark.dependency(name="test_00_01_153_checkEmailWithTwoAtSignsRejected")
@allure.description("Login back (hallazgo): Un correo con dos @ ('a@gmail.com@iteso.mx') se rechaza")
def test_00_01_153_checkEmailWithTwoAtSignsRejected(page):
    assert_action(actions.test_00_01_153_checkEmailWithTwoAtSignsRejected, page)
