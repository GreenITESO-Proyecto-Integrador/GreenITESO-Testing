"""Acciones del login institucional, lado backend (tests/LoginInstitucionalBack/test_LoginInstitucionalBack.py).

ID01 ("Identidad 1"): login institucional con Microsoft, dominio @iteso.mx, alta o actualización
del usuario y rol según el puesto. Se llama a ``POST /api/v1/auth/login/`` como lo hace el front,
con el proveedor mock del backend (``mock:<correo>`` o ``mock:{json}``). Por eso solo corren con
AUTH_MODE=mock (stack local o el de CI): en prod el backend rechaza los tokens mock.

Cada prueba usa correos nuevos de la corrida (``e2e.login.<marcador>-<n>@iteso.mx``), así no toca
a los usuarios de prueba que usan los otros módulos.
"""

import json
import re
import time
from itertools import count

from playwright.sync_api import APIResponse, Page

from src.configs import environment as env
from src.utils.api import api_for_page
from src.utils.logger import get_logger
from src.utils.test_data import run_id

logger = get_logger(__name__)

_LOGIN_PATH = "/api/v1/auth/login/"
_COUNTER = count(1)
_THROTTLE_DEADLINE_SECONDS = 75


# --- privadas -------------------------------------------------------------------------------

def _new_email() -> str:
    marker = re.sub(r"[^a-z0-9-]", "", run_id().lower())
    worker = f"{env.XDIST_WORKER}-" if env.XDIST_WORKER else ""
    return f"e2e.login.{marker}-{worker}{next(_COUNTER)}@iteso.mx"


def _send(page: Page, method: str, data: dict | None = None) -> APIResponse:
    """Call the login endpoint, waiting out the backend throttle (10/min per IP and token) if it hits."""
    url = env.API_BASE_URL.rstrip("/") + _LOGIN_PATH
    # La ventana del throttle es de 60 s: pasado ese tiempo siempre hay cupo.
    deadline = time.monotonic() + _THROTTLE_DEADLINE_SECONDS
    response = page.request.fetch(url, method=method, data=data)
    while response.status == 429 and time.monotonic() < deadline:
        wait = int(response.headers.get("retry-after", "5"))
        logger.info("Login throttled; reintento en %ss", wait)
        page.wait_for_timeout((wait + 1) * 1000)
        response = page.request.fetch(url, method=method, data=data)
    return response


def _login(page: Page, id_token: str) -> APIResponse:
    return _send(page, "POST", {"id_token": id_token, "access_token": ""})


def _mock(**claims: object) -> str:
    return "mock:" + json.dumps(claims)


def _expect(response: APIResponse, status: int, code: str | None = None) -> bool:
    if response.status != status:
        logger.error("Se esperaba %s y llegó %s: %s", status, response.status, response.text()[:300])
        return False
    if code is not None:
        got = (response.json().get("error") or {}).get("code")
        if got != code:
            logger.error("Se esperaba el código %s y llegó %s", code, got)
            return False
    return True


def _login_ok(page: Page, id_token: str) -> dict:
    response = _login(page, id_token)
    if response.status != 200:
        raise RuntimeError(f"Login {id_token!r} → {response.status}: {response.text()[:300]}")
    return response.json()


def _set_role(page: Page, user_id: str, role: str) -> None:
    api_for_page(page).json("admin", "PATCH", f"/api/v1/users/{user_id}/role/", data={"role": role})


# --- tests: alta y actualización ------------------------------------------------------------

def test_00_01_101_checkFirstLoginCreatesUser(page: Page) -> bool:
    body = _login_ok(page, f"mock:{_new_email()}")
    user = body.get("user") or {}
    checks = {
        "created es true": body.get("created") is True,
        "hay access y refresh distintos": bool(body.get("access")) and body.get("access") != body.get("refresh"),
        "rol STUDENT por default": user.get("role") == "STUDENT",
        "no expone password ni microsoft_oid": "password" not in user and "microsoft_oid" not in user,
    }
    for name, ok in checks.items():
        if not ok:
            logger.error("Falló: %s (respuesta: %s)", name, body)
    return all(checks.values())


def test_00_01_102_checkSecondLoginReusesUser(page: Page) -> bool:
    email = _new_email()
    first = _login_ok(page, f"mock:{email}")
    second = _login_ok(page, f"mock:{email.upper()}")
    if second.get("created") is not False:
        logger.error("El segundo login volvió a crear la cuenta")
        return False
    if second["user"]["id"] != first["user"]["id"]:
        logger.error("El correo en mayúsculas creó otra cuenta")
        return False
    return second["user"]["email"] == email


def test_00_01_103_checkOtherDomainsRejected(page: Page) -> bool:
    results = [
        _expect(_login(page, "mock:e2e.login@gmail.com"), 403, "DOMAIN_NOT_ALLOWED"),
        _expect(_login(page, "mock:e2e.login@alumnos.iteso.mx"), 403, "DOMAIN_NOT_ALLOWED"),
    ]
    return all(results)


def test_00_01_104_checkInvalidRequestsRejected(page: Page) -> bool:
    # Cada token lleva el marcador de la corrida: el throttle cuenta por (IP, token), y las peticiones
    # sin id_token comparten una sola cubeta que se llena al repetir corridas.
    marker = run_id()
    results = [
        _expect(_login(page, "x" * 8200 + marker), 400, "VALIDATION_ERROR"),
        _expect(_login(page, f"no-es-mock-{marker}"), 401, "UNAUTHENTICATED"),
    ]
    return all(results)


def test_00_01_105_checkDirectoryDataApplied(page: Page) -> bool:
    email = _new_email()
    body = _login_ok(page, _mock(email=email, given_name="Ana", surname="García", job_title="Profesor"))
    user = body["user"]
    if (user.get("first_name"), user.get("last_name")) != ("Ana", "García"):
        logger.error("No se copiaron los nombres del directorio: %s", user)
        return False
    if user.get("role") != "STAFF":
        logger.error("Un 'Profesor' debería ser STAFF y quedó %s", user.get("role"))
        return False
    # Sin puesto en el directorio (Graph no lo mandó) no se toca el rol.
    again = _login_ok(page, f"mock:{email}")
    if again["user"]["role"] != "STAFF":
        logger.error("Un login sin puesto bajó al STAFF a %s", again["user"]["role"])
        return False
    return True


def test_00_01_106_checkAdminNeverDemoted(page: Page) -> bool:
    email = _new_email()
    user_id = _login_ok(page, f"mock:{email}")["user"]["id"]
    _set_role(page, user_id, "ADMIN")
    role = _login_ok(page, _mock(email=email, job_title="Alumno"))["user"]["role"]
    if role != "ADMIN":
        logger.error("El login con puesto 'Alumno' le quitó el ADMIN (quedó %s)", role)
        return False
    return True


def test_00_01_107_checkSelfDeactivatedAccountReactivates(page: Page) -> bool:
    email = _new_email()
    access = _login_ok(page, f"mock:{email}")["access"]
    url = env.API_BASE_URL.rstrip("/") + "/api/v1/profile/me/deactivate/"
    response = page.request.post(url, data={"confirm": True}, headers={"Authorization": f"Bearer {access}"})
    if response.status != 204:
        raise RuntimeError(f"No se pudo desactivar la cuenta: {response.status} {response.text()[:300]}")
    body = _login_ok(page, f"mock:{email}")
    if body.get("reactivated") is not True or body.get("created") is not False:
        logger.error("Se esperaba reactivated=true y created=false: %s", body)
        return False
    return True


# --- tests: hallazgos (fallan mientras el problema exista) ----------------------------------

def test_00_01_151_checkAdminAssignedRoleSurvivesLogin(page: Page) -> bool:
    """Hallazgo 1 (alta, DehBarca): el login regresa a STUDENT a quien un admin hizo STAFF."""
    email = _new_email()
    user_id = _login_ok(page, _mock(email=email, job_title="Alumno"))["user"]["id"]
    _set_role(page, user_id, "STAFF")
    role = _login_ok(page, _mock(email=email, job_title="Alumno"))["user"]["role"]
    logger.info("Rol después del login: %s (esperado STAFF)", role)
    return role == "STAFF"


def test_00_01_152_checkStudentAssistantIsStudent(page: Page) -> bool:
    """Hallazgo 2 (media, DehBarca): 'Alumno Asistente de Profesor' queda como STAFF."""
    body = _login_ok(page, _mock(email=_new_email(), job_title="Alumno Asistente de Profesor"))
    logger.info("Rol: %s (esperado STUDENT)", body["user"]["role"])
    return body["user"]["role"] == "STUDENT"


def test_00_01_153_checkEmailWithTwoAtSignsRejected(page: Page) -> bool:
    """Hallazgo 5 (baja, Pardosito): el filtro de dominio solo mira la última @."""
    marker = re.sub(r"[^a-z0-9-]", "", run_id().lower())
    return _expect(_login(page, f"mock:e2e.{marker}@gmail.com@iteso.mx"), 403, "DOMAIN_NOT_ALLOWED")
