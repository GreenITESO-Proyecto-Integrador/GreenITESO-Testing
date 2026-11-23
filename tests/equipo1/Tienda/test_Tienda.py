import allure
import pytest

from src.actions import Tienda_actions as actions
from src.utils.helpers import assert_action

# Usuario propio del módulo (TEST_STORE_EMAIL). 003 canjea de verdad y no se puede deshacer: solo full.
# 004, 005 (si el saldo real no alcanza), 006 y 010 usan mocks de red (ver el docstring de Tienda_actions).


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_001_checkBalanceAndCatalog")
@allure.description(
    "Tienda: El saldo coincide con la API y cada tarjeta muestra categoría, costo y si ya es del usuario"
)
def test_01_08_001_checkBalanceAndCatalog(page):
    assert_action(actions.test_01_08_001_checkBalanceAndCatalog, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_002_checkCategoryFilter", depends=["test_01_08_001_checkBalanceAndCatalog"])
@allure.description("Tienda: Los chips Marcos/Fondos/Otros/Todos filtran el catálogo y solo uno queda activo")
def test_01_08_002_checkCategoryFilter(page):
    assert_action(actions.test_01_08_002_checkCategoryFilter, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_003_checkRedeemWithEnoughPoints")
@allure.description(
    "Tienda: Canjear con saldo suficiente descuenta los puntos y marca 'Canjeado', también tras recargar"
)
def test_01_08_003_checkRedeemWithEnoughPoints(page):
    assert_action(actions.test_01_08_003_checkRedeemWithEnoughPoints, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_004_checkInsufficientPointsBlocked")
@allure.description("Tienda: Sin puntos suficientes se avisa 'Puntos insuficientes' y no se abre ni se manda el canje")
def test_01_08_004_checkInsufficientPointsBlocked(page):
    assert_action(actions.test_01_08_004_checkInsufficientPointsBlocked, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_005_checkCancelRedeem")
@allure.description("Tienda: 'Cancelar' cierra la confirmación sin canjear ni cambiar el saldo")
def test_01_08_005_checkCancelRedeem(page):
    assert_action(actions.test_01_08_005_checkCancelRedeem, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_006_checkCatalogErrorAndRetry")
@allure.description("Tienda: Si falla el catálogo se muestra el error y 'Reintentar' lo vuelve a cargar")
def test_01_08_006_checkCatalogErrorAndRetry(page):
    assert_action(actions.test_01_08_006_checkCatalogErrorAndRetry, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_007_checkShopRoute")
@allure.description("Tienda: La ruta /shop abre la tienda con su saldo y catálogo")
def test_01_08_007_checkShopRoute(page):
    assert_action(actions.test_01_08_007_checkShopRoute, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_01_08_008_checkDuplicateRedeemRejected", depends=["test_01_08_003_checkRedeemWithEnoughPoints"]
)
@allure.description("Tienda: Un artículo ya canjeado queda deshabilitado y la API rechaza canjearlo otra vez")
def test_01_08_008_checkDuplicateRedeemRejected(page):
    assert_action(actions.test_01_08_008_checkDuplicateRedeemRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_009_checkApiRejectsInsufficientPoints")
@allure.description("Tienda: La API rechaza un canje sin saldo suficiente sin tocar saldo ni inventario")
def test_01_08_009_checkApiRejectsInsufficientPoints(page):
    assert_action(actions.test_01_08_009_checkApiRejectsInsufficientPoints, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_08_010_checkEmptyCatalog")
@allure.description("Tienda: Con el catálogo vacío se muestra 'No hay canjeables disponibles' sin filtros")
def test_01_08_010_checkEmptyCatalog(page):
    assert_action(actions.test_01_08_010_checkEmptyCatalog, page)
