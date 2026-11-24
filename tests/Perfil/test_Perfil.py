import allure
import pytest

from src.actions import Perfil_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_13_001_checkProfileMetrics")
@allure.description("Perfil: Muestra el perfil del usuario con métricas de impacto ambiental y progreso")
def test_00_13_001_checkProfileMetrics(page):
    assert_action(actions.test_00_13_001_checkProfileMetrics, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_13_004_checkProfileAvatar")
@allure.description("Perfil: Muestra el avatar y permite abrir el diálogo de edición con opciones de foto")
def test_00_13_004_checkProfileAvatar(page):
    assert_action(actions.test_00_13_004_checkProfileAvatar, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_13_011_checkChangeNickname")
@allure.description("Perfil: Valida y gestiona el nickname del usuario respetando el límite de 50 caracteres")
def test_00_13_011_checkChangeNickname(page):
    assert_action(actions.test_00_13_011_checkChangeNickname, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_13_013_checkDeactivateAccount")
@allure.description("Perfil: Una cuenta desactivada o deshabilitada es bloqueada y no puede acceder al perfil")
def test_00_13_013_checkDeactivateAccount(page):
    assert_action(actions.test_00_13_013_checkDeactivateAccount, page)
