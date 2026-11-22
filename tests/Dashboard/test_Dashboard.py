import allure
import pytest

from src.actions import Dashboard_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_001_checkImpactMetrics")
@allure.description("Dashboard: Las 5 métricas de 'Tu impacto' muestran los valores de profile/me con formato es-MX")
def test_00_03_001_checkImpactMetrics(page):
    assert_action(actions.test_00_03_001_checkImpactMetrics, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_002_checkImpactTrend")
@allure.description("Dashboard: La tendencia de 4 semanas tiene 3 gráficas y los ejes X coinciden con week_start")
def test_00_03_002_checkImpactTrend(page):
    assert_action(actions.test_00_03_002_checkImpactTrend, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_003_checkActiveMissions")
@allure.description("Dashboard: Misiones activas muestra el progreso de cada misión de las campañas en curso")
def test_00_03_003_checkActiveMissions(page):
    assert_action(actions.test_00_03_003_checkActiveMissions, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_004_checkMyCampaignsFilter")
@allure.description(
    "Dashboard: Los filtros de estado y alcance de 'Mis campañas' muestran solo las campañas que coinciden"
)
def test_00_03_004_checkMyCampaignsFilter(page):
    assert_action(actions.test_00_03_004_checkMyCampaignsFilter, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_005_checkNewUserEmptyStates")
@allure.description("Dashboard: Un usuario nuevo ve los estados vacíos de campañas, misiones y tendencia en cero")
def test_00_03_005_checkNewUserEmptyStates(page):
    assert_action(actions.test_00_03_005_checkNewUserEmptyStates, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_006_checkAdminSimpleDashboard")
@allure.description("Dashboard: El admin ve el dashboard simple y no las secciones de impacto ni campañas")
def test_00_03_006_checkAdminSimpleDashboard(page):
    assert_action(actions.test_00_03_006_checkAdminSimpleDashboard, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_03_007_checkProfileLoadError")
@allure.description(
    "Dashboard: Si falla profile/me se muestra el error con 'Reintentar' y 'Tu impacto' carga al reintentar"
)
def test_00_03_007_checkProfileLoadError(page):
    assert_action(actions.test_00_03_007_checkProfileLoadError, page)
