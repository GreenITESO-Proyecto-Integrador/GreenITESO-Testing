import allure
import pytest

from src.actions import Clanes_actions as actions
from src.utils.helpers import assert_action

# Solo se prueba la creación de clanes (TC-11-002 y TC-11-003). Cada test que crea un clan lo disuelve
# al terminar, porque un usuario solo puede liderar uno a la vez (BR-04).


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_001_checkSetUp")
@allure.description("Clanes: Desde /clans se abre el diálogo 'Crear clan' con nombre, descripción, privacidad (Pública por defecto) y botones")
def test_00_11_001_checkSetUp(page):
    assert_action(actions.test_00_11_001_checkSetUp, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_002_checkCreatePublicClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Crear un clan público lleva a su perfil con aviso de éxito, 1 miembro y acciones de líder")
def test_00_11_002_checkCreatePublicClan(page):
    assert_action(actions.test_00_11_002_checkCreatePublicClan, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_003_checkCreatePrivateInviteClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Crear un clan 'Solo invitación' muestra su insignia y el botón 'Invitar con código' al líder")
def test_00_11_003_checkCreatePrivateInviteClan(page):
    assert_action(actions.test_00_11_003_checkCreatePrivateInviteClan, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_004_checkCreateClanWithoutDescription", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: La descripción es opcional; se crea el clan solo con nombre")
def test_00_11_004_checkCreateClanWithoutDescription(page):
    assert_action(actions.test_00_11_004_checkCreateClanWithoutDescription, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_005_checkCreatedClanListedInDirectory", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El clan creado aparece en 'Explorar clanes' al buscarlo por nombre")
def test_00_11_005_checkCreatedClanListedInDirectory(page):
    assert_action(actions.test_00_11_005_checkCreatedClanListedInDirectory, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_006_checkNameRequired", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un nombre vacío o de solo espacios muestra 'Escribe un nombre para el clan.' y no crea nada")
def test_00_11_006_checkNameRequired(page):
    assert_action(actions.test_00_11_006_checkNameRequired, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_007_checkFieldLengthLimits", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El nombre admite 50 caracteres y la descripción 100, con su contador")
def test_00_11_007_checkFieldLengthLimits(page):
    assert_action(actions.test_00_11_007_checkFieldLengthLimits, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_008_checkDuplicateNameRejected", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un nombre de clan ya usado es rechazado con 'Ya existe un clan con ese nombre'")
def test_00_11_008_checkDuplicateNameRejected(page):
    assert_action(actions.test_00_11_008_checkDuplicateNameRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_009_checkReservedCareerNameRejected", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El nombre de un clan de carrera es rechazado al crear un clan")
def test_00_11_009_checkReservedCareerNameRejected(page):
    assert_action(actions.test_00_11_009_checkReservedCareerNameRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_010_checkSecondLeadershipRejected", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Quien ya lidera un clan no puede crear otro (BR-04)")
def test_00_11_010_checkSecondLeadershipRejected(page):
    assert_action(actions.test_00_11_010_checkSecondLeadershipRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_011_checkCancelDoesNotCreateClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Cancelar el diálogo cierra el formulario y no crea el clan")
def test_00_11_011_checkCancelDoesNotCreateClan(page):
    assert_action(actions.test_00_11_011_checkCancelDoesNotCreateClan, page)
