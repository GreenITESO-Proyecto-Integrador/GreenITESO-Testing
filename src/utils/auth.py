"""Sesión de pruebas sin pasar por la UI de Microsoft en cada test.

Pide tokens reales al backend y los inyecta en el sessionStorage del frontend, igual que el
login de Microsoft. Hay dos modos (AUTH_MODE):

- ``refresh`` (ambientes desplegados): una persona inicia sesión UNA vez por usuario con
  ``uv run python -m src.utils.auth --role <rol>``. Se guarda su refresh token y en cada corrida
  se canjea en /api/v1/auth/refresh/. Los refresh tokens son de un solo uso (rotan) y duran
  7 días, así que el token nuevo se guarda de inmediato; mientras haya una corrida cada
  7 días, la sesión no caduca.
- ``mock`` (stack local): pide la sesión con un id_token ``mock:<email>``. El backend solo lo
  acepta con MICROSOFT_AUTH_MODE=mock (DJANGO_ENV=dev, no desplegado).
"""

import argparse
import base64
import fcntl
import json
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

from playwright.sync_api import APIRequestContext, Page, sync_playwright

from src.configs import environment as env
from src.utils.logger import get_logger

logger = get_logger(__name__)

_LOGIN_PATH = "/api/v1/auth/login/"
_REFRESH_PATH = "/api/v1/auth/refresh/"
_EXPIRY_MARGIN_SECONDS = 5 * 60
_MAX_THROTTLE_RETRIES = 3
_BOOTSTRAP_TIMEOUT_SECONDS = 5 * 60

# Mismas llaves que GreenITESO-Frontend/src/lib/auth/session.ts
_STORAGE_KEYS = {
    "access": "greeniteso.access_token",
    "refresh": "greeniteso.refresh_token",
    "user": "greeniteso.user",
}
# Marca que la sesión ya se inyectó en esta pestaña; así "Cerrar sesión" no se revierte al navegar.
_INJECTED_FLAG = "greeniteso.e2e_session_injected"
# Tour guiado (GreenITESO-Frontend/src/components/onboarding/GuidedTour.tsx): se guarda en
# localStorage por usuario y fase. Un navegador de prueba arranca vacío, así que sin esto el
# tour taparía la UI en cada test.
_TOUR_STORAGE_PREFIX = "greeniteso.guided-tour."
_TOUR_PHASES = ("simple", "campaigns")
# En modo refresh el navegador NO recibe el refresh token real: si el frontend lo canjeara,
# lo invalidaría y la cadena guardada se perdería. Con el access token vigente no lo necesita.
_BROWSER_REFRESH_PLACEHOLDER = "e2e-refresh-placeholder"


class AuthUser(TypedDict):
    id: str
    email: str
    firstName: str
    lastName: str
    role: str


class Session(TypedDict):
    access: str
    refresh: str
    user: AuthUser


_MEMORY_CACHE: dict[str, Session] = {}


def _token_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:  # noqa: BLE001
        return 0.0


def _is_fresh(token: str) -> bool:
    return _token_exp(token) - _EXPIRY_MARGIN_SECONDS > time.time()


def _api_url(path: str) -> str:
    return env.API_BASE_URL.rstrip("/") + path


def _session_file(email: str) -> Path:
    return env.AUTH_STATE_DIR / f"{email.lower()}.json"


@contextmanager
def _locked(email: str) -> Iterator[None]:
    """Serialize token refreshes across xdist workers: a refresh token can only be redeemed once."""
    env.AUTH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(env.AUTH_STATE_DIR / f"{email.lower()}.lock", "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _read_session_file(email: str) -> Session | None:
    try:
        return json.loads(_session_file(email).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _write_session_file(email: str, session: Session) -> None:
    env.AUTH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_file(email)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(session), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def _post_with_throttle_retry(request: APIRequestContext, url: str, data: dict, label: str):
    for attempt in range(_MAX_THROTTLE_RETRIES + 1):
        response = request.post(url, data=data)
        if response.status == 429 and attempt < _MAX_THROTTLE_RETRIES:
            wait = int(response.headers.get("retry-after", "10"))
            logger.info("%s throttled; reintento en %ss", label, wait)
            time.sleep(wait)
            continue
        return response
    raise RuntimeError(f"{label} siguió throttled después de {_MAX_THROTTLE_RETRIES} reintentos.")


# --- modo refresh ---------------------------------------------------------------------------

def _refresh_session(request: APIRequestContext, email: str) -> Session:
    with _locked(email):
        stored = _read_session_file(email)
        if stored is None:
            raise RuntimeError(
                f"No hay sesión guardada para {email}. Inicia sesión una vez con: "
                f"uv run python -m src.utils.auth --email {email}"
            )
        if _is_fresh(stored["access"]):
            return stored

        logger.info("Renovando sesión de %s", email)
        response = _post_with_throttle_retry(
            request, _api_url(_REFRESH_PATH), {"refresh": stored["refresh"]}, f"Refresh de {email}"
        )
        if not response.ok:
            raise RuntimeError(
                f"No se pudo renovar la sesión de {email} ({response.status}). El refresh token "
                "expiró (más de 7 días sin corridas) o ya se usó. Vuelve a iniciar sesión con: "
                f"uv run python -m src.utils.auth --email {email}"
            )
        body = response.json()
        session: Session = {
            "access": body["access"],
            "refresh": body.get("refresh", stored["refresh"]),
            "user": stored["user"],
        }
        _write_session_file(email, session)
        return session


def _capture_session_from_browser(email: str) -> Session:
    """Open a headed browser so a person logs in with Microsoft, then read the resulting tokens."""
    login_url = env.BASE_URL.rstrip("/") + "/login"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(login_url)
        print(f"\nInicia sesión con la cuenta {email} en la ventana que se abrió ({login_url}).")
        deadline = time.monotonic() + _BOOTSTRAP_TIMEOUT_SECONDS
        tokens = None
        while time.monotonic() < deadline:
            try:
                tokens = page.evaluate(
                    "keys => keys.map(k => sessionStorage.getItem(k))",
                    [_STORAGE_KEYS["access"], _STORAGE_KEYS["refresh"], _STORAGE_KEYS["user"]],
                )
            except Exception:  # noqa: BLE001  (la página está navegando por Microsoft)
                tokens = None
            if tokens and all(tokens):
                break
            page.wait_for_timeout(1_000)
        browser.close()

    if not tokens or not all(tokens):
        raise RuntimeError("No se detectó el inicio de sesión a tiempo.")
    access, refresh, raw_user = tokens
    user = json.loads(raw_user)
    if user.get("email", "").lower() != email.lower():
        raise RuntimeError(f"Se inició sesión como {user.get('email')}, se esperaba {email}.")
    return {"access": access, "refresh": refresh, "user": user}


# --- modo mock ------------------------------------------------------------------------------

def _mock_session(request: APIRequestContext, email: str) -> Session:
    cached = _MEMORY_CACHE.get(email) or _read_session_file(email)
    if cached and _is_fresh(cached["access"]):
        _MEMORY_CACHE[email] = cached
        return cached

    logger.info("Pidiendo sesión mock para %s", email)
    response = _post_with_throttle_retry(
        request, _api_url(_LOGIN_PATH), {"id_token": f"mock:{email}", "access_token": ""}, f"Login mock de {email}"
    )
    if not response.ok:
        raise RuntimeError(
            f"Login mock falló para {email} ({response.status}): {response.text()}. "
            "¿El backend corre en local con MICROSOFT_AUTH_MODE=mock?"
        )
    body = response.json()
    user = body["user"]
    session: Session = {
        "access": body["access"],
        "refresh": body["refresh"],
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "firstName": user.get("first_name", ""),
            "lastName": user.get("last_name", ""),
            "role": user.get("role", ""),
        },
    }
    _MEMORY_CACHE[email] = session
    _write_session_file(email, session)
    return session


# --- API pública ----------------------------------------------------------------------------

def get_session(request: APIRequestContext, email: str) -> Session:
    """Return a valid backend session for `email` using the configured AUTH_MODE."""
    if env.AUTH_MODE == "mock":
        return _mock_session(request, email)
    if env.AUTH_MODE == "refresh":
        return _refresh_session(request, email)
    raise RuntimeError(f"AUTH_MODE desconocido: {env.AUTH_MODE!r} (usa 'refresh' o 'mock').")


def inject_session(page: Page, session: Session, *, skip_tour: bool = True) -> None:
    """Write the session into the frontend's sessionStorage before any of its scripts run.

    With `skip_tour`, the guided tours are also marked as skipped for this user so they do not
    cover the UI; pass False only in the tests of the tour itself.
    """
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(env.BASE_URL))
    refresh = session["refresh"] if env.AUTH_MODE == "mock" else _BROWSER_REFRESH_PLACEHOLDER
    values = {
        _STORAGE_KEYS["access"]: session["access"],
        _STORAGE_KEYS["refresh"]: refresh,
        _STORAGE_KEYS["user"]: json.dumps(session["user"]),
        _INJECTED_FLAG: "1",
    }
    tour_values = (
        {f"{_TOUR_STORAGE_PREFIX}{session['user']['id']}.{phase}": "skipped" for phase in _TOUR_PHASES}
        if skip_tour
        else {}
    )
    page.add_init_script(
        script=f"""
        (() => {{
            if (window.location.origin !== {json.dumps(origin)}) return;
            try {{
                if (sessionStorage.getItem({json.dumps(_INJECTED_FLAG)})) return;
                for (const [key, value] of Object.entries({json.dumps(values)})) {{
                    sessionStorage.setItem(key, value);
                }}
                for (const [key, value] of Object.entries({json.dumps(tour_values)})) {{
                    localStorage.setItem(key, value);
                }}
            }} catch (e) {{}}
        }})();
        """
    )


def bootstrap(email: str) -> None:
    """Interactive one-time login for `email`; saves the session for AUTH_MODE=refresh."""
    session = _capture_session_from_browser(email)
    with _locked(email):
        _write_session_file(email, session)
    print(f"Sesión guardada para {email} (rol {session['user'].get('role')}) en {_session_file(email)}")


# Lo que el dueño de la cuenta corre en la consola de DevTools (con sesión iniciada en el sitio).
DEVTOOLS_SNIPPET = (
    "copy(JSON.stringify({access: sessionStorage.getItem('greeniteso.access_token'), "
    "refresh: sessionStorage.getItem('greeniteso.refresh_token'), "
    "user: JSON.parse(sessionStorage.getItem('greeniteso.user'))}))"
)


def import_session(email: str, raw: str) -> None:
    """Save a session copied from DevTools for `email`, rotating its refresh token right away.

    Al canjearlo de inmediato, la copia que tiene el dueño (o el chat por donde se mandó) deja de
    servir y solo este equipo conserva un refresh token válido.
    """
    try:
        pasted = json.loads(raw)
        refresh, user = pasted["refresh"], pasted["user"]
    except Exception as exc:
        raise RuntimeError(f"El texto pegado no es la sesión esperada. En DevTools corre: {DEVTOOLS_SNIPPET}") from exc
    if not refresh or not isinstance(user, dict):
        raise RuntimeError("La sesión pegada no trae refresh token o usuario: ¿el dueño tenía la sesión iniciada?")
    if str(user.get("email", "")).lower() != email.lower():
        raise RuntimeError(f"La sesión pegada es de {user.get('email')}, se esperaba {email}.")

    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            response = _post_with_throttle_retry(request, _api_url(_REFRESH_PATH), {"refresh": refresh}, "Importar")
            if not response.ok:
                raise RuntimeError(
                    f"El backend rechazó el refresh token ({response.status}): ya se usó, expiró o el dueño "
                    "cerró sesión. Pídele que inicie sesión de nuevo y copie la sesión otra vez."
                )
            body = response.json()
        finally:
            request.dispose()
    session: Session = {"access": body["access"], "refresh": body.get("refresh", refresh), "user": user}
    with _locked(email):
        _write_session_file(email, session)
    print(f"Sesión importada para {email} (rol {user.get('role')}) en {_session_file(email)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guarda la sesión de un usuario de prueba (login manual).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--role", choices=sorted(env.TEST_USERS), help="rol de env.TEST_USERS")
    group.add_argument("--email", help="correo del usuario de prueba")
    parser.add_argument(
        "--import",
        dest="import_session",
        action="store_true",
        help="en vez de abrir el navegador, lee de stdin la sesión copiada en DevTools por el dueño de la cuenta",
    )
    args = parser.parse_args()
    target = args.email or env.TEST_USERS[args.role]
    if args.import_session:
        if sys.stdin.isatty():
            print(f"Pega la sesión de {target} (lo que copió el snippet de DevTools) y presiona Enter:")
            raw = input()
        else:
            raw = sys.stdin.read()  # p. ej. ``pbpaste | python -m src.utils.auth --role admin --import``
        if not raw.strip():
            raise SystemExit("No llegó ninguna sesión. Copia la sesión y corre: pbpaste | <este comando>")
        import_session(target, raw.strip())
    else:
        bootstrap(target)
