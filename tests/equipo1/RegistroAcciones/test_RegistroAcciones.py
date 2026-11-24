import allure
import pytest

from src.actions import RegistroAcciones_actions as actions
from src.utils.helpers import assert_action

# 001, 002 y 006 registran de verdad y gastan cupo diario: sin reintento (Jenkins usa --reruns 1), porque
# el reintento crearía registros extra y, en 002, taparía el error original con un BLOQUEADO por cupo.


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.flaky(reruns=0)
@pytest.mark.dependency(name="test_01_06_001_checkRegisterWithoutEvidence")
@allure.description("Registro de acciones: Registrar una acción sin evidencia la aprueba y suma sus puntos")
def test_01_06_001_checkRegisterWithoutEvidence(page):
    assert_action(actions.test_01_06_001_checkRegisterWithoutEvidence, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.flaky(reruns=0)
@pytest.mark.dependency(name="test_01_06_002_checkRegisterWithPhotoPendingAudit")
@allure.description("Registro de acciones: Registrar una acción con foto la deja pendiente de auditoría sin sumar puntos")
def test_01_06_002_checkRegisterWithPhotoPendingAudit(page):
    assert_action(actions.test_01_06_002_checkRegisterWithPhotoPendingAudit, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_06_003_checkActionRequired")
@allure.description("Registro de acciones: Registrar sin elegir una acción muestra el error y no envía nada")
def test_01_06_003_checkActionRequired(page):
    assert_action(actions.test_01_06_003_checkActionRequired, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_06_004_checkPhotoRequired")
@allure.description("Registro de acciones: Una acción con foto pide la evidencia antes de registrar")
def test_01_06_004_checkPhotoRequired(page):
    assert_action(actions.test_01_06_004_checkPhotoRequired, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_06_005_checkPhotoOverSizeLimit")
@allure.description("Registro de acciones: Una foto de más de 5 MB muestra el error de tamaño y no se envía")
def test_01_06_005_checkPhotoOverSizeLimit(page):
    assert_action(actions.test_01_06_005_checkPhotoOverSizeLimit, page)


@pytest.mark.full
@pytest.mark.flaky(reruns=0)
@pytest.mark.dependency(
    name="test_01_06_006_checkDailyLimitMessage", depends=["test_01_06_001_checkRegisterWithoutEvidence"]
)
@allure.description("Registro de acciones: Al llegar al límite diario se muestra el mensaje y los puntos no cambian")
def test_01_06_006_checkDailyLimitMessage(page):
    assert_action(actions.test_01_06_006_checkDailyLimitMessage, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_06_007_checkPreselectFromUrl")
@allure.description("Registro de acciones: El parámetro ?action= (código o id) preselecciona la acción")
def test_01_06_007_checkPreselectFromUrl(page):
    assert_action(actions.test_01_06_007_checkPreselectFromUrl, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_06_008_checkClearForm")
@allure.description("Registro de acciones: 'Limpiar' regresa el selector al inicio y quita la imagen")
def test_01_06_008_checkClearForm(page):
    assert_action(actions.test_01_06_008_checkClearForm, page)
