"""Keep this opt-in acceptance suite on its disposable local stack."""

import pytest

from src.configs import environment as env


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.collectonly:
        return
    if (
        env.BASE_URL != "http://localhost:8080"
        or env.API_BASE_URL != "http://localhost:8080"
        or env.AUTH_MODE != "mock"
        or env.E2E_CLEANUP
    ):
        raise pytest.UsageError(
            "release_qa requires the isolated localhost:8080 stack, AUTH_MODE=mock and E2E_CLEANUP=false."
        )
