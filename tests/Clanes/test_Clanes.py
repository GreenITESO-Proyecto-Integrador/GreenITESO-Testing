import allure
import pytest

from src.actions import Clanes_actions as actions
from src.utils.helpers import assert_action

# 001–011: crear un clan (TC-11-002 y TC-11-003).
# 012–025: buscar, perfil, unirse, salir, clan activo, enlace, solicitudes, disolver,
# transferir, error de la lista y campañas (TC-11-001 y TC-11-004 a TC-11-016).
# Cada test que crea un clan lo disuelve al terminar (BR-04: un usuario lidera uno a la vez).


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
@allure.description("Clanes: Un nombre de clan ya usado es rechazado con 'No repitas la misma acción en una campaña.'")
def test_00_11_008_checkDuplicateNameRejected(page):
    assert_action(actions.test_00_11_008_checkDuplicateNameRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_009_checkReservedCareerNameRejected", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El nombre de un clan de carrera es rechazado con 'No repitas la misma acción en una campaña.'")
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


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_012_checkSearchClansByName", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El clan creado aparece en Explorar clanes al pasar de página")
def test_00_11_012_checkSearchClansByName(page):
    assert_action(actions.test_00_11_012_checkSearchClansByName, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_013_checkOpenClanProfile", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Abrir la tarjeta muestra nombre, descripción, privacidad y un miembro")
def test_00_11_013_checkOpenClanProfile(page):
    assert_action(actions.test_00_11_013_checkOpenClanProfile, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_014_checkJoinPublicClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un estudiante se une a un clan público y el clan queda con 2 miembros")
def test_00_11_014_checkJoinPublicClan(page):
    assert_action(actions.test_00_11_014_checkJoinPublicClan, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_015_checkLeaveClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un miembro confirma salir y vuelve al directorio")
def test_00_11_015_checkLeaveClan(page):
    assert_action(actions.test_00_11_015_checkLeaveClan, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_016_checkSetActiveClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un miembro establece el clan como activo")
def test_00_11_016_checkSetActiveClan(page):
    assert_action(actions.test_00_11_016_checkSetActiveClan, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_017_checkCopyInviteLink", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Copiar el enlace de invitación de un clan público avisa que se copió")
def test_00_11_017_checkCopyInviteLink(page):
    assert_action(actions.test_00_11_017_checkCopyInviteLink, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_018_checkRequestJoinByInviteLink", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El enlace de un clan solo por invitación permite solicitar unirse")
def test_00_11_018_checkRequestJoinByInviteLink(page):
    assert_action(actions.test_00_11_018_checkRequestJoinByInviteLink, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_019_checkAcceptJoinRequest", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El líder acepta una solicitud y el clan queda con 2 miembros")
def test_00_11_019_checkAcceptJoinRequest(page):
    assert_action(actions.test_00_11_019_checkAcceptJoinRequest, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_020_checkRejectJoinRequest", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El líder rechaza una solicitud y la lista queda vacía")
def test_00_11_020_checkRejectJoinRequest(page):
    assert_action(actions.test_00_11_020_checkRejectJoinRequest, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_021_checkInvalidInviteRejected", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un enlace inexistente y un código mal formado son rechazados")
def test_00_11_021_checkInvalidInviteRejected(page):
    assert_action(actions.test_00_11_021_checkInvalidInviteRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_022_checkDissolveClan", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El líder disuelve el clan y su perfil ya no existe")
def test_00_11_022_checkDissolveClan(page):
    assert_action(actions.test_00_11_022_checkDissolveClan, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_023_checkTransferLeadership", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: El líder transfiere el liderazgo y deja de poder disolver el clan")
def test_00_11_023_checkTransferLeadership(page):
    assert_action(actions.test_00_11_023_checkTransferLeadership, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_024_checkClanListErrorAndRetry", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Si la lista falla, Reintentar vuelve a cargarla")
def test_00_11_024_checkClanListErrorAndRetry(page):
    assert_action(actions.test_00_11_024_checkClanListErrorAndRetry, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_11_025_checkClanActiveCampaigns", depends=["test_00_11_001_checkSetUp"])
@allure.description("Clanes: Un miembro ve la sección de campañas activas, vacía si no hay ninguna")
def test_00_11_025_checkClanActiveCampaigns(page):
    assert_action(actions.test_00_11_025_checkClanActiveCampaigns, page)
