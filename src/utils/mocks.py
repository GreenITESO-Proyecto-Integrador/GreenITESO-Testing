r"""Mocks de red reutilizables por los módulos.

Úsalos SOLO para estados que las cuentas reales no pueden alcanzar (error del servidor, listas
vacías, usuario nuevo) o para interceptar difusiones que llegarían a usuarios reales (websocket).
Los caminos felices van contra el backend real.

Cada mock responde solo al método indicado; el resto de las peticiones pasan con ``route.fallback()``.

Cómo escribir `path_glob` (se compara contra la URL completa, query string incluida):

- El glob se ancla a la URL completa: ``"**/api/v1/profile/me/"`` NO coincide con ``.../me/?x=1``.
  En Playwright ≥1.5x ``?`` es literal y ``*`` no cruza ``/``, así que ``"**/api/v1/campaigns/?*"``
  coincide solo con la lista con query (no con ``/campaigns/<id>/`` ni ``/campaigns/proposals/``).
  Para algo más fino usa una regex (``re.compile(r"/api/v1/campaigns/(\?.*)?$")``) o una función
  ``lambda url: "/api/v1/campaigns/" in url``.
- Acepta ``str`` (glob), ``re.Pattern`` o ``Callable[[str], bool]``.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, Request, Route, WebSocketRoute

from src.configs import environment as env
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CORS_HEADERS = {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "authorization, content-type",
    "access-control-allow-methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
}
UrlMatcher = str | re.Pattern[str] | Callable[[str], bool]
_ERROR_BODY = {"detail": "Error simulado por la prueba E2E."}


class RouteHandle:
    """Handle of a mock: `restore()` removes it so the real backend answers again."""

    def __init__(self, page: Page, path_glob: UrlMatcher) -> None:
        self._page = page
        self._glob = path_glob
        self._handler: Callable[[Route], None] | None = None
        self.requests: list[Request] = []

    def _attach(self, handler: Callable[[Route], None]) -> None:
        self._handler = handler
        self._page.route(self._glob, handler)

    def restore(self) -> None:
        """Remove this mock; later requests reach the real backend again."""
        if self._handler is not None:
            self._page.unroute(self._glob, self._handler)
            self._handler = None


def _json_route(handle: RouteHandle, method: str, status: int, body: Any) -> Callable[[Route], None]:
    payload = json.dumps(body, ensure_ascii=False)

    def handler(route: Route) -> None:
        request = route.request
        # Preflight CORS de la peticion simulada: se contesta aquí, sin llegar al backend.
        if request.method == "OPTIONS":
            route.fulfill(status=204, headers=_CORS_HEADERS)
            return
        if request.method != method:
            route.fallback()
            return
        handle.requests.append(request)
        logger.debug("Mock %s %s → %s", method, request.url, status)
        route.fulfill(
            status=status,
            headers=_CORS_HEADERS,
            content_type="application/json",
            body=payload,
        )

    return handler


def mock_api_error(page: Page, path_glob: UrlMatcher, *, status: int = 500, method: str = "GET") -> RouteHandle:
    """Answer `method` requests matching `path_glob` with an error status (for error + retry flows).

    `path_glob` is a glob, a regex or a predicate over the full URL (query string included; see module docstring).
    """
    handle = RouteHandle(page, path_glob)
    handle._attach(_json_route(handle, method, status, _ERROR_BODY))
    return handle


def mock_api_json(
    page: Page, path_glob: UrlMatcher, body: Any, *, status: int = 200, method: str = "GET"
) -> RouteHandle:
    """Answer `method` requests matching `path_glob` with `body` (empty states, new user, intercepts).

    `path_glob` is a glob, a regex or a predicate over the full URL (query string included; see module docstring).
    """
    handle = RouteHandle(page, path_glob)
    handle._attach(_json_route(handle, method, status, body))
    return handle


def capture_json_response(
    page: Page,
    url_predicate: Callable[[str], bool],
    action: Callable[[], None],
    *,
    timeout: int = env.DEFAULT_TIMEOUT,
) -> Any:
    """Run `action` and return the JSON body of the GET response the UI consumed for `url_predicate`.

    Sirve para comparar la UI contra el cuerpo exacto que renderizó, sin depender de datos que
    otros módulos estén escribiendo en paralelo.
    """
    with page.expect_response(
        lambda response: url_predicate(response.url) and response.request.method == "GET",
        timeout=timeout,
    ) as response_info:
        action()
    response = response_info.value
    if not response.ok:
        logger.debug("capture_json_response: %s → %s", response.url, response.status)
    return response.json()


class FakeNotificationsSocket:
    """Stand-in for the notifications websocket: answers auth and ping, and pushes notifications."""

    def __init__(self, unread: int) -> None:
        self._unread = unread
        self._ws: WebSocketRoute | None = None

    def _on_connect(self, ws: WebSocketRoute) -> None:
        self._ws = ws
        ws.on_message(self._on_message)

    def _on_message(self, message: str | bytes) -> None:
        if self._ws is None:
            return
        text = message.decode() if isinstance(message, bytes) else message
        try:
            frame = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("Socket simulado: mensaje no JSON ignorado")
            return
        kind = frame.get("type") if isinstance(frame, dict) else None
        if kind == "auth":
            self._ws.send(json.dumps({"type": "auth.ok", "unread_count": self._unread}))
        elif kind == "ping":
            self._ws.send(json.dumps({"type": "pong"}))

    @property
    def connected(self) -> bool:
        """True once the page has opened the socket."""
        return self._ws is not None

    def push(self, notification: dict) -> None:
        """Send a ``notification.created`` event to the page, as the backend does."""
        if self._ws is None:
            raise RuntimeError("El socket de notificaciones todavía no se conecta; espera a `connected`.")
        self._ws.send(json.dumps({"type": "notification.created", "notification": notification}))


def fake_notifications_socket(page: Page, *, unread: int = 0) -> FakeNotificationsSocket:
    """Replace the notifications websocket of `page`. Call it BEFORE go_to."""
    fake = FakeNotificationsSocket(unread)
    page.route_web_socket(re.compile(r"/ws/notifications/"), fake._on_connect)
    return fake
