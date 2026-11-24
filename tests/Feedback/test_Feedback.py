import allure
import pytest

from src.actions import Feedback_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_000_checkSetUp")
@allure.description("Feedback: Preparar las sesiones y los asuntos marcados del módulo")
def test_00_16_000_checkSetUp(page):
    assert_action(actions.test_00_16_000_checkSetUp, page)


# --- Formulario (sin enviar nada) ---

@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_001_checkOpenFeedbackPage")
@allure.description("Feedback: /feedback muestra el formulario, el historial y el envío deshabilitado")
def test_00_16_001_checkOpenFeedbackPage(page):
    assert_action(actions.test_00_16_001_checkOpenFeedbackPage, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_002_checkSubmitDisabledUntilValid")
@allure.description("Feedback: El envío se habilita solo con asunto de 1-120 y mensaje de 10-1000 caracteres")
def test_00_16_002_checkSubmitDisabledUntilValid(page):
    assert_action(actions.test_00_16_002_checkSubmitDisabledUntilValid, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_003_checkClearForm", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: 'Limpiar formulario' vacía asunto, mensaje y calificación")
def test_00_16_003_checkClearForm(page):
    assert_action(actions.test_00_16_003_checkClearForm, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_004_checkRatingToggle", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: La calificación se elige, se cambia y se quita")
def test_00_16_004_checkRatingToggle(page):
    assert_action(actions.test_00_16_004_checkRatingToggle, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_005_checkInvalidFileTypeRejected", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Un adjunto que no es imagen se rechaza y bloquea el envío")
def test_00_16_005_checkInvalidFileTypeRejected(page):
    assert_action(actions.test_00_16_005_checkInvalidFileTypeRejected, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_006_checkOversizedFileRejected", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Una imagen de más de 5 MB se rechaza y bloquea el envío")
def test_00_16_006_checkOversizedFileRejected(page):
    assert_action(actions.test_00_16_006_checkOversizedFileRejected, page)


# --- Envío e historial: crean datos que NO se pueden borrar, por eso solo van en full ---

@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_007_checkSubmitFeedback", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Enviar un reporte con categoría y calificación lo muestra en el historial y la API")
def test_00_16_007_checkSubmitFeedback(page):
    assert_action(actions.test_00_16_007_checkSubmitFeedback, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_008_checkSubmitFeedbackWithScreenshot", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Enviar una idea con captura (vista previa, quitar, enviar y abrirla desde el historial)")
def test_00_16_008_checkSubmitFeedbackWithScreenshot(page):
    assert_action(actions.test_00_16_008_checkSubmitFeedbackWithScreenshot, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_009_checkHistoryPersistsAfterReload", depends=["test_00_16_007_checkSubmitFeedback", "test_00_16_008_checkSubmitFeedbackWithScreenshot"])
@allure.description("Feedback: El historial conserva los envíos al recargar, el más reciente primero")
def test_00_16_009_checkHistoryPersistsAfterReload(page):
    assert_action(actions.test_00_16_009_checkHistoryPersistsAfterReload, page)


# --- API: permisos y validaciones ---

@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_010_checkApiRejectsInvalidPayload", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: La API responde 400 a mensaje corto, asunto en blanco, categoría desconocida y calificación 6")
def test_00_16_010_checkApiRejectsInvalidPayload(page):
    assert_action(actions.test_00_16_010_checkApiRejectsInvalidPayload, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_011_checkApiRejectsInvalidScreenshot", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: La API responde 400 a una captura que no es imagen")
def test_00_16_011_checkApiRejectsInvalidScreenshot(page):
    assert_action(actions.test_00_16_011_checkApiRejectsInvalidScreenshot, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_012_checkFeedbackIsPrivateToAuthor", depends=["test_00_16_007_checkSubmitFeedback", "test_00_16_008_checkSubmitFeedbackWithScreenshot"])
@allure.description("Feedback: Cada usuario ve solo sus propios envíos")
def test_00_16_012_checkFeedbackIsPrivateToAuthor(page):
    assert_action(actions.test_00_16_012_checkFeedbackIsPrivateToAuthor, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_013_checkScreenshotAccessControl", depends=["test_00_16_007_checkSubmitFeedback", "test_00_16_008_checkSubmitFeedbackWithScreenshot"])
@allure.description("Feedback: La captura la ve el autor y el admin; otros reciben 403, 404 o 401")
def test_00_16_013_checkScreenshotAccessControl(page):
    assert_action(actions.test_00_16_013_checkScreenshotAccessControl, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_014_checkAdminListAndFilters", depends=["test_00_16_007_checkSubmitFeedback", "test_00_16_008_checkSubmitFeedbackWithScreenshot"])
@allure.description("Feedback: El admin lista y filtra por categoría y estado; los filtros inválidos dan 400")
def test_00_16_014_checkAdminListAndFilters(page):
    assert_action(actions.test_00_16_014_checkAdminListAndFilters, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_015_checkAdminUpdateReachesStudent", depends=["test_00_16_007_checkSubmitFeedback"])
@allure.description("Feedback: El estado y la nota del admin llegan al historial del estudiante")
def test_00_16_015_checkAdminUpdateReachesStudent(page):
    assert_action(actions.test_00_16_015_checkAdminUpdateReachesStudent, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_016_checkAnonymousIsRedirectedToLogin")
@allure.description("Feedback: Sin sesión se manda a login y la API responde 401")
def test_00_16_016_checkAnonymousIsRedirectedToLogin(page):
    assert_action(actions.test_00_16_016_checkAnonymousIsRedirectedToLogin, page)


# --- Estados que las cuentas reales no alcanzan (mocks) ---

@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_017_checkHistoryErrorAndRetry", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Un error del historial muestra 'Reintentar' y se recupera")
def test_00_16_017_checkHistoryErrorAndRetry(page):
    assert_action(actions.test_00_16_017_checkHistoryErrorAndRetry, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_018_checkHistoryEmptyState", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Sin envíos se muestra el estado vacío y el contador en 0")
def test_00_16_018_checkHistoryEmptyState(page):
    assert_action(actions.test_00_16_018_checkHistoryEmptyState, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_00_16_019_checkSubmitErrorKeepsForm", depends=["test_00_16_000_checkSetUp"])
@allure.description("Feedback: Si el envío falla se muestra el error y el formulario conserva lo escrito")
def test_00_16_019_checkSubmitErrorKeepsForm(page):
    assert_action(actions.test_00_16_019_checkSubmitErrorKeepsForm, page)

