"""Acciones del login institucional, lado frontend (tests/LoginInstitucionalFront/test_LoginInstitucionalFront.py).

ID01 ("Identidad 1"): la pantalla /login y el salto a Microsoft. La ida a login.microsoftonline.com
se intercepta y se cancela, así que no hace falta una cuenta real y corre en cualquier ambiente.
Lo que ya cubre tests/Auth/ (título, botón, aviso, /profile → /login) no se repite aquí.
"""

from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, Route

from src.utils.common_actions import go_to
from src.utils.helpers import locator_has_visible_match, wait_for_path, wait_until
from src.utils.locators import Locs
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SHORT_TIMEOUT = 5_000
_MICROSOFT_GLOB = "https://login.microsoftonline.com/**"
_LOGIN_API_FRAGMENT = "/api/v1/auth/login/"
_REQUIRED_SCOPES = ("openid", "profile", "email", "offline_access", "User.Read")
_SESSION_ONLY_PATHS = ("/clans", "/admin/users")


# --- privadas -------------------------------------------------------------------------------

def _open_login(page: Page) -> None:
    go_to(page, "/login")
    page.locator(Locs.LOGIN_TITLE).first.wait_for(timeout=_SHORT_TIMEOUT * 2)
    if locator_has_visible_match(page.locator(Locs.LOGIN_NOT_CONFIGURED_ALERT)):
        raise RuntimeError("Microsoft login no está configurado (falta VITE_MICROSOFT_CLIENT_ID)")


def _capture_authorize_params(page: Page) -> tuple[dict[str, str], str]:
    """Click the login button and return the /authorize query params plus the app origin."""
    captured: list[str] = []

    def handler(route: Route) -> None:
        url = route.request.url
        if urlsplit(url).path.endswith("/authorize"):
            captured.append(url)
        route.abort()

    page.route(_MICROSOFT_GLOB, handler)
    _open_login(page)
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(page.url))
    page.locator(Locs.LOGIN_BUTTON).first.click()
    if not wait_until(lambda: bool(captured), page, timeout=_SHORT_TIMEOUT * 2):
        raise RuntimeError("El botón no mandó al /authorize de Microsoft")
    logger.info("Redirect a Microsoft: %s", captured[0].split("?")[0])
    params = {key: values[0] for key, values in parse_qs(urlsplit(captured[0]).query).items()}
    return params, origin


def _report(checks: dict[str, bool]) -> bool:
    for name, ok in checks.items():
        if not ok:
            logger.error("Falló: %s", name)
    return all(checks.values())


# --- tests ----------------------------------------------------------------------------------

def test_00_01_201_checkLoginPageIsClean(page: Page) -> bool:
    login_calls: list[str] = []
    page.on("request", lambda request: login_calls.append(request.url) if _LOGIN_API_FRAGMENT in request.url else None)
    _open_login(page)
    return _report({
        "no pide contraseña propia": not locator_has_visible_match(page.locator(Locs.PASSWORD_INPUT)),
        "no pide correo propio": not locator_has_visible_match(page.locator(Locs.EMAIL_INPUT)),
        "no muestra errores al entrar": not locator_has_visible_match(page.locator(Locs.ALERT)),
        "no llama al backend solo por abrir la página": not login_calls,
    })


def test_00_01_202_checkMicrosoftRedirectTarget(page: Page) -> bool:
    params, origin = _capture_authorize_params(page)
    redirect = urlsplit(params.get("redirect_uri", ""))
    return _report({
        "manda el client_id de la app": bool(params.get("client_id")),
        "regresa al mismo origen": f"{redirect.scheme}://{redirect.netloc}" == origin,
        "regresa a /login": redirect.path == "/login",
        "no manda client_secret": "client_secret" not in params,
    })


def test_00_01_203_checkMicrosoftRedirectUsesPkce(page: Page) -> bool:
    params, _ = _capture_authorize_params(page)
    scopes = params.get("scope", "").split()
    missing = [scope for scope in _REQUIRED_SCOPES if scope not in scopes]
    if missing:
        logger.error("Faltan permisos %s en %s", missing, scopes)
    return _report({
        "pide openid, profile, email, offline_access y User.Read": not missing,
        "usa response_type=code (no el flujo implícito)": params.get("response_type") == "code",
        "usa PKCE con S256": params.get("code_challenge_method") == "S256" and bool(params.get("code_challenge")),
    })


def test_00_01_204_checkSessionOnlyRoutesRedirect(page: Page) -> bool:
    results = []
    for path in _SESSION_ONLY_PATHS:
        go_to(page, path)
        try:
            wait_for_path(page, "/login")
            results.append(True)
            logger.info("%s → /login", path)
        except RuntimeError as exc:
            logger.error("%s no redirigió a /login: %s", path, exc)
            results.append(False)
    return all(results)
