import allure
import pytest

from src.actions import Leaderboard_actions as actions
from src.utils.helpers import assert_action

# Los tests 005 a 008 mockean /api/v1/rankings/ con page.route (ver el docstring de Leaderboard_actions).


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_001_checkSetUp")
@allure.description("Leaderboard: /leaderboard muestra el título y las tres pestañas, con 'Clasificación Global' activa")
def test_01_12_001_checkSetUp(page):
    assert_action(actions.test_01_12_001_checkSetUp, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_002_checkDefaultGlobalRanking", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard: La clasificación global muestra Pos./Participante/Puntos con posiciones ascendentes")
def test_01_12_002_checkDefaultGlobalRanking(page):
    assert_action(actions.test_01_12_002_checkDefaultGlobalRanking, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_003_checkInstitutionalRanking", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard: La pestaña 'Ranking institucional' pide type=INSTITUTIONAL y muestra la columna Equipo")
def test_01_12_003_checkInstitutionalRanking(page):
    assert_action(actions.test_01_12_003_checkInstitutionalRanking, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_004_checkPrivateClanRanking", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard: La pestaña 'Clanes privados' pide type=PRIVATE_CLAN y muestra la columna Equipo")
def test_01_12_004_checkPrivateClanRanking(page):
    assert_action(actions.test_01_12_004_checkPrivateClanRanking, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_005_checkPagination", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard (API mockeada): 120 filas se paginan en 50/50/20 y cambiar de pestaña regresa a la página 1")
def test_01_12_005_checkPagination(page):
    assert_action(actions.test_01_12_005_checkPagination, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_006_checkPrivateUsersNotListed", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard (API mockeada): La tabla muestra solo los usuarios que devuelve la API")
def test_01_12_006_checkPrivateUsersNotListed(page):
    assert_action(actions.test_01_12_006_checkPrivateUsersNotListed, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_007_checkEmptyState", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard (API mockeada): Sin resultados muestra 'Aún no hay clasificación' sin tabla ni paginador")
def test_01_12_007_checkEmptyState(page):
    assert_action(actions.test_01_12_007_checkEmptyState, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_01_12_008_checkErrorStateAndRetry", depends=["test_01_12_001_checkSetUp"])
@allure.description("Leaderboard (API mockeada): Un 500 muestra el error con 'Reintentar' y al recuperarse aparece la tabla")
def test_01_12_008_checkErrorStateAndRetry(page):
    assert_action(actions.test_01_12_008_checkErrorStateAndRetry, page)
