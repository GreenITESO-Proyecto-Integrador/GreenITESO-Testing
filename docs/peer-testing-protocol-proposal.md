# Peer-testing protocol proposal

**Status:** proposal for agreement by Teams 1, 2, and 3. This is not an approved release gate yet.  
**Scope:** repeatable cross-team UI, API, and database checks for GreenITESO changes.  
**Owner:** GreenITESO-Testing contributors; team/module ownership must be confirmed in the project board.

## Purpose

Each team checks a change owned by another team and leaves evidence that a classmate can repeat. The implementing team may help prepare a test account or explain a contract, but does not mark its own change as peer-tested. Automated checks and peer acceptance are separate results.

## Before a run

Record the issue or acceptance criterion, repositories and exact commit SHAs under test, the tester's team, the owning team, the chosen environment, and the intended test scope. Agree on a safe test account and synthetic records with the environment owner.

- Prefer isolated local environments. Backend and database checks use PostgreSQL 18 through the backend's Compose/devcontainer workflow; do not use Neon credentials for local development.
- Use synthetic users and records. Do not include real student data, passwords, tokens, connection strings, or unredacted personal information in logs, screenshots, traces, or reports.
- Do not run destructive checks, migrations, seed commands, or cleanup against shared staging or production without the environment owner's explicit authorization and a documented recovery plan. Never use production for routine peer testing.
- Record the app, API, database/schema, and browser versions that materially affect the result. If a required service or test account is unavailable, report `BLOCKED` instead of substituting an unapproved environment.

## Choose the right test layer

Use the cheapest layer that proves the acceptance criterion, then add a browser flow when the user-visible integration matters.

| Layer | What it can prove | GreenITESO starting point |
| --- | --- | --- |
| Backend/API | Response contract, authorization, persistence, transactions, and error cases | Backend's PostgreSQL 18 Compose/devcontainer instructions and `make test` |
| Frontend component/build | Type correctness, rendering/build, and isolated UI behavior | Frontend `pnpm type-check`, `pnpm build`, and Playwright tests |
| Browser + real API | A user journey crosses the UI, authentication/session, API, and persistence | Run the frontend and backend against an approved isolated local setup; capture browser and API evidence |
| Database/release | Migration graph, schema state, least-privilege roles, and smoke checks | `make makemigrations-check`, empty-database and upgrade-path checks, and `make db-smoke` locally |

The Frontend `playwright.config.ts` starts Vite at `http://localhost:3000`; it does not start Django or PostgreSQL. A passing frontend Playwright run alone therefore does not prove that an API-backed flow works. The Frontend configuration currently defines Chromium, Firefox, and WebKit projects. Select and record the projects actually run.

The separate `GreenITESO-Testing` framework uses Python Playwright, pytest, and `uv`; its `sanity` and `full` markers are the intended suite selectors. A marker is not evidence that coverage exists: report the collected case count and the actual result for the tested revision.

## Reproducible commands

Use the repository's lockfile and documented setup. Do not install ad hoc dependencies during a peer run.

### Frontend Playwright

From the Frontend repository:

```sh
pnpm install --frozen-lockfile
pnpm test
```

To narrow a run, use the repository's installed Playwright CLI, for example:

```sh
pnpm exec playwright test tests/example.spec.ts --project=chromium
```

The default config runs all configured browser projects and starts Vite only. For an API-backed journey, start the Backend and its PostgreSQL service using the Backend's own instructions and explicitly record the API URL/configuration. Do not claim an integrated test if requests were mocked or intercepted.

### Backend and database

From the Backend repository, follow `docs/database-development.md` and use the documented disposable PostgreSQL 18 environment. The usual checks are:

```sh
make compose-up
make migrate
make makemigrations-check
make test
make db-smoke
```

Run migration checks from both an empty disposable database and the prior integration schema when the change alters migrations. Record which paths ran. `make compose-down` preserves the local volume; do not delete a volume unless its owner confirms it is disposable.

### Cross-team E2E framework

From `GreenITESO-Testing`:

```sh
uv sync --frozen
uv run playwright install chromium
cp .env.example .env
uv run pytest -m sanity
```

Use `uv run pytest -m full` only for the agreed full suite/release scope. Put credentials only in the ignored local `.env` or an approved CI secret store. Confirm `BASE_URL` points to the authorized test environment before starting. The current framework scaffold may not yet contain cases for every module; report the collected and executed counts and list missing cases as `NOT RUN`.

Before selecting Firefox or WebKit in this framework, install that browser too (for example, `uv run playwright install chromium firefox webkit`). Installing Chromium alone does not prepare the other engines.

## Test case and result record

Use one record per acceptance criterion or cohesive scenario. Keep the expected outcome observable and the steps repeatable.

```markdown
### <case ID> — <short title>
- Issue / acceptance criterion:
- Implementing team / testing team:
- Repository SHAs (frontend / backend / infra or test framework):
- Environment and data: (local/isolated/shared; synthetic account and fixture label only)
- Browser and version / viewport, if applicable:
- Preconditions:
- Steps:
  1.
- Expected result:
- Actual result:
- Status: PASS | FAIL | BLOCKED | NOT RUN | SKIPPED
- Evidence: (sanitized screenshot, trace, request/response, log, or DB assertion link)
- Related defect / follow-up issue:
- Cleanup performed:
```

### Status meanings

- **PASS:** every stated expected result was observed on the recorded revision and environment.
- **FAIL:** a step ran and a stated expected result did not occur; include a reproducible path and evidence.
- **BLOCKED:** execution could not start or continue because of an external prerequisite; name the missing prerequisite without calling it a product failure.
- **NOT RUN:** the case is in scope but was not attempted. Give the reason when known.
- **SKIPPED:** an automated dependency/setup case failed, so this case was not independently exercised. Do not count it as a pass.

When a rerun changes a result, append a new run with its timestamp and SHAs. Preserve the earlier result instead of overwriting it. Link a failing case to a GitHub issue and link the result back to that issue or PR. A PR's green CI does not by itself establish peer acceptance or deployment.

## Evidence and triage

Capture only the smallest evidence needed to reproduce and verify the result: sanitized screenshot, Playwright trace on failure, relevant console/network request and response, backend log excerpt, and a before/after database assertion when persistence is part of the criterion. Record timestamps and redact cookies, authorization headers, tokens, email addresses, and other personal data.

Describe a failure as observed behavior, not an inferred cause. Include the exact step, expected and actual result, revision, and environment. The implementation team owns diagnosis and correction; the peer tester confirms the fix on the updated SHA. Keep `BLOCKED`, `NOT RUN`, flaky, and passing outcomes distinct in the GitHub Project and report.

## Database-specific safeguards

- Run schema tests against PostgreSQL 18, never SQLite as a substitute for database behavior.
- Check both fresh installation and upgrade from the prior integration state for migration changes.
- Review ownership and cross-app dependencies for migrations; do not edit a migration already shared with an environment.
- Verify persistence and rollback behavior with synthetic records, including foreign-key, uniqueness, authorization, and transaction outcomes that match the criterion.
- Keep role, migration, seed, and destructive checks on disposable local data unless an environment owner has approved a controlled shared-environment run.
- Record database smoke results separately from browser results. A DB smoke test does not prove the frontend is wired to that database.

## Agreement needed before adoption

The three teams should confirm: (1) the module ownership and rotating peer-testing assignments; (2) whether Chromium-only is acceptable for routine checks and when Firefox/WebKit are required; (3) where run records live (this repository, the GitHub issue, or both); and (4) who may authorize shared staging checks. Until confirmed, treat the sections above as a proposal and the existing project/repository rules as authoritative.

## Source references

These links identify the implementation and instructions checked while drafting this proposal:

- [GreenITESO-Testing framework conventions](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Testing/blob/52773b3d1b942f8ab993da257ed0fdf63fac20b3/CLAUDE.md)
- [Frontend Playwright configuration](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/blob/0af133e33bd1b15c614f48da3ddc28c78fb526a6/playwright.config.ts)
- [Frontend test scripts](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/blob/0af133e33bd1b15c614f48da3ddc28c78fb526a6/package.json)
- [Backend database development guide](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/blob/d4394d0cb277e93cb07389b1534e5bf4d0c87cfa/docs/database-development.md)
- [Infra private object bucket scaffold](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Infra/blob/be854337bd5a74e81eb891b81bc3924cd801843f/modules/storage/main.tf)
