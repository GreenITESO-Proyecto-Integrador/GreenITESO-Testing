# Dashboard test coverage

## Scope

This document describes the automated coverage for the Dashboard module (Module 03, `/` and `/home`) in `tests/Dashboard/`.

## Executable cases

| Case | Coverage | Test layer |
| --- | --- | --- |
| TC-03-001 | Five impact metrics match `profile/me` and es-MX formatting. | Real API |
| TC-03-002 | The trend has three charts and four matching week labels. | Real API |
| TC-03-003 | Active missions show campaign titles, targets, points, progress and register-action navigation. | Real API |
| TC-03-004 | State/scope filters, no-match state and campaign pagination behave according to API data. | Real API |
| TC-03-005 | A new-user profile, trend and campaign list show their empty/zero states. | Mocked UI state |
| TC-03-006 | An administrator sees the plain dashboard and no student sections. | Real API |
| TC-03-007 | Profile load failure shows an error and retry recovers. | Mocked error/retry |
| TC-03-008 | Trend load failure shows an error and retry recovers. | Mocked error/retry |
| TC-03-009 | Campaign and mission load failures show errors and retry recovers. | Mocked error/retry |
| TC-03-010 | A participating campaign opens its detail dialog. | Real API |
| TC-03-011 | Reload preserves the authenticated dashboard and reloaded profile metrics. | Real API |
| TC-03-012 | Core dashboard sections render at 390 px without horizontal overflow. | Real API/layout |

## Execution rules

Run module cases with:

```sh
uv run pytest tests/Dashboard/test_Dashboard.py
uv run pytest tests/Dashboard/test_Dashboard.py -m sanity
uv run pytest tests/Dashboard/test_Dashboard.py -m full
```

The cases are module-local and should run on the same worker. Cases marked `sanity` are intended for a fast daily run; `full` includes the complete Dashboard module.

Mocked cases cover states that require synthetic data or server failures. They prove frontend behavior, not backend availability. Real-API cases compare visible values with the response consumed by the page or verify navigation and persistence; they do not prove the correctness of backend calculations.

## Environment record

Before an execution, record:

- Frontend and backend commit SHAs.
- Environment and data source.
- Browser and viewport.
- Authentication role and synthetic account label.
- TC list executed and marker used.
- `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` or `SKIPPED` status for each case.
- Sanitized screenshot, Allure result or trace for failures.

Do not include credentials, tokens, refresh tokens, email addresses or raw personal data. Use the peer-testing protocol in `docs/peer-testing-protocol-proposal.md` for the result format.

## Remaining coverage

The following cases still require separate implementation or a real peer run:

- Pagination beyond the first dashboard campaign page with real data.
- Data change and persistence after a campaign or mission is updated through another module.
- Trend reload/error behavior with malformed or partial API responses.
- Keyboard and accessible-name behavior for filters and campaign cards.
- Tablet and other mobile widths.
- Independent loading and retry behavior for profile, trend and campaigns.
- Dashboard onboarding tooltip visibility below the fixed navbar.
- Real signed-in browser reload for the deployed revision.
