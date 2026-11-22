"""Crea los usuarios de prueba en el stack desechable (ci/stack) y les deja el onboarding hecho.

Solo usa la biblioteca estándar, para correr antes de instalar nada. Lee los correos de las variables
TEST_*_EMAIL (las mismas que usan las pruebas) y la URL de BASE_URL.

- Cada usuario se crea con su primer login mock (``id_token = "mock:<email>"``).
- El onboarding (carrera + nickname) se completa por API para que el OnboardingGate no tape la UI.
- Imprime los correos que deben ser ADMIN; up.sh les asigna el rol con ``manage.py assign_user_role``.

Uso: python ci/stack/seed_users.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
ROLES = {
    "student": os.environ.get("TEST_STUDENT_EMAIL", "e2e.student@iteso.mx"),
    "admin": os.environ.get("TEST_ADMIN_EMAIL", "e2e.admin@iteso.mx"),
    "leader": os.environ.get("TEST_LEADER_EMAIL", "e2e.leader@iteso.mx"),
    "campaign_leader": os.environ.get("TEST_CAMPAIGN_LEADER_EMAIL", "e2e.campaign.leader@iteso.mx"),
}


def _call(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> dict:
    request = urllib.request.Request(f"{BASE_URL}{path}", method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, data, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} → {exc.code}: {exc.read().decode()[:300]}") from exc
    return json.loads(raw) if raw else {}


def _seed(role: str, email: str) -> None:
    token = _call("POST", "/api/v1/auth/login/", body={"id_token": f"mock:{email}", "access_token": ""})["access"]
    state = _call("GET", "/api/v1/clans/institutional-clan/", token=token)
    if state.get("onboarding_completed_at"):
        print(f"{role}: {email} ya tenía onboarding", file=sys.stderr)
        return
    careers = _call("GET", "/api/v1/clans/institutional-clan/careers/", token=token)["careers"]
    nickname = f"e2e_{role}"[:50]
    _call("POST", "/api/v1/clans/institutional-clan/", token=token, body={"career": careers[0], "nickname": nickname})
    print(f"{role}: {email} creado con onboarding ({careers[0]}, {nickname})", file=sys.stderr)


def main() -> None:
    for role, email in dict.fromkeys(ROLES.items()):
        _seed(role, email)
    # stdout: solo los correos que necesitan rol ADMIN, para que up.sh los asigne.
    print(ROLES["admin"])


if __name__ == "__main__":
    main()
