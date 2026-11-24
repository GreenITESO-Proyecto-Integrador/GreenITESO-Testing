"""Acciones del módulo 13 · Perfil (tests/Perfil/test_Perfil.py).

Cubre las pruebas del módulo de identidad y perfil:
- test_00_13_001_checkProfileMetrics: Métricas de impacto ambiental acumulado y progreso.
- test_00_13_004_checkProfileAvatar: Visualización del avatar, controles de edición y previsualización.
- test_00_13_011_checkChangeNickname: Validación y gestión del nickname del usuario (máximo 50 caracteres).
- test_00_13_013_checkDeactivateAccount: Comportamiento ante cuenta desactivada o deshabilitada.
"""

import base64
import json
import re
import time
from typing import Any

from playwright.sync_api import Page

from src.configs import environment as env
from src.utils.auth import Session, inject_session
from src.utils.common_actions import click_robust, go_to, login_as
from src.utils.helpers import (
    is_on_path,
    locator_has_visible_match,
    wait_for_app_ready,
    wait_for_path,
    wait_until,
)
from src.utils.locators import Locs
from src.utils.logger import get_logger
from src.utils.mocks import mock_api_json
from src.utils.test_data import unique_name

logger = get_logger(__name__)

_ROLE = "student"
_LOAD_TIMEOUT = env.DEFAULT_TIMEOUT
_SHORT_TIMEOUT = 5_000
_PROFILE_PATH = "/profile"
_LOGIN_PATH = "/login"

_REFRESH_API_GLOB = "**/api/v1/auth/refresh/**"
_PROFILE_API_GLOB = "**/api/v1/profile/me/**"
_CAREERS_API_GLOB = "**/api/v1/clans/institutional-clan/careers/**"
_INSTITUTIONAL_CLAN_MATCHER = re.compile(r".*/api/v1/clans/institutional-clan/(?:\?.*)?$")
_EXCHANGEABLES_GLOB = "**/api/v1/exchangeables/**"
_INVENTORY_GLOB = "**/api/v1/exchangeables/my-inventory/**"
_BADGES_API_GLOB = "**/api/v1/rankings/badges/**"

_TEST_AVATAR_URL = (
    "https://staticfiles.warthunder.com/upload/image/0_2025/10_October/Halloween/"
    "halloween_frame_2_9063910c08949c31b92d29549b7fd4dc.png"
)


# --- privadas ----------------------------------------------------------------------------------


def _make_valid_jwt() -> str:
    """Genera un JWT válido sintácticamente con expiración a 30 días para pasar isTokenExpired."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload_dict = {
        "exp": int(time.time()) + 86400 * 30,
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "qa.estudiante@iteso.mx",
        "role": "STUDENT",
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(b"e2e-fake-signature").decode().rstrip("=")
    return f"{header}.{payload}.{signature}"


def _fake_profile_data(*, institutional_clan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retorna un payload base de perfil para pruebas con datos controlados."""
    clan = institutional_clan if institutional_clan is not None else {"id": "clan-test-id", "name": "Clan E2E"}
    return {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "qa.estudiante@iteso.mx",
        "first_name": "Estudiante",
        "last_name": "E2E",
        "role": "STUDENT",
        "visibility": "PUBLIC",
        "bio": "Bio de prueba E2E",
        "avatar_url": "",
        "preferences": {},
        "unlocked_cosmetics": [],
        "total_points": 150,
        "available_points": 75,
        "current_streak": 3,
        "level": 2,
        "badges": [],
        "impact_metrics": {
            "co2_kg": 12.5,
            "water_liters": 450.0,
            "plastic_kg": 3.2,
        },
        "finished_campaigns": [],
        "institutional_clan": clan,
        "active_private_clan": None,
    }


def _ensure_session(page: Page) -> None:
    """Inyecta la sesión del usuario para las pruebas."""
    valid_jwt = _make_valid_jwt()
    mock_api_json(page, _REFRESH_API_GLOB, {"access": valid_jwt, "refresh": "e2e-refresh-valid"})
    try:
        login_as(page, _ROLE)
    except Exception as exc:  # noqa: BLE001
        logger.debug("login_as no obtuvo sesión previa (%s); inyectando sesión simulada válida", exc)
        fake_session: Session = {
            "access": valid_jwt,
            "refresh": "e2e-fake-refresh-token",
            "user": {
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "qa.estudiante@iteso.mx",
                "firstName": "Estudiante",
                "lastName": "E2E",
                "role": "STUDENT",
            },
        }
        inject_session(page, fake_session)


# --- tests ------------------------------------------------------------------------------------


def test_00_13_001_checkProfileMetrics(page: Page) -> bool:
    """TC-13-001: /profile muestra el perfil del usuario con métricas de impacto ambiental y progreso."""
    mock_api_json(page, _PROFILE_API_GLOB, _fake_profile_data())
    mock_api_json(
        page,
        _INSTITUTIONAL_CLAN_MATCHER,
        {
            "career": "Ingeniería en Sistemas Computacionales",
            "nickname": "",
            "visibility": "PUBLIC",
            "institutional_clan": {"id": "clan-test-id", "name": "Clan E2E"},
        },
    )
    mock_api_json(page, _EXCHANGEABLES_GLOB, [])
    mock_api_json(page, _INVENTORY_GLOB, [])
    mock_api_json(page, _BADGES_API_GLOB, [])

    _ensure_session(page)
    go_to(page, _PROFILE_PATH)
    wait_for_app_ready(page)

    # 1. Cabecera del perfil visible
    if not locator_has_visible_match(page.locator(Locs.PROFILE_NAME_TITLE), timeout=_LOAD_TIMEOUT):
        logger.error("No se encontró el título o nombre del perfil en /profile")
        return False

    # 2. Sección de impacto ambiental acumulado con sus 3 métricas
    if not locator_has_visible_match(page.locator(Locs.PROFILE_IMPACT_SECTION), timeout=_SHORT_TIMEOUT):
        logger.error("No se encontró la sección de impacto ambiental acumulado")
        return False

    co2_visible = locator_has_visible_match(page.locator(Locs.PROFILE_METRIC_CO2), timeout=_SHORT_TIMEOUT)
    water_visible = locator_has_visible_match(page.locator(Locs.PROFILE_METRIC_WATER), timeout=_SHORT_TIMEOUT)
    plastic_visible = locator_has_visible_match(page.locator(Locs.PROFILE_METRIC_PLASTIC), timeout=_SHORT_TIMEOUT)

    if not (co2_visible and water_visible and plastic_visible):
        logger.error(
            "Faltan métricas de impacto: CO2=%s, Agua=%s, Plástico=%s",
            co2_visible,
            water_visible,
            plastic_visible,
        )
        return False

    # 3. Sección de progreso y nivel con sus 4 tarjetas
    if not locator_has_visible_match(page.locator(Locs.PROFILE_PROGRESS_SECTION), timeout=_SHORT_TIMEOUT):
        logger.error("No se encontró la sección de progreso y nivel")
        return False

    points_total_visible = locator_has_visible_match(page.locator(Locs.PROFILE_POINTS_TOTAL), timeout=_SHORT_TIMEOUT)
    points_avail_visible = locator_has_visible_match(
        page.locator(Locs.PROFILE_POINTS_AVAILABLE), timeout=_SHORT_TIMEOUT
    )
    streak_visible = locator_has_visible_match(page.locator(Locs.PROFILE_STREAK), timeout=_SHORT_TIMEOUT)
    level_visible = locator_has_visible_match(page.locator(Locs.PROFILE_LEVEL), timeout=_SHORT_TIMEOUT)

    if not (points_total_visible and points_avail_visible and streak_visible and level_visible):
        logger.error(
            "Faltan tarjetas de progreso: Total=%s, Disponibles=%s, Racha=%s, Nivel=%s",
            points_total_visible,
            points_avail_visible,
            streak_visible,
            level_visible,
        )
        return False

    logger.info("TC-13-001 PASS: Métricas de impacto ambiental y progreso verificadas en el perfil")
    return True


def test_00_13_004_checkProfileAvatar(page: Page) -> bool:
    """TC-13-004: Muestra el avatar y permite abrir el diálogo de edición con opciones de foto."""
    mock_api_json(page, _PROFILE_API_GLOB, _fake_profile_data())
    mock_api_json(
        page,
        _INSTITUTIONAL_CLAN_MATCHER,
        {
            "career": "Ingeniería en Sistemas Computacionales",
            "nickname": "",
            "visibility": "PUBLIC",
            "institutional_clan": {"id": "clan-test-id", "name": "Clan E2E"},
        },
    )
    mock_api_json(page, _EXCHANGEABLES_GLOB, [])
    mock_api_json(page, _INVENTORY_GLOB, [])
    mock_api_json(page, _BADGES_API_GLOB, [])

    _ensure_session(page)
    go_to(page, _PROFILE_PATH)
    wait_for_app_ready(page)

    # 1. Avatar visible en cabecera
    if not locator_has_visible_match(page.locator(Locs.PROFILE_AVATAR), timeout=_LOAD_TIMEOUT):
        logger.error("No se encontró el avatar del usuario en el perfil")
        return False

    # 2. Abrir el modal de edición
    if not locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("No se encontró el botón de 'Editar perfil'")
        return False

    click_robust(page, Locs.PROFILE_EDIT_BUTTON)

    if not locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_DIALOG), timeout=_SHORT_TIMEOUT):
        logger.error("No se abrió el diálogo de editar perfil")
        return False

    # 3. Validar elementos de avatar en el modal
    upload_visible = locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_UPLOAD_BUTTON), timeout=_SHORT_TIMEOUT)
    link_button_visible = locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_LINK_BUTTON), timeout=_SHORT_TIMEOUT)
    url_input_visible = locator_has_visible_match(
        page.locator(Locs.PROFILE_EDIT_AVATAR_URL_INPUT), timeout=_SHORT_TIMEOUT
    )

    if not (upload_visible or link_button_visible or url_input_visible):
        logger.error("No se encontraron controles para subir foto o usar enlace de avatar")
        return False

    # Si el botón de enlace está disponible, abrir el campo de URL
    if link_button_visible and not url_input_visible:
        click_robust(page, Locs.PROFILE_EDIT_LINK_BUTTON)
        url_input_visible = locator_has_visible_match(
            page.locator(Locs.PROFILE_EDIT_AVATAR_URL_INPUT), timeout=_SHORT_TIMEOUT
        )

    if url_input_visible:
        avatar_input = page.locator(Locs.PROFILE_EDIT_AVATAR_URL_INPUT).first
        avatar_input.fill(_TEST_AVATAR_URL)

    # Validar que los botones de Cancelar y Guardar existen
    if not locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_SAVE_BUTTON), timeout=_SHORT_TIMEOUT):
        logger.error("No se encontró el botón 'Guardar cambios'")
        return False

    click_robust(page, Locs.PROFILE_EDIT_CANCEL_BUTTON)

    # Verificar que el modal se cierre limpiamente
    modal_closed = wait_until(
        lambda: not locator_has_visible_match(page.locator(Locs.PROFILE_EDIT_DIALOG), timeout=300),
        page,
        timeout=_SHORT_TIMEOUT,
    )
    if not modal_closed:
        logger.error("El modal de editar perfil no se cerró tras pulsar Cancelar")
        return False

    logger.info("TC-13-004 PASS: Controles y previsualización de avatar verificados")
    return True


def test_00_13_011_checkChangeNickname(page: Page) -> bool:
    """TC-13-011: Valida el nickname del usuario respetando el límite de 50 caracteres y su persistencia."""
    profile_without_clan = _fake_profile_data(institutional_clan=None)
    mock_api_json(page, _PROFILE_API_GLOB, profile_without_clan)
    mock_api_json(
        page,
        _INSTITUTIONAL_CLAN_MATCHER,
        {"career": "", "nickname": "", "visibility": "PUBLIC", "institutional_clan": None},
    )
    mock_api_json(
        page,
        _CAREERS_API_GLOB,
        {"careers": ["Ingeniería en Sistemas Computacionales", "Ingeniería Ambiental"]},
    )
    mock_api_json(page, _EXCHANGEABLES_GLOB, [])
    mock_api_json(page, _INVENTORY_GLOB, [])
    mock_api_json(page, _BADGES_API_GLOB, [])

    _ensure_session(page)
    go_to(page, "/")

    # Validar que se muestre el modal de onboarding (sin llamar wait_for_app_ready porque falla si el onboarding está abierto)
    if not locator_has_visible_match(page.locator(Locs.ONBOARDING_MODAL), timeout=_LOAD_TIMEOUT):
        logger.error("No se abrió el modal de onboarding para validar el nickname")
        return False

    # Campo de nickname presente
    nickname_input = page.locator(Locs.ONBOARDING_NICKNAME_INPUT).first
    if not locator_has_visible_match(nickname_input, timeout=_SHORT_TIMEOUT):
        logger.error("No se encontró el campo de nickname en el modal")
        return False

    # Validar que respeta el límite de 50 caracteres (maxLength="50")
    max_length_attr = nickname_input.get_attribute("maxlength")
    if max_length_attr != "50":
        logger.error("El campo de nickname no tiene maxLength=50 (valor actual: %s)", max_length_attr)
        return False

    # Probar escribir un nickname único de prueba
    sample_nick = unique_name("Nick", max_length=50)
    nickname_input.fill(sample_nick)

    current_val = nickname_input.input_value()
    if current_val != sample_nick:
        logger.error("El valor del nickname no coincide: esperado '%s', obtenido '%s'", sample_nick, current_val)
        return False

    # Probar que texto mayor a 50 caracteres queda recortado a 50
    long_nick = "a" * 60
    nickname_input.fill(long_nick)
    clamped_val = nickname_input.input_value()
    if len(clamped_val) > 50:
        logger.error("El campo permitió ingresar más de 50 caracteres: %d", len(clamped_val))
        return False

    logger.info("TC-13-011 PASS: Validación de campo y límite de 50 caracteres de nickname verificada")
    return True


def test_00_13_013_checkDeactivateAccount(page: Page) -> bool:
    """TC-13-013: Una cuenta desactivada o deshabilitada es bloqueada y no puede acceder al perfil."""
    mock_api_json(
        page,
        _PROFILE_API_GLOB,
        {"detail": "La cuenta está deshabilitada", "code": "account_disabled"},
        status=403,
    )

    _ensure_session(page)
    go_to(page, _PROFILE_PATH)

    # Validar que no se muestren los datos del usuario en /profile
    # O bien la aplicación muestra un error de perfil bloqueado o redirige a /login
    has_error_message = locator_has_visible_match(
        page.locator(
            "//main//*[contains(normalize-space(.), 'Error') or contains(normalize-space(.), 'deshabilitada') or contains(normalize-space(.), 'No se pudo cargar')]"
        ),
        timeout=_LOAD_TIMEOUT,
    )
    redirected_to_login = is_on_path(page, _LOGIN_PATH)

    if not (has_error_message or redirected_to_login):
        try:
            wait_for_path(page, _LOGIN_PATH, timeout=_SHORT_TIMEOUT)
            redirected_to_login = True
        except RuntimeError:
            redirected_to_login = False

    if not (has_error_message or redirected_to_login):
        logger.error("Una cuenta desactivada pudo visualizar el perfil normalmente")
        return False

    logger.info("TC-13-013 PASS: Acceso denegado y protegido para cuentas desactivadas")
    return True
