import allure
import pytest

from src.actions import Catalogo_actions as actions
from src.utils.helpers import assert_action

# Los tests 002 a 008 mockean /api/v1/actions/ con page.route (ver el docstring de Catalogo_actions).


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_001_checkCatalogCards")
@allure.description("Catálogo: /actions muestra las tarjetas con nombre y puntos")
def test_01_05_001_checkCatalogCards(page):
    assert_action(actions.test_01_05_001_checkCatalogCards, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_002_checkNoImpactNotice")
@allure.description("Catálogo: Una acción sin impacto calibrado muestra el aviso")
def test_01_05_002_checkNoImpactNotice(page):
    assert_action(actions.test_01_05_002_checkNoImpactNotice, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_003_checkErrorAndRetry")
@allure.description("Catálogo: Si falla el catálogo se muestra el error y Reintentar lo recupera")
def test_01_05_003_checkErrorAndRetry(page):
    assert_action(actions.test_01_05_003_checkErrorAndRetry, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_004_checkLongDescriptionExpanded")
@allure.description("Catálogo: Una descripción larga se recorta y 'Ver más' la expande")
def test_01_05_004_checkLongDescriptionExpanded(page):
    assert_action(actions.test_01_05_004_checkLongDescriptionExpanded, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_005_checkCardDetails")
@allure.description("Catálogo: La tarjeta muestra puntos, límite, evidencia y factores de impacto")
def test_01_05_005_checkCardDetails(page):
    assert_action(actions.test_01_05_005_checkCardDetails, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_006_checkEmptyCatalog")
@allure.description("Catálogo: Un catálogo vacío muestra el estado vacío")
def test_01_05_006_checkEmptyCatalog(page):
    assert_action(actions.test_01_05_006_checkEmptyCatalog, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_007_checkInactiveActionsHidden")
@allure.description("Catálogo: Las acciones inactivas no se muestran")
def test_01_05_007_checkInactiveActionsHidden(page):
    assert_action(actions.test_01_05_007_checkInactiveActionsHidden, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_008_checkMalformedPayload")
@allure.description("Catálogo: Un payload sin acciones válidas se muestra como error")
def test_01_05_008_checkMalformedPayload(page):
    assert_action(actions.test_01_05_008_checkMalformedPayload, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_05_009_checkRequiresSession")
@allure.description("Catálogo: Sin sesión no se muestra el catálogo")
def test_01_05_009_checkRequiresSession(page):
    assert_action(actions.test_01_05_009_checkRequiresSession, page)
