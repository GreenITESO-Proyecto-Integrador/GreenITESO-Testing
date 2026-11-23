import allure
import pytest

from src.actions import Notificaciones_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_001_checkNotificationsList")
@allure.description(
    "Notificaciones: La lista muestra las notificaciones de prueba y el contador de no leídas coincide con la UI"
)
def test_00_10_001_checkNotificationsList(page):
    assert_action(actions.test_00_10_001_checkNotificationsList, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_002_checkMarkAsRead", depends=["test_00_10_001_checkNotificationsList"])
@allure.description("Notificaciones: Marcar una notificación como leída baja el contador y se guarda en la API")
def test_00_10_002_checkMarkAsRead(page):
    assert_action(actions.test_00_10_002_checkMarkAsRead, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_003_checkMarkAllAsRead", depends=["test_00_10_001_checkNotificationsList"])
@allure.description("Notificaciones: 'Marcar todo' deja la lista al día y el contador de la API en cero")
def test_00_10_003_checkMarkAllAsRead(page):
    assert_action(actions.test_00_10_003_checkMarkAllAsRead, page)


@pytest.mark.full
@pytest.mark.dependency(
    name="test_00_10_004_checkDeleteNotification", depends=["test_00_10_001_checkNotificationsList"]
)
@allure.description("Notificaciones: Eliminar una notificación la quita de la lista y no regresa al recargar")
def test_00_10_004_checkDeleteNotification(page):
    assert_action(actions.test_00_10_004_checkDeleteNotification, page)


@pytest.mark.full
@pytest.mark.flaky(reruns=1)
@pytest.mark.dependency(name="test_00_10_005_checkRealtimeNotification")
@allure.description("Notificaciones: Una notificación nueva llega por el socket con aviso y aparece sin recargar")
def test_00_10_005_checkRealtimeNotification(page):
    assert_action(actions.test_00_10_005_checkRealtimeNotification, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_006_checkEmptyState")
@allure.description("Notificaciones: Sin notificaciones se muestra el estado vacío y 'Estás al día.'")
def test_00_10_006_checkEmptyState(page):
    assert_action(actions.test_00_10_006_checkEmptyState, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_007_checkLoadError")
@allure.description("Notificaciones: Si falla la carga se muestra el aviso de error")
def test_00_10_007_checkLoadError(page):
    assert_action(actions.test_00_10_007_checkLoadError, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_008_checkBadgeCelebration")
@allure.description(
    "Notificaciones: Una insignia nueva muestra la celebración, la cola y lleva al perfil marcándola como leída"
)
def test_00_10_008_checkBadgeCelebration(page):
    assert_action(actions.test_00_10_008_checkBadgeCelebration, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_10_009_checkCannotTouchOthersNotification")
@allure.description(
    "Notificaciones: Otro usuario no puede ver, marcar ni borrar una notificación de S (404) y S la conserva sin leer"
)
def test_00_10_009_checkCannotTouchOthersNotification(page):
    assert_action(actions.test_00_10_009_checkCannotTouchOthersNotification, page)
