"""Configuración del entorno de pruebas, leída desde variables de entorno / .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


PRODUCTION_URL = "https://greeniteso-production-frontend-682248660949.northamerica-south1.run.app"
BASE_URL = os.getenv("BASE_URL", PRODUCTION_URL)
HEADLESS = _bool("HEADLESS", True)
SLOW_MO = int(os.getenv("SLOW_MO", "0"))
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "15000"))
NAVIGATION_TIMEOUT = int(os.getenv("NAVIGATION_TIMEOUT", "30000"))

# En los ambientes desplegados nginx manda /api/ al backend, así que la API vive en el mismo origen.
API_BASE_URL = os.getenv("API_BASE_URL") or BASE_URL

# refresh = ambientes desplegados (login manual una vez por usuario); mock = stack local.
AUTH_MODE = os.getenv("AUTH_MODE", "refresh").strip().lower()
# Fuera del repo para que los tokens nunca se suban y sobrevivan entre builds de Jenkins.
AUTH_STATE_DIR = Path(os.getenv("AUTH_STATE_DIR", str(Path.home() / ".greeniteso-e2e" / "auth"))).expanduser()

# Limpieza de los datos marcados al final de la corrida (src/utils/test_data.py). Apágala solo para
# depurar: lo que no se limpie lo borra la siguiente corrida después de unas horas.
E2E_CLEANUP = _bool("E2E_CLEANUP", True)

# Cuentas de prueba por rol. En AUTH_MODE=refresh deben ser cuentas @iteso.mx reales.
TEST_USERS = {
    "student": os.getenv("TEST_STUDENT_EMAIL", "qa.estudiante@iteso.mx"),
    "admin": os.getenv("TEST_ADMIN_EMAIL", "qa.admin@iteso.mx"),
    "leader": os.getenv("TEST_LEADER_EMAIL", "qa.lider@iteso.mx"),
}

REPORTING_DIR = ROOT_DIR / "reporting"
SCREENSHOTS_DIR = REPORTING_DIR / "screenshots"
LOGS_DIR = REPORTING_DIR / "logs"
ALLURE_RESULTS_DIR = REPORTING_DIR / "allure-results"
