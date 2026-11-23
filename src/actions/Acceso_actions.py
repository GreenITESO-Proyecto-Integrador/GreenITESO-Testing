"""Acciones del módulo 15 · Acceso: tokens JWT, 401 vs 403 y control por rol (tests/equipo2/Acceso).

Módulo del Equipo 2 (identidad y acceso), probado por el Equipo 1. Combina pruebas de API (el contrato
de autenticación del backend) con pruebas de UI (cómo reacciona el frontend a la sesión y al rol).

Ningún caso canjea ni revoca un refresh token real: en modo refresh cada usuario de prueba tiene una sola
cadena de refresh tokens y gastarla rompería las corridas siguientes. Todos corren en mock y en refresh.
"""

import base64
import json
import re
import uuid
from collections.abc import Sequence

from playwright.sync_api import APIResponse, Locator, Page

from src.configs import environment as env
from src.utils.auth import Session, get_session, inject_session
from src.utils.common_actions import go_to, login_as, logout
from src.utils.helpers import (
    is_on_path,
    locator_has_visible_match,
    wait_for_app_ready,
    wait_for_path,
    wait_until,
)
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_REFRESH_PATH = "/api/v1/auth/refresh/"
_LOGOUT_PATH = "/api/v1/auth/logout/"
_PROFILE_PATH = "/api/v1/profile/me/"
_USERS_PATH = "/api/v1/users/"
_ACTIONS_PATH = "/api/v1/actions/"
_MAX_THROTTLE_RETRIES = 3
# SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] del backend (settings/base.py): 60 minutos.
_ACCESS_LIFETIME_SECONDS = 60 * 60
_INVALID_TOKEN = "e2e-not-a-jwt"
_EXPIRED_ACCESS = "e2e-expired-access-token"
# Mismas llaves que GreenITESO-Frontend/src/lib/auth/session.ts (AUTH_STORAGE_KEYS).
_STORAGE_KEYS = {
    "access": "greeniteso.access_token",
    "refresh": "greeniteso.refresh_token",
    "user": "greeniteso.user",
}
# Rutas con ADMIN_ROLES en GreenITESO-Frontend/src/routes.tsx.
_ADMIN_ROUTES = ("/audit", "/audit?tab=proposals", "/admin/users", "/admin/feedback")
# Etiquetas del menú lateral (GreenITESO-Frontend/src/components/layout/nav-links.ts).
_ADMIN_NAV_LABELS = ("Auditoría", "Usuarios", "Buzón de feedback")
_STUDENT_NAV_LABEL = "Clanes"


# --- privadas: API --------------------------------------------------------------------------

def _api(page: Page, method: str, path: str, *, token: str | None = None, data: dict | None = None) -> APIResponse:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for attempt in range(_MAX_THROTTLE_RETRIES + 1):
        response = page.request.fetch(env.API_BASE_URL.rstrip("/") + path, method=method, headers=headers, data=data)
        if response.status != 429 or attempt == _MAX_THROTTLE_RETRIES:
            return response
        wait = int(response.headers.get("retry-after", "10"))
        logger.info("%s %s throttled; reintento en %ss", method, path, wait)
        page.wait_for_timeout(wait * 1000)
    return response


def _session(page: Page, role: str) -> Session:
    return get_session(page.request, env.TEST_USERS[role])


def _expect_status(response: APIResponse, expected: int, label: str) -> bool:
    if response.status == expected:
        logger.info("%s → %s", label, response.status)
        return True
    logger.error("%s → %s (se esperaba %s): %s", label, response.status, expected, response.text()[:200])
    return False


def _error_code(response: APIResponse) -> str:
    try:
        return str(response.json().get("code", ""))
    except Exception:  # noqa: BLE001
        return ""


def _has_bearer_challenge(response: APIResponse) -> bool:
    return "bearer" in response.headers.get("www-authenticate", "").lower()


def _tampered(token: str) -> str:
    """Change the last characters of the signature so the token keeps its shape but fails verification."""
    suffix = "AAAA" if not token.endswith("AAAA") else "BBBB"
    return token[:-4] + suffix


def _jwt_claims(token: str) -> dict:
    """Decode the JWT payload without verifying it (only to read its claims)."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


# --- privadas: UI ---------------------------------------------------------------------------

def _storage_value(page: Page, key: str) -> str | None:
    return page.evaluate("k => sessionStorage.getItem(k)", key)


def _storage_leftovers(page: Page) -> list[str]:
    return [key for key in _STORAGE_KEYS.values() if _storage_value(page, key) is not None]


def _fake_session(role: str) -> Session:
    return {
        "access": _EXPIRED_ACCESS,
        "refresh": _INVALID_TOKEN,
        "user": {"id": str(uuid.uuid4()), "email": "e2e@iteso.mx", "firstName": "E2E", "lastName": "", "role": role},
    }


def _sidebar_link(page: Page, label: str) -> Locator:
    # <aside> del menú lateral (components/layout/Sidebar.tsx) tiene el rol implícito "complementary".
    return page.get_by_role("complementary").get_by_role("link", name=re.compile(rf"^\s*{re.escape(label)}\s*$"))


def _visible_nav_labels(page: Page, labels: Sequence[str]) -> list[str]:
    return [label for label in labels if locator_has_visible_match(_sidebar_link(page, label))]


def _admin_data_endpoints(user_id: str) -> tuple[str, ...]:
    """GET endpoints that expose admin panel data (audit queue, feedback inbox, user history)."""
    return (
        "/api/v1/action-logs/",
        f"/api/v1/action-logs/{uuid.uuid4()}/evidence/",
        "/api/v1/feedback/",
        f"/api/v1/feedback/{uuid.uuid4()}/",
        f"/api/v1/users/{user_id}/role-history/",
        f"/api/v1/users/{user_id}/ban-history/",
    )


def _admin_operations() -> tuple[tuple[str, str, dict], ...]:
    """Admin-only writes, all against random ids: the role check comes first, so nothing can change."""
    target = uuid.uuid4()
    proposal = uuid.uuid4()
    return (
        ("PATCH", f"/api/v1/users/{target}/role/", {"role": "ADMIN"}),
        ("POST", f"/api/v1/users/{target}/ban/", {}),
        ("POST", f"/api/v1/users/{target}/unban/", {}),
        ("POST", f"/api/v1/campaigns/proposals/{proposal}/approve/", {}),
        ("POST", f"/api/v1/campaigns/proposals/{proposal}/reject/", {"rejection_reason": "E2E"}),
    )


def _path_only(path: str) -> str:
    return path.split("?", 1)[0]


def _shows_access_denied(page: Page, path: str) -> bool:
    go_to(page, path)
    path = _path_only(path)
    visible = all(
        locator_has_visible_match(page.locator(selector), timeout=_SHORT_TIMEOUT * 2)
        for selector in (Locs.ACCESS_DENIED_TITLE, Locs.ACCESS_DENIED_BADGE)
    )
    if not visible:
        logger.error("%s no muestra 'Acceso Restringido' / 'Error 403'", path)
        return False
    if not is_on_path(page, path):
        logger.error("Se esperaba seguir en %s, la URL es %s", path, page.url)
        return False
    logger.info("%s → Acceso Restringido (403)", path)
    return True


# --- tests: 401 vs 403 ----------------------------------------------------------------------

def test_02_15_001_checkMissingTokenReturns401(page: Page) -> bool:
    ok = True
    for path in (_PROFILE_PATH, _USERS_PATH):
        response = _api(page, "GET", path)
        ok &= _expect_status(response, 401, f"GET {path} sin token")
        if not _has_bearer_challenge(response):
            logger.error("GET %s sin token no trae WWW-Authenticate: Bearer", path)
            ok = False
    return ok


def test_02_15_002_checkInvalidTokenReturns401(page: Page) -> bool:
    tokens = (
        ("token malformado", _INVALID_TOKEN),
        ("firma alterada", _tampered(_session(page, "student")["access"])),
    )
    ok = True
    for label, token in tokens:
        response = _api(page, "GET", _PROFILE_PATH, token=token)
        ok &= _expect_status(response, 401, f"GET {_PROFILE_PATH} con {label}")
        if _error_code(response) != "token_not_valid":
            logger.error("Con %s el código es %r, se esperaba 'token_not_valid'", label, _error_code(response))
            ok = False
    return ok


def test_02_15_003_checkStudentGets403OnAdminEndpoints(page: Page) -> bool:
    token = _session(page, "student")["access"]
    # Control: el token es válido, así que cualquier rechazo siguiente es por rol (403), no por sesión (401).
    if not _expect_status(_api(page, "GET", _PROFILE_PATH, token=token), 200, "Estudiante en /profile/me/"):
        return False
    checks = (
        ("GET", _USERS_PATH, None),
        # El permiso se revisa antes de buscar el log o validar el cuerpo: no modifica nada.
        ("PATCH", f"/api/v1/action-logs/{uuid.uuid4()}/audit/", {"status": "APPROVED"}),
        ("POST", _ACTIONS_PATH, {}),
    )
    ok = True
    for method, path, data in checks:
        ok &= _expect_status(_api(page, method, path, token=token, data=data), 403, f"Estudiante {method} {path}")
    return ok


def test_02_15_004_checkAdminAllowedOnAdminEndpoint(page: Page) -> bool:
    response = _api(page, "GET", _USERS_PATH, token=_session(page, "admin")["access"])
    if not _expect_status(response, 200, f"Admin GET {_USERS_PATH}"):
        return False
    return "results" in response.json()


# --- tests: tokens JWT (sin canjear ni revocar ningún refresh real) -------------------------

def test_02_15_005_checkRefreshRejectsInvalidToken(page: Page) -> bool:
    invalid = _expect_status(
        _api(page, "POST", _REFRESH_PATH, data={"refresh": _INVALID_TOKEN}), 401, "Refresh con token inválido"
    )
    # Sin el campo es un error de validación (400), no de autenticación.
    missing = _expect_status(_api(page, "POST", _REFRESH_PATH, data={}), 400, "Refresh sin el campo refresh")
    return invalid and missing


def test_02_15_006_checkLogoutRejectsInvalidToken(page: Page) -> bool:
    response = _api(page, "POST", _LOGOUT_PATH, data={"refresh": _INVALID_TOKEN})
    return _expect_status(response, 401, "Logout con refresh inválido")


def test_02_15_007_checkRefreshTokenRejectedAsBearer(page: Page) -> bool:
    # Mandarlo como Bearer no lo canjea: no gasta la cadena guardada del usuario de prueba.
    response = _api(page, "GET", _PROFILE_PATH, token=_session(page, "student")["refresh"])
    if not _expect_status(response, 401, "Refresh token como Bearer"):
        return False
    return _error_code(response) == "token_not_valid"


def test_02_15_008_checkAccessTokenRejectedForRefreshAndLogout(page: Page) -> bool:
    access = _session(page, "student")["access"]
    refresh = _expect_status(
        _api(page, "POST", _REFRESH_PATH, data={"refresh": access}), 401, "Access token en /auth/refresh/"
    )
    revoke = _expect_status(_api(page, "POST", _LOGOUT_PATH, data={"refresh": access}), 401, "Access en /auth/logout/")
    # El access sigue sirviendo: los rechazos anteriores no lo invalidaron.
    still_valid = _expect_status(_api(page, "GET", _PROFILE_PATH, token=access), 200, "Access después de los rechazos")
    return refresh and revoke and still_valid


def test_02_15_009_checkAccessTokenClaims(page: Page) -> bool:
    access = _session(page, "student")["access"]
    claims = _jwt_claims(access)
    profile = _api(page, "GET", "/api/v1/users/me/", token=access)
    if not _expect_status(profile, 200, "GET /api/v1/users/me/"):
        return False
    lifetime = int(claims.get("exp", 0)) - int(claims.get("iat", 0))
    checks = {
        "token_type es 'access'": claims.get("token_type") == "access",
        f"dura {_ACCESS_LIFETIME_SECONDS} s (tiene {lifetime})": lifetime == _ACCESS_LIFETIME_SECONDS,
        "user_id es el del usuario": str(claims.get("user_id")) == str(profile.json().get("id")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    for name in failed:
        logger.error("Claim del access token no cumple: %s", name)
    return not failed


# --- tests: sesión en el frontend -----------------------------------------------------------

def test_02_15_010_checkFailedRenewalSendsToLogin(page: Page) -> bool:
    inject_session(page, _fake_session("STUDENT"))
    go_to(page, "/profile")
    wait_for_path(page, "/login")
    if not locator_has_visible_match(page.locator(Locs.LOGIN_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("Con un refresh rechazado no se ve la pantalla de login")
        return False
    leftovers = _storage_leftovers(page)
    if leftovers:
        logger.error("El frontend no limpió la sesión rechazada: %s", leftovers)
        return False
    return True


def test_02_15_011_checkLogoutClearsBrowserSession(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/")
    wait_for_app_ready(page)
    logout(page)
    wait_for_path(page, "/login")
    leftovers = _storage_leftovers(page)
    if leftovers:
        logger.error("Después de cerrar sesión siguen en sessionStorage: %s", leftovers)
        return False
    # Regresar con el botón "atrás" no debe devolver la sesión.
    page.go_back(wait_until="domcontentloaded")
    if not wait_until(lambda: is_on_path(page, "/login"), page, timeout=_SHORT_TIMEOUT):
        logger.error("Al regresar con 'atrás' la URL es %s, se esperaba /login", page.url)
        return False
    return True


def test_02_15_012_checkFrontendSendsBearerToken(page: Page) -> bool:
    login_as(page, "student")
    with page.expect_request(lambda r: "/api/v1/" in r.url and r.method == "GET", timeout=_SHORT_TIMEOUT * 3) as sent:
        go_to(page, "/profile")
    header = sent.value.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) <= len("Bearer "):
        logger.error("La llamada %s no manda 'Authorization: Bearer <token>'", sent.value.url)
        return False
    logger.info("El frontend manda Bearer en %s", sent.value.url)
    return True


# --- tests: roles y rutas -------------------------------------------------------------------

def test_02_15_013_checkStudentBlockedFromAdminRoutes(page: Page) -> bool:
    login_as(page, "student")
    # Lista y no generador: se revisan todas las rutas aunque una falle, para verlas todas en el log.
    results = [_shows_access_denied(page, path) for path in _ADMIN_ROUTES]
    return all(results)


def test_02_15_014_checkStudentNavHidesAdminLinks(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/")
    wait_for_app_ready(page)
    if not _visible_nav_labels(page, [_STUDENT_NAV_LABEL]):
        logger.error("No se ve el menú lateral (falta '%s'); no se puede validar", _STUDENT_NAV_LABEL)
        return False
    shown = _visible_nav_labels(page, _ADMIN_NAV_LABELS)
    if shown:
        logger.error("El estudiante ve links de admin: %s", shown)
        return False
    return True


def test_02_15_015_checkAdminSeesAdminRoutes(page: Page) -> bool:
    login_as(page, "admin")
    # Control positivo de TC-15-013: las mismas rutas sí abren para el admin.
    for path in _ADMIN_ROUTES:
        go_to(page, path)
        wait_for_app_ready(page)
        if locator_has_visible_match(page.locator(Locs.ACCESS_DENIED_TITLE), timeout=_SHORT_TIMEOUT):
            logger.error("El admin ve 'Acceso Restringido' en %s", path)
            return False
        logger.info("Admin abre %s", path)
    go_to(page, "/admin/users")
    wait_for_app_ready(page)
    title = page.get_by_role("heading", level=1, name=re.compile(r"^\s*Usuarios\s*$"))
    if not locator_has_visible_match(title, timeout=_SHORT_TIMEOUT * 2):
        logger.error("No se ve el título 'Usuarios' en /admin/users")
        return False
    missing = [label for label in _ADMIN_NAV_LABELS if label not in _visible_nav_labels(page, _ADMIN_NAV_LABELS)]
    if missing:
        logger.error("Al admin le faltan links de administración: %s", missing)
        return False
    return True


def test_02_15_017_checkStudentDeniedAdminPanelData(page: Page) -> bool:
    session = _session(page, "student")
    ok = True
    for path in _admin_data_endpoints(session["user"]["id"]):
        ok &= _expect_status(_api(page, "GET", path, token=session["access"]), 403, f"Estudiante GET {path}")
    return ok


def test_02_15_018_checkStudentCannotRunAdminOperations(page: Page) -> bool:
    token = _session(page, "student")["access"]
    ok = True
    for method, path, data in _admin_operations():
        ok &= _expect_status(_api(page, method, path, token=token, data=data), 403, f"Estudiante {method} {path}")
    return ok


def test_02_15_019_checkStudentHomeHidesAuditPanel(page: Page) -> bool:
    login_as(page, "student")
    go_to(page, "/home")
    wait_for_app_ready(page)
    profile_button = page.get_by_role("button", name=re.compile(r"Mi Perfil", re.IGNORECASE))
    if not locator_has_visible_match(profile_button, timeout=_SHORT_TIMEOUT * 2):
        logger.error("No se ve el botón 'Mi Perfil' en /home; no se puede validar")
        return False
    audit_button = page.get_by_role("button", name=re.compile(r"Panel de Auditoría", re.IGNORECASE))
    if locator_has_visible_match(audit_button, timeout=_SHORT_TIMEOUT):
        logger.error("El estudiante ve el botón 'Panel de Auditoría' en /home")
        return False
    return True


def test_02_15_016_checkTamperedRoleIsRejectedByApi(page: Page) -> bool:
    user = login_as(page, "student")
    # El rol del frontend vive en sessionStorage: un estudiante puede cambiarlo, pero el backend decide.
    tampered_user = json.dumps({**user, "role": "ADMIN"})
    page.add_init_script(
        script=f"sessionStorage.setItem({json.dumps(_STORAGE_KEYS['user'])}, {json.dumps(tampered_user)});"
    )
    with page.expect_response(
        lambda r: _USERS_PATH in r.url and r.request.method == "GET", timeout=_SHORT_TIMEOUT * 3
    ) as captured:
        go_to(page, "/admin/users")
    return _expect_status(captured.value, 403, "UI con rol ADMIN falso → GET /users/")
