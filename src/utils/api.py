"""Cliente de la API para preparar datos y leer valores esperados (y para la limpieza al final).

Un token (bearer) por rol de prueba, tomado de la sesión de auth.get_session. Las acciones de
un módulo usan ``api_for_page(page)``, que comparte el contexto de Playwright del test.
"""

from collections.abc import Iterator, Sequence
from typing import Any

from playwright.sync_api import APIRequestContext, APIResponse, Page

from src.configs import environment as env
from src.utils.auth import _is_fresh, get_session
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_PAGES = 20
_PAGE_CACHE: dict[int, tuple[Page, "ApiClient"]] = {}


class ApiClient:
    """Authenticated API client: one APIRequestContext, a bearer token per test-user role."""

    def __init__(self, request: APIRequestContext) -> None:
        self.request = request
        self.tokens: dict[str, str] = {}
        self._user_ids: dict[str, str] = {}
        # Los tokens de acceso duran 60 min: ``_token`` los renueva con get_session si ya vencieron.
        for role, email in env.TEST_USERS.items():
            try:
                session = get_session(request, email)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sin sesión para %s (%s): %s", role, email, exc)
                continue
            self.tokens[role] = session["access"]
            if session["user"].get("id"):
                self._user_ids[role] = str(session["user"]["id"])

    def _token(self, role: str) -> str:
        """Return the access token of `role`, renewing it through get_session when it is about to expire."""
        token = self.tokens[role]
        if _is_fresh(token):
            return token
        logger.debug("Token de %s por vencer; se renueva la sesión", role)
        token = get_session(self.request, env.TEST_USERS[role])["access"]
        self.tokens[role] = token
        return token

    def call(
        self,
        role: str,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        params: dict | None = None,
        multipart: dict | None = None,
    ) -> APIResponse:
        """Send one request as `role`; `path` is absolute (e.g. ``/api/v1/campaigns/``)."""
        if role not in self.tokens:
            raise RuntimeError(f"no hay sesión guardada de {role} ({env.TEST_USERS.get(role)})")
        url = env.API_BASE_URL.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self._token(role)}"}
        return self.request.fetch(url, method=method, headers=headers, data=data, params=params, multipart=multipart)

    def pages(self, role: str, path: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item of a list endpoint, paginated (DRF ``results``/``next``) or not."""
        for page in range(1, _MAX_PAGES + 1):
            response = self.call(role, "GET", path, params={**(params or {}), "page": page})
            if not response.ok:
                logger.debug("GET %s página %s → %s", path, page, response.status)
                return
            body = response.json()
            if isinstance(body, list):
                yield from body
                return
            yield from body.get("results", [])
            if not body.get("next"):
                return

    def json(
        self,
        role: str,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        params: dict | None = None,
        expected: Sequence[int] = (200, 201),
    ) -> Any:
        """Call the API and return the JSON body (None for 204); raise RuntimeError if the status is not expected."""
        response = self.call(role, method, path, data=data, params=params)
        if response.status not in expected:
            raise RuntimeError(f"{method} {path} → {response.status}: {response.text()[:300]}")
        if response.status == 204:
            return None
        return response.json()

    def user_id(self, role: str) -> str:
        """Return the id of the user behind `role` (from the session, else from the profile)."""
        if role not in self._user_ids:
            profile = self.json(role, "GET", "/api/v1/profile/me/")
            self._user_ids[role] = str(profile.get("user_id") or profile["id"])
        return self._user_ids[role]


def api_for_page(page: Page) -> ApiClient:
    """ApiClient built on page.request (shares the test's Playwright context); cached per page."""
    cached = _PAGE_CACHE.get(id(page))
    # Se guarda la página junto al cliente: así un id reciclado por Python no devuelve un cliente viejo.
    if cached and cached[0] is page:
        return cached[1]
    client = ApiClient(page.request)
    _PAGE_CACHE[id(page)] = (page, client)
    return client
