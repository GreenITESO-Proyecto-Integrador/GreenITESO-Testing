import allure
import pytest

from src.actions import Acceso_actions as actions
from src.utils.helpers import assert_action

# --- 401 vs 403 ---

@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_001_checkMissingTokenReturns401")
@allure.description("Acceso: Sin token, el API responde 401 con WWW-Authenticate: Bearer")
def test_02_15_001_checkMissingTokenReturns401(page):
    assert_action(actions.test_02_15_001_checkMissingTokenReturns401, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_002_checkInvalidTokenReturns401")
@allure.description("Acceso: Un token malformado o con la firma alterada recibe 401 token_not_valid")
def test_02_15_002_checkInvalidTokenReturns401(page):
    assert_action(actions.test_02_15_002_checkInvalidTokenReturns401, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_003_checkStudentGets403OnAdminEndpoints")
@allure.description("Acceso: Un estudiante con sesión válida recibe 403 (no 401) en endpoints de admin")
def test_02_15_003_checkStudentGets403OnAdminEndpoints(page):
    assert_action(actions.test_02_15_003_checkStudentGets403OnAdminEndpoints, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_004_checkAdminAllowedOnAdminEndpoint")
@allure.description("Acceso: El admin sí puede listar usuarios (control positivo del 403)")
def test_02_15_004_checkAdminAllowedOnAdminEndpoint(page):
    assert_action(actions.test_02_15_004_checkAdminAllowedOnAdminEndpoint, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_017_checkStudentDeniedAdminPanelData")
@allure.description("Acceso: El estudiante recibe 403 al leer la cola de auditoría, el buzón y el historial de usuarios")
def test_02_15_017_checkStudentDeniedAdminPanelData(page):
    assert_action(actions.test_02_15_017_checkStudentDeniedAdminPanelData, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_018_checkStudentCannotRunAdminOperations")
@allure.description("Acceso: El estudiante recibe 403 al cambiar roles, banear o aprobar/rechazar propuestas")
def test_02_15_018_checkStudentCannotRunAdminOperations(page):
    assert_action(actions.test_02_15_018_checkStudentCannotRunAdminOperations, page)


# --- Tokens JWT ---

@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_005_checkRefreshRejectsInvalidToken")
@allure.description("Acceso: Refresh inválido → 401; sin el campo refresh → 400")
def test_02_15_005_checkRefreshRejectsInvalidToken(page):
    assert_action(actions.test_02_15_005_checkRefreshRejectsInvalidToken, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_006_checkLogoutRejectsInvalidToken")
@allure.description("Acceso: El logout con un refresh inválido responde 401")
def test_02_15_006_checkLogoutRejectsInvalidToken(page):
    assert_action(actions.test_02_15_006_checkLogoutRejectsInvalidToken, page)


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_007_checkRefreshTokenRejectedAsBearer")
@allure.description("Acceso: Un refresh token usado como Bearer recibe 401 token_not_valid")
def test_02_15_007_checkRefreshTokenRejectedAsBearer(page):
    assert_action(actions.test_02_15_007_checkRefreshTokenRejectedAsBearer, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_008_checkAccessTokenRejectedForRefreshAndLogout")
@allure.description("Acceso: Un access token no sirve para renovar ni para cerrar sesión (401)")
def test_02_15_008_checkAccessTokenRejectedForRefreshAndLogout(page):
    assert_action(actions.test_02_15_008_checkAccessTokenRejectedForRefreshAndLogout, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_009_checkAccessTokenClaims")
@allure.description("Acceso: El access token es de tipo access, dura 60 min y pertenece al usuario")
def test_02_15_009_checkAccessTokenClaims(page):
    assert_action(actions.test_02_15_009_checkAccessTokenClaims, page)


# --- Sesión en el frontend ---

@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_010_checkFailedRenewalSendsToLogin")
@allure.description("Acceso: Si la renovación falla, el frontend limpia la sesión y manda a /login")
def test_02_15_010_checkFailedRenewalSendsToLogin(page):
    assert_action(actions.test_02_15_010_checkFailedRenewalSendsToLogin, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_011_checkLogoutClearsBrowserSession")
@allure.description("Acceso: Cerrar sesión limpia el sessionStorage y 'atrás' no devuelve la sesión")
def test_02_15_011_checkLogoutClearsBrowserSession(page):
    assert_action(actions.test_02_15_011_checkLogoutClearsBrowserSession, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_012_checkFrontendSendsBearerToken")
@allure.description("Acceso: El frontend manda Authorization: Bearer en sus llamadas al API")
def test_02_15_012_checkFrontendSendsBearerToken(page):
    assert_action(actions.test_02_15_012_checkFrontendSendsBearerToken, page)


# --- Roles y rutas ---

@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_013_checkStudentBlockedFromAdminRoutes")
@allure.description("Acceso: El estudiante ve 'Acceso Restringido' en /audit, /admin/users y /admin/feedback")
def test_02_15_013_checkStudentBlockedFromAdminRoutes(page):
    assert_action(actions.test_02_15_013_checkStudentBlockedFromAdminRoutes, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_014_checkStudentNavHidesAdminLinks")
@allure.description("Acceso: El menú del estudiante no muestra links a /audit, /admin/users ni /admin/feedback")
def test_02_15_014_checkStudentNavHidesAdminLinks(page):
    assert_action(actions.test_02_15_014_checkStudentNavHidesAdminLinks, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_015_checkAdminSeesAdminRoutes")
@allure.description("Acceso: El admin abre /audit, /admin/users y /admin/feedback y ve sus links")
def test_02_15_015_checkAdminSeesAdminRoutes(page):
    assert_action(actions.test_02_15_015_checkAdminSeesAdminRoutes, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_019_checkStudentHomeHidesAuditPanel")
@allure.description("Acceso: El estudiante no ve el botón 'Panel de Auditoría' en /home")
def test_02_15_019_checkStudentHomeHidesAuditPanel(page):
    assert_action(actions.test_02_15_019_checkStudentHomeHidesAuditPanel, page)


@pytest.mark.full
@pytest.mark.dependency(name="test_02_15_016_checkTamperedRoleIsRejectedByApi")
@allure.description("Acceso: Un estudiante que se pone rol ADMIN en el navegador recibe 403 del API")
def test_02_15_016_checkTamperedRoleIsRejectedByApi(page):
    assert_action(actions.test_02_15_016_checkTamperedRoleIsRejectedByApi, page)
