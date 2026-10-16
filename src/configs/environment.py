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


BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
HEADLESS = _bool("HEADLESS", True)
SLOW_MO = int(os.getenv("SLOW_MO", "0"))
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "15000"))
NAVIGATION_TIMEOUT = int(os.getenv("NAVIGATION_TIMEOUT", "30000"))

TEST_USER = os.getenv("TEST_USER", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")

REPORTING_DIR = ROOT_DIR / "reporting"
SCREENSHOTS_DIR = REPORTING_DIR / "screenshots"
LOGS_DIR = REPORTING_DIR / "logs"
ALLURE_RESULTS_DIR = REPORTING_DIR / "allure-results"
