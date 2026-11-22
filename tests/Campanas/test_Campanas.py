import allure
import pytest

from src.actions import Campanas_actions as actions
from src.utils.helpers import assert_action

# El setup (_000) crea el clan, la inscripción de S y la campaña A. Los números coinciden con los TC del test plan.


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_000_checkSetupCampaigns")
@allure.description("Campañas: Setup vía API (clan público del líder, S se une, campaña A privada para mañana)")
def test_00_04_000_checkSetupCampaigns(page):
    assert_action(actions.test_00_04_000_checkSetupCampaigns, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_001_checkListAndDetail", depends=["test_00_04_000_checkSetupCampaigns"])
@allure.description("Campañas: S ve la tarjeta de la campaña de clan y su detalle (fechas, participantes, misiones)")
def test_00_04_001_checkListAndDetail(page):
    assert_action(actions.test_00_04_001_checkListAndDetail, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_002_checkStatusAndScopeFilters", depends=["test_00_04_000_checkSetupCampaigns"]
)
@allure.description("Campañas: Los filtros de estado y alcance mandan query params y muestran la campaña correcta")
def test_00_04_002_checkStatusAndScopeFilters(page):
    assert_action(actions.test_00_04_002_checkStatusAndScopeFilters, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_003_checkJoinPromotionCampaign", depends=["test_00_04_000_checkSetupCampaigns"]
)
@allure.description("Campañas: S se une a una campaña en promoción y la API lo confirma")
def test_00_04_003_checkJoinPromotionCampaign(page):
    assert_action(actions.test_00_04_003_checkJoinPromotionCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_004_checkProposeGlobalCampaign")
@allure.description("Campañas: S propone una campaña global y queda como propuesta pendiente")
def test_00_04_004_checkProposeGlobalCampaign(page):
    assert_action(actions.test_00_04_004_checkProposeGlobalCampaign, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_005_checkRequiredFields")
@allure.description("Campañas: El formulario de propuesta marca los campos obligatorios y no envía nada")
def test_00_04_005_checkRequiredFields(page):
    assert_action(actions.test_00_04_005_checkRequiredFields, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_006_checkLeaderCreatesClanCampaign", depends=["test_00_04_000_checkSetupCampaigns"]
)
@allure.description("Campañas: El líder crea una campaña privada para su clan")
def test_00_04_006_checkLeaderCreatesClanCampaign(page):
    assert_action(actions.test_00_04_006_checkLeaderCreatesClanCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_007_checkNonLeaderCannotCreateClanCampaign", depends=["test_00_04_000_checkSetupCampaigns"]
)
@allure.description("Campañas: Un miembro que no lidera el clan no puede crear campañas de clan (403)")
def test_00_04_007_checkNonLeaderCannotCreateClanCampaign(page):
    assert_action(actions.test_00_04_007_checkNonLeaderCannotCreateClanCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_008_checkAdminCreatesGlobalCampaign")
@allure.description("Campañas: El admin crea una campaña global (POST interceptado, nada real se crea)")
def test_00_04_008_checkAdminCreatesGlobalCampaign(page):
    assert_action(actions.test_00_04_008_checkAdminCreatesGlobalCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_009_checkEditPromotionCampaignAndAddMission",
    depends=["test_00_04_006_checkLeaderCreatesClanCampaign"],
)
@allure.description("Campañas: El líder edita una campaña en promoción y le agrega una misión")
def test_00_04_009_checkEditPromotionCampaignAndAddMission(page):
    assert_action(actions.test_00_04_009_checkEditPromotionCampaignAndAddMission, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_010_checkEditBlockedOutsidePromotion", depends=["test_00_04_000_checkSetupCampaigns"]
)
@allure.description("Campañas: Una campaña ya activa no ofrece editar ni agregar misiones")
def test_00_04_010_checkEditBlockedOutsidePromotion(page):
    assert_action(actions.test_00_04_010_checkEditBlockedOutsidePromotion, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_011_checkAdminCannotJoin", depends=["test_00_04_000_checkSetupCampaigns"])
@allure.description("Campañas: El admin ve la campaña de clan pero no puede unirse")
def test_00_04_011_checkAdminCannotJoin(page):
    assert_action(actions.test_00_04_011_checkAdminCannotJoin, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_012_checkListErrorAndRetry", depends=["test_00_04_000_checkSetupCampaigns"])
@allure.description("Campañas: Error al cargar la lista, luego 'Reintentar' carga las campañas")
def test_00_04_012_checkListErrorAndRetry(page):
    assert_action(actions.test_00_04_012_checkListErrorAndRetry, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_013_checkStartPromotionCampaign",
    depends=["test_00_04_006_checkLeaderCreatesClanCampaign", "test_00_04_009_checkEditPromotionCampaignAndAddMission"],
)
@allure.description("Campañas: El líder inicia una campaña en promoción (confirmación y estado Activa)")
def test_00_04_013_checkStartPromotionCampaign(page):
    assert_action(actions.test_00_04_013_checkStartPromotionCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_04_014_checkFinishActiveCampaign", depends=["test_00_04_013_checkStartPromotionCampaign"]
)
@allure.description("Campañas: El líder finaliza una campaña activa (confirmación y estado Finalizada)")
def test_00_04_014_checkFinishActiveCampaign(page):
    assert_action(actions.test_00_04_014_checkFinishActiveCampaign, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_04_015_checkCancelStart", depends=["test_00_04_000_checkSetupCampaigns"])
@allure.description("Campañas: Cancelar el inicio de una campaña la deja en promoción")
def test_00_04_015_checkCancelStart(page):
    assert_action(actions.test_00_04_015_checkCancelStart, page)
