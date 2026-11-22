"""Datos de prueba marcados y limpieza al final de la corrida (pruebas contra prod).

Todo lo que un test crea (posts, clanes, campañas, nicknames, ...) debe llevar el marcador de la
corrida, que se obtiene con ``unique_name("Clan")`` → ``"E2E-2611061530-ab12 Clan 1"``. Al terminar,
``cleanup_run`` (lo llama conftest.py en el proceso controlador, una vez por corrida) usa la API con
las sesiones de los usuarios de prueba para quitar lo que tenga el marcador:

- posts del feed marcados → DELETE (como admin)
- propuestas de campaña marcadas y pendientes → rechazar (como admin)
- campañas marcadas → iniciar y finalizar (no hay DELETE)
- clanes marcados → disolver (como su líder); después de las campañas, porque al disolverlo
  se ocultan sus campañas PRIVATE
- membresías temporales (``register_membership``: un usuario de prueba que se unió a un clan sin
  marcador) → salir del clan, después de las campañas
- action logs de los usuarios de prueba creados durante la corrida → rechazar (como admin; revierte puntos)
- notificaciones marcadas (mensaje o título) → DELETE, soft delete (cada usuario de prueba); al final,
  porque rechazar propuestas y disolver clanes también genera notificaciones con el marcador
- perfil de cada usuario de prueba (bio, preferencias, visibilidad, avatar) → se restaura a como estaba

Al iniciar también se limpian los marcadores de corridas viejas que no terminaron (más de
``_STALE_AFTER`` horas), sin tocar los de otra corrida que pueda estar en curso.

Lo que NO se puede deshacer: canjes en la tienda, campañas finalizadas (quedan en el historial),
notificaciones que les llegaron a usuarios reales, el costo de cambiar el nickname, propuestas de
campaña rechazadas (no hay DELETE; quedan como REJECTED) y las imágenes del feed que se subieron pero
nunca se adjuntaron a un post (las de un post se borran junto con él).
"""

import json
import re
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from src.configs import environment as env
from src.utils.api import ApiClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MARKER_PREFIX = "E2E-"
_RUN_TS_FORMAT = "%y%m%d%H%M"
_MARKER_RE = re.compile(rf"{_MARKER_PREFIX}(\d{{10}})-[0-9a-f]{{4}}")
_STALE_AFTER = timedelta(hours=3)
_MAX_PAGES = 20
# Margen para el redondeo de created_at y la diferencia de reloj entre el agente y el servidor.
_CLOCK_MARGIN = timedelta(minutes=2)
_REJECTION_REASON = "Limpieza automática de datos de prueba E2E"
_PROFILE_FIELDS = ("bio", "preferences", "visibility", "avatar_url")

_RUN_ID: str | None = None
_COUNTER = count(1)


# --- marcador de la corrida -----------------------------------------------------------------

def new_run_id() -> str:
    """Create a run marker such as ``E2E-2611061530-ab12`` (UTC timestamp + random suffix)."""
    return f"{_MARKER_PREFIX}{datetime.now(UTC).strftime(_RUN_TS_FORMAT)}-{secrets.token_hex(2)}"


def set_run_id(run_id: str) -> None:
    """Fix the run marker for this process (the controller passes it to every xdist worker)."""
    global _RUN_ID
    _RUN_ID = run_id


def run_id() -> str:
    """Return this run's marker, creating one if the process has none yet."""
    if _RUN_ID is None:
        set_run_id(new_run_id())
    return _RUN_ID  # type: ignore[return-value]


def unique_name(label: str, *, max_length: int = 100) -> str:
    """Build a unique, marked name for test data: ``"<marker> <label> <n>"`` cut to `max_length`.

    Límites del backend: nickname 50, nombre de clan 100, título de campaña 150, bio 500.
    """
    # El contador es por proceso: con xdist se le antepone el worker para no repetir nombres entre módulos.
    worker = f"{env.XDIST_WORKER}-" if env.XDIST_WORKER else ""
    suffix = f" {worker}{next(_COUNTER)}"
    base = f"{run_id()} {label}"
    return base[: max_length - len(suffix)] + suffix


def is_marked(text: str | None, *, marker: str | None = None) -> bool:
    """Tell whether `text` carries `marker` (or any E2E marker when `marker` is None)."""
    if not text:
        return False
    return marker in text if marker else bool(_MARKER_RE.search(text))


def _is_stale_marker(text: str | None, *, now: datetime) -> bool:
    match = _MARKER_RE.search(text or "")
    if not match:
        return False
    started = datetime.strptime(match.group(1), _RUN_TS_FORMAT).replace(tzinfo=UTC)
    return now - started > _STALE_AFTER


# --- pasos de limpieza ----------------------------------------------------------------------

class _Report:
    def __init__(self) -> None:
        self.done: dict[str, int] = {}
        self.failed: list[str] = []

    def ok(self, kind: str) -> None:
        self.done[kind] = self.done.get(kind, 0) + 1

    def fail(self, what: str) -> None:
        logger.warning("Limpieza: no se pudo %s", what)
        self.failed.append(what)


def _clean_feed(api: ApiClient, should_clean: Callable[[str | None], bool], report: _Report) -> None:
    posts = [p for p in api.pages("admin", "/api/v1/feed/") if should_clean(p.get("content"))]
    for post in posts:
        response = api.call("admin", "DELETE", f"/api/v1/feed/{post['id']}/")
        if response.ok or response.status == 404:
            report.ok("posts borrados")
        else:
            report.fail(f"borrar el post {post['id']} ({response.status})")


def _clean_clans(api: ApiClient, should_clean: Callable[[str | None], bool], report: _Report) -> None:
    clans = [c for c in api.pages("admin", "/api/v1/clans/", {"search": _MARKER_PREFIX}) if should_clean(c.get("name"))]
    for clan in clans:
        # Solo el líder actual puede disolverlo; se prueba con cada usuario de prueba.
        for role in api.tokens:
            response = api.call(role, "DELETE", f"/api/v1/clans/{clan['id']}/")
            if response.ok or response.status == 404:
                report.ok("clanes disueltos")
                break
        else:
            report.fail(f"disolver el clan {clan['name']!r}")


def _clean_campaigns(api: ApiClient, should_clean: Callable[[str | None], bool], report: _Report) -> None:
    for proposal in api.pages("admin", "/api/v1/campaigns/proposals/", {"approval_status": "PENDING"}):
        if not should_clean(proposal.get("title")):
            continue
        response = api.call(
            "admin", "POST", f"/api/v1/campaigns/proposals/{proposal['id']}/reject/",
            data={"rejection_reason": _REJECTION_REASON},
        )
        if response.ok:
            report.ok("propuestas rechazadas")
        else:
            report.fail(f"rechazar la propuesta {proposal.get('title')!r} ({response.status})")

    seen: set[str] = set()
    for role in api.tokens:
        for campaign in api.pages(role, "/api/v1/campaigns/"):
            if campaign["id"] in seen or not should_clean(campaign.get("title")):
                continue
            if campaign.get("status") == "FINISHED" or not campaign.get("can_manage"):
                continue
            seen.add(campaign["id"])
            steps = ["start", "finish"] if campaign.get("status") == "PROMOTION" else ["finish"]
            for step in steps:
                response = api.call(role, "POST", f"/api/v1/campaigns/{campaign['id']}/{step}/")
                if not response.ok:
                    report.fail(f"{step} la campaña {campaign.get('title')!r} ({response.status})")
                    break
            else:
                report.ok("campañas finalizadas")


def _clean_notifications(api: ApiClient, should_clean: Callable[[str | None], bool], report: _Report) -> None:
    """Soft-delete the notifications that carry the marker (no admin needed; each user sees its own)."""
    for role in api.tokens:
        marked = [
            n for n in api.pages(role, "/api/v1/notifications/")
            if should_clean(n.get("message")) or should_clean(n.get("title"))
        ]
        for notification in marked:
            response = api.call(role, "DELETE", f"/api/v1/notifications/{notification['id']}/")
            if response.ok or response.status == 404:
                report.ok("notificaciones borradas")
            else:
                report.fail(f"borrar la notificación {notification['id']} de {role} ({response.status})")


def _clean_action_logs(api: ApiClient, since: datetime, report: _Report) -> None:
    for role in api.tokens:
        for log in api.pages(role, "/api/v1/action-logs/mine/"):
            created = datetime.fromisoformat(log["created_at"])
            if created < since or log.get("status") == "REJECTED":
                continue
            response = api.call(
                "admin", "PATCH", f"/api/v1/action-logs/{log['id']}/audit/",
                data={"status": "REJECTED", "rejection_reason": _REJECTION_REASON},
            )
            # 409: los puntos ya se gastaron (p. ej. en la tienda) y no se pueden revertir.
            if response.ok:
                report.ok("action logs rechazados")
            else:
                report.fail(f"rechazar el action log {log['id']} de {role} ({response.status})")


# --- perfil: foto antes de la corrida y restauración al final -------------------------------

def _profile_snapshot_file(role: str) -> Path:
    return env.AUTH_STATE_DIR / f"{env.TEST_USERS[role].lower()}.profile.json"


def _snapshot_profiles(api: ApiClient, report: _Report) -> None:
    for role in api.tokens:
        path = _profile_snapshot_file(role)
        if path.exists():
            # Una corrida anterior no terminó: primero regresa el perfil a como estaba.
            _restore_profile(api, role, report)
        response = api.call(role, "GET", "/api/v1/profile/me/")
        if not response.ok:
            report.fail(f"leer el perfil de {role} ({response.status})")
            continue
        body = response.json()
        path.write_text(json.dumps({k: body.get(k) for k in _PROFILE_FIELDS if k in body}), encoding="utf-8")


def _restore_profile(api: ApiClient, role: str, report: _Report) -> None:
    path = _profile_snapshot_file(role)
    if not path.exists():
        return
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    current = api.call(role, "GET", "/api/v1/profile/me/")
    if current.ok:
        # Solo se manda lo que cambió: el backend rechaza reenviar avatares externos sin extensión
        # (p. ej. la foto de Microsoft) aunque sean los mismos que ya tiene.
        body = current.json()
        snapshot = {k: v for k, v in snapshot.items() if body.get(k) != v}
    if not snapshot:
        path.unlink()
        report.ok("perfiles sin cambios")
        return
    response = api.call(role, "PATCH", "/api/v1/profile/me/", data=snapshot)
    if response.ok:
        path.unlink()
        report.ok("perfiles restaurados")
    else:
        report.fail(f"restaurar el perfil de {role} ({response.status}: {response.text()[:200]})")


# --- membresías temporales en clanes ajenos a la corrida -------------------------------------

def _memberships_file(role: str) -> Path:
    return env.AUTH_STATE_DIR / f"{env.TEST_USERS[role].lower()}.memberships.json"


def register_membership(role: str, clan_id: str) -> None:
    """Record that `role` joined an unmarked clan during the run, so cleanup makes it leave again."""
    path = _memberships_file(role)
    clans = set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()
    clans.add(clan_id)
    path.write_text(json.dumps(sorted(clans)), encoding="utf-8")


def _leave_memberships(api: ApiClient, report: _Report) -> None:
    for role in api.tokens:
        path = _memberships_file(role)
        if not path.exists():
            continue
        pending = []
        for clan_id in json.loads(path.read_text(encoding="utf-8")):
            response = api.call(role, "POST", f"/api/v1/clans/{clan_id}/leave/")
            # 400 = ya no es miembro; 404 = el clan ya no existe. En los dos casos no queda nada.
            if response.ok or response.status in (400, 404):
                report.ok("membresías temporales dejadas")
            else:
                pending.append(clan_id)
                report.fail(f"{role} no pudo salir del clan {clan_id} ({response.status})")
        if pending:
            path.write_text(json.dumps(pending), encoding="utf-8")
        else:
            path.unlink()


# --- punto de entrada -----------------------------------------------------------------------

def _with_api(action: Callable[[ApiClient], None], report: _Report) -> None:
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            api = ApiClient(request)
            if not api.tokens:
                report.fail("limpiar: no hay sesiones guardadas de los usuarios de prueba")
                return
            action(api)
        finally:
            request.dispose()


def _require_admin(api: ApiClient, report: _Report) -> bool:
    """Feed, clans, campaigns and action logs are listed/cleaned as admin; skip them all at once without it."""
    if "admin" in api.tokens:
        return True
    report.fail("limpiar feed, clanes, campañas y action logs: falta la sesión de admin")
    return False


def _run_step(report: _Report, name: str, step: Callable[[], None]) -> None:
    try:
        step()
    except Exception as exc:  # noqa: BLE001  (la limpieza nunca debe tumbar la corrida)
        report.fail(f"{name}: {exc}")


def prepare_run() -> dict[str, Any]:
    """Before the run: clean data of stale, unfinished runs and snapshot the test users' profiles."""
    report = _Report()
    now = datetime.now(UTC)

    def stale(text: str | None) -> bool:
        return _is_stale_marker(text, now=now)

    def action(api: ApiClient) -> None:
        _run_step(report, "restaurar/guardar perfiles", lambda: _snapshot_profiles(api, report))
        # Campañas antes que clanes: al disolver un clan se ocultan sus campañas PRIVATE.
        has_admin = _require_admin(api, report)
        if has_admin:
            _run_step(report, "limpiar feed viejo", lambda: _clean_feed(api, stale, report))
            _run_step(report, "limpiar campañas viejas", lambda: _clean_campaigns(api, stale, report))
        # Una corrida anterior que no terminó pudo dejar membresías temporales.
        _run_step(report, "dejar membresías temporales", lambda: _leave_memberships(api, report))
        if has_admin:
            _run_step(report, "limpiar clanes viejos", lambda: _clean_clans(api, stale, report))
        # Al final: rechazar propuestas y disolver clanes también genera notificaciones con el marcador.
        _run_step(report, "limpiar notificaciones viejas", lambda: _clean_notifications(api, stale, report))

    _run_step(report, "preparar la corrida", lambda: _with_api(action, report))
    logger.info("Preparación E2E: %s; fallas: %s", report.done or "nada que limpiar", len(report.failed))
    return {"done": report.done, "failed": report.failed}


def cleanup_run(marker: str, *, started_at: float) -> dict[str, Any]:
    """After the run: remove everything carrying `marker` and restore the test users' profiles."""
    report = _Report()
    since = datetime.fromtimestamp(started_at, UTC) - _CLOCK_MARGIN

    def mine(text: str | None) -> bool:
        return is_marked(text, marker=marker)

    def action(api: ApiClient) -> None:
        # Campañas antes que clanes: al disolver un clan se ocultan sus campañas PRIVATE.
        has_admin = _require_admin(api, report)
        if has_admin:
            _run_step(report, "limpiar feed", lambda: _clean_feed(api, mine, report))
            _run_step(report, "limpiar campañas", lambda: _clean_campaigns(api, mine, report))
        # Después de finalizar las campañas: salir antes ocultaría las PRIVATE de ese clan.
        _run_step(report, "dejar membresías temporales", lambda: _leave_memberships(api, report))
        if has_admin:
            _run_step(report, "limpiar clanes", lambda: _clean_clans(api, mine, report))
            _run_step(report, "rechazar action logs", lambda: _clean_action_logs(api, since, report))
        # Al final: rechazar propuestas y disolver clanes también genera notificaciones con el marcador.
        _run_step(report, "limpiar notificaciones", lambda: _clean_notifications(api, mine, report))
        for role in api.tokens:
            _run_step(report, f"restaurar perfil de {role}", lambda r=role: _restore_profile(api, r, report))

    t0 = time.monotonic()
    _run_step(report, "limpiar la corrida", lambda: _with_api(action, report))
    summary = {
        "marker": marker,
        "done": report.done,
        "failed": report.failed,
        "seconds": round(time.monotonic() - t0, 1),
        "irreversible": [
            "canjes en la tienda",
            "campañas finalizadas (quedan en el historial)",
            "notificaciones enviadas a usuarios reales",
            "costo de cambiar el nickname",
            "propuestas de campaña rechazadas (no hay DELETE; quedan como REJECTED)",
            "imágenes subidas al feed que no llegaron a un post (las de un post se borran con él)",
        ],
    }
    env.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (env.LOGS_DIR / f"cleanup_{marker}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), "utf-8")
    logger.info("Limpieza E2E de %s: %s; fallas: %s", marker, report.done or "nada", len(report.failed))
    return summary
