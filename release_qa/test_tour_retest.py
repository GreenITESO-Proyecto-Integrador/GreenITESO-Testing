"""Recheck T1-15 via first-run handoff and explicit replay against localhost."""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from release_qa import test_final_identity, test_release_tour
from release_qa.test_release_tour import CAMPAIGN_STEPS, GENERAL_STEPS, assert_step, first_login, replay
from release_qa.test_team2_acceptance import api, db_read_or_seed

browser_context_args = test_final_identity.browser_context_args
isolated_stack = test_release_tour.isolated_stack
journey = test_release_tour.journey


@pytest.mark.parametrize("entry", ["automatic", "replay"])
def test_tour_completion_recheck(journey, entry, browser_name):
    page, _ = journey
    output = Path(os.getenv("TOUR_RETEST_OUTPUT", "reporting/final-peer-qa/tour"))
    output.mkdir(parents=True, exist_ok=True)
    prefix = output / f"{browser_name}-{entry}"
    seen = []
    first_login(page)
    seed = os.environ.get("TOUR_SEED_CAMPAIGN") == "1"
    if seed:
        user_id = api(page, "/api/v1/profile/me/")["user_id"]
        db_read_or_seed(f'''
import json
from datetime import timedelta
from django.utils import timezone
from green_iteso.campaigns.models import Campaign
now = timezone.now()
Campaign.objects.get_or_create(title="Campaña de muestra para el recorrido", defaults={{
    "scope": "GLOBAL", "status": "IN_PROGRESS", "creator_id": {user_id!r},
    "start_date": now-timedelta(days=1), "end_date": now+timedelta(days=1),
}})
print(json.dumps(True))
''')
    for index, (label, path) in enumerate(GENERAL_STEPS):
        assert_step(page, label, path)
        button = "Finalizar" if index == len(GENERAL_STEPS) - 1 else f"Siguiente ({index + 1} de 6)"
        page.get_by_role("button", name=button, exact=True).click()
        seen.append(f"General {index + 1}/6")
    if entry == "replay":
        assert_step(page, CAMPAIGN_STEPS[0], "/campaigns")
        page.get_by_role("button", name="Saltar", exact=True).click()
        replay(page, "Recorrido de campañas")
    if seed:
        expect(page.get_by_text("Campaña de muestra para el recorrido", exact=True).first).to_be_visible()
    for index, label in enumerate(CAMPAIGN_STEPS):
        button = "Finalizar" if index == 4 else f"Siguiente ({index + 1} de 5)"
        control = page.get_by_role("button", name=button, exact=True)
        try:
            expect(control).to_be_visible(timeout=8000)
            assert_step(page, label, "/campaigns")
        except AssertionError:
            page.screenshot(path=f"{prefix}-interrumpido.png")
            target = page.locator('[data-tour="campaigns-create"]')
            state = {
                "entry": entry, "browser": browser_name, "steps": seen,
                "expected_step": index + 1,
                "create_button_present": target.count() == 1,
                "visible_tour_buttons": page.get_by_role("button", name="Finalizar", exact=True).count(),
                "scroll_y": page.evaluate("window.scrollY"),
                "viewport_height": page.evaluate("window.innerHeight"),
                "target_y": target.evaluate("el => el.getBoundingClientRect().top") if target.count() else None,
                "completed": page.evaluate("Object.entries(localStorage).some(([k,v]) => k.endsWith('.campaigns') && v === 'completed')"),
            }
            Path(f"{prefix}.json").write_text(json.dumps(state, indent=2))
            pytest.fail(f"Campaign step {index + 1} unavailable after {seen[-1]}", pytrace=False)
        seen.append(f"Campañas {index + 1}/5")
        if index >= 1 and os.environ.get("TOUR_CAPTURE_IN_VIEWPORT") == "1":
            control.scroll_into_view_if_needed()
            expect(control).to_be_in_viewport()
            page.screenshot(path=f"{prefix}-paso-{index + 1}.png", animations="disabled")
        elif index >= 1:
            page.screenshot(path=f"{prefix}-paso-{index + 1}.png")
        control.click()
    expect(page.get_by_role("button", name="Finalizar", exact=True)).to_have_count(0)
    completed = page.evaluate("Object.entries(localStorage).some(([k,v]) => k.endsWith('.campaigns') && v === 'completed')")
    assert completed
    Path(f"{prefix}.json").write_text(json.dumps({"entry": entry, "browser": browser_name, "steps": seen, "completed": completed}, indent=2))
