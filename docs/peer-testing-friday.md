# GreenITESO peer testing: Friday starter matrix

Delivery: Friday, 20 November 2026. The assignments below transcribe the teacher's classroom whiteboard. Each team tests another team's features; the feature-owning team helps reproduce and fix failures.

| Testing team | Feature owner | Features to test |
| --- | --- | --- |
| Team 1 | Team 2 | Identity, access, clans |
| Team 2 | Team 3 | Notifications, campaigns, feed, dashboard |
| Team 3 | Team 1 | Actions, points, gamification |

## How to use this matrix

- This is a **starter**, not a claim of complete coverage. Adapt the cases to the current product and acceptance criteria; add missing cases and record any unavailable feature as `NOT RUN` or `BLOCKED` with a reason.
- Every case below starts **NOT RUN for this cycle**. Historical links show what was observed in older local runs, not the current production result. Do not copy an old PASS or FAIL as Friday's result.
- Start with the [6 November re-execution](https://lab.ferramos.com/noviembre-2026/reejecucion-octubre) and search for the cited QA or CLAN/FEED ID. The individual evidence links in the tables below point to the older 9 October snapshot; the November page records the newer outcome and test layer where the case was rerun.
- The demo is planned for production. Agree with the environment owner which read-only or non-destructive checks and test accounts are allowed there; run destructive, account/role-changing, migration, seed and cleanup scenarios only in an approved isolated environment. Record the actual environment for each case. Do not expose real users, credentials or tokens.
- For each execution record tester/team, date and time, frontend/backend revision or deployed version if known, environment, account role, steps, expected and actual result, status, sanitized evidence link and issue link. Use the template in the [protocol](peer-testing-protocol-proposal.md#test-case-and-result-record). Do not enter a SHA or claim a deployment unless verified; write `unknown` when needed.
- Test the actual UI with the real API when the requirement is an integrated journey; identify mocked UI or API-only tests as such. Record the browser and whether results survived reload. Capture only safe evidence.

## Team 1 tests Team 2: identity, access and clans

| Case | Expected result | Historical starting point |
| --- | --- | --- |
| T1-01 | Institutional login reaches the app; reloading keeps the session. Never record password or MFA entry. | [QA35A: prior real login](https://lab.ferramos.com/evidence/final-QA35A.json) |
| T1-02 | A signed-out user cannot open a protected route; logout returns to login. | [QA16A](https://lab.ferramos.com/evidence/final-QA16A.json), [QA34A](https://lab.ferramos.com/evidence/final-QA34A.json) |
| T1-03 | Session refresh works across consecutive renewals. | [QA16G](https://lab.ferramos.com/evidence/final-QA16G.json) |
| T1-04 | A student cannot access or perform an administrator-only operation. | [QA02B](https://lab.ferramos.com/evidence/final-QA02B.json), [QA29D](https://lab.ferramos.com/evidence/final-QA29D.json) |
| T1-05 | Onboarding validates career and shows the assigned institutional clan; the selection persists. | [QA30B](https://lab.ferramos.com/evidence/final-QA30B.json), [QA30D](https://lab.ferramos.com/evidence/final-QA30D.json) |
| T1-06 | Create or join a clan, select it and verify membership after reload; use approved disposable data. | [CLAN-02](https://lab.ferramos.com/evidence/CLAN-02.json), [CLAN-05](https://lab.ferramos.com/evidence/CLAN-05.json) |
| T1-07 | A leader handles a join request and a non-authorized member cannot perform leader-only actions. | [QA36B](https://lab.ferramos.com/evidence/final-QA36B.json), [QA36E](https://lab.ferramos.com/evidence/final-QA36E.json) |
| T1-08 | A private profile's owner sees their avatar after login; another student does not. If profile editing is available, save a photo and check it after navigation and reload. | [Backend #277 review](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/pull/277#pullrequestreview-5892912784), [Frontend #125 review](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/pull/125#pullrequestreview-5892910865); both are historical PR-specific findings. |

## Team 2 tests Team 3: notifications, campaigns, feed and dashboard

| Case | Expected result | Historical starting point |
| --- | --- | --- |
| T2-01 | The dashboard loads for the signed-in user and displays available data without broken requests. | [QA14](https://lab.ferramos.com/evidence/final-QA14.json) |
| T2-02 | A user sees real notifications, can mark one read, and its state persists after reload. | [QA10B](https://lab.ferramos.com/evidence/final-QA10B.json), [QA21C](https://lab.ferramos.com/evidence/final-QA21C.json) |
| T2-03 | A user cannot read or modify another user's notification. | [QA21B](https://lab.ferramos.com/evidence/final-QA21B.json), [QA37E](https://lab.ferramos.com/evidence/final-QA37E.json) |
| T2-04 | An eligible user can find and join a campaign and see its missions and progress. | [QA07B](https://lab.ferramos.com/evidence/final-QA07B.json), [QA31G](https://lab.ferramos.com/evidence/final-QA31G.json) |
| T2-05 | An authorized user can create or review a campaign; unauthorized actions are rejected. Use disposable data. | [QA26A](https://lab.ferramos.com/evidence/final-QA26A.json), [QA27G](https://lab.ferramos.com/evidence/final-QA27G.json) |
| T2-06 | Create, edit and delete an own feed post; verify changes after reload and reject edits by another user. Use disposable data. | [FEED-02](https://lab.ferramos.com/evidence/FEED-02.json), [QA09B](https://lab.ferramos.com/evidence/final-QA09B.json) |
| T2-07 | Where available, a feed image loads after upload and a Like persists after reload; record the deployed revision. | [QA28B](https://lab.ferramos.com/evidence/final-QA28B.json); real photo storage was not verified in that snapshot. [Frontend #122](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/pull/122) also records an accepted filter-refresh race; its deployment is not established here. |

### Dashboard coverage for T2-01

The automated Dashboard module (`tests/Dashboard/`) complements T2-01 with these executable cases:

| TC | Automated coverage | Type |
| --- | --- | --- |
| TC-03-001 | Student impact metrics match `profile/me` in es-MX format | Real API |
| TC-03-002 | Four-week impact trend has three charts and matching week labels | Real API |
| TC-03-003 | Active missions, progress and “Registrar acción” navigation | Real API |
| TC-03-004 | State/scope filters, no-filter match state and pagination | Real API |
| TC-03-005 | New-user zero metrics, empty campaigns and empty missions | Mocked UI state |
| TC-03-006 | Admin dashboard hides student-only sections | Real API |
| TC-03-007 | Profile load error and retry | Mocked error/retry |
| TC-03-008 | Trend load error and retry | Mocked error/retry |
| TC-03-009 | Campaign and mission load errors and retry | Mocked error/retry |
| TC-03-010 | Opening a participating campaign detail | Real API |
| TC-03-011 | Reload preserves the authenticated dashboard and reloaded metrics | Real API |
| TC-03-012 | Mobile dashboard sections render without horizontal overflow | Real API |

T2-01 requires an actual peer run in the selected environment. A passing automated case does not replace a recorded result: each run must include the environment, browser, viewport, frontend/backend revisions, status and sanitized evidence.

## Team 3 tests Team 1: actions, points and gamification

| Case | Expected result | Historical starting point |
| --- | --- | --- |
| T3-01 | The action catalog loads the available actions and points for a signed-in user. | [QA03](https://lab.ferramos.com/evidence/final-QA03.json) |
| T3-02 | A user registers an action from the UI; its result persists after reload. Use an approved test account and data. | [QA04](https://lab.ferramos.com/evidence/final-QA04.json) |
| T3-03 | An action's points and mission progress reflect its actual approval state; a pending item is not prematurely credited. | [QA05A](https://lab.ferramos.com/evidence/final-QA05A.json), [QA06A](https://lab.ferramos.com/evidence/final-QA06A.json), [QA07A](https://lab.ferramos.com/evidence/final-QA07A.json) |
| T3-04 | Authorized audit can approve or reject an action; other roles are denied. Verify point changes when applicable. | [QA06B](https://lab.ferramos.com/evidence/final-QA06B.json), [QA06C](https://lab.ferramos.com/evidence/final-QA06C.json), [QA06E](https://lab.ferramos.com/evidence/final-QA06E.json) |
| T3-05 | A repeated request does not duplicate the action or points, and the daily limit is enforced. | [QA05B](https://lab.ferramos.com/evidence/final-QA05B.json), [QA25C](https://lab.ferramos.com/evidence/final-QA25C.json) |
| T3-06 | Rankings and earned badges show the expected user data and persist after reload. | [QA08A](https://lab.ferramos.com/evidence/final-QA08A.json), [QA10C](https://lab.ferramos.com/evidence/final-QA10C.json) |
| T3-07 | A permitted reward redemption updates available points and inventory; duplicate or insufficient-balance cases are handled. Use disposable data. | [QA19A](https://lab.ferramos.com/evidence/final-QA19A.json), [QA19B](https://lab.ferramos.com/evidence/final-QA19B.json), [QA19C](https://lab.ferramos.com/evidence/final-QA19C.json) |
| T3-08 | An authorized administrator can create or update a catalog action and see the saved value; a student is denied. Use disposable data. | [QA12A](https://lab.ferramos.com/evidence/final-QA12A.json), [QA23](https://lab.ferramos.com/evidence/final-QA23.json), [QA38A](https://lab.ferramos.com/evidence/final-QA38A.json). |

## Prior QA and evidence provenance

These are historical sources for cases and reproduction evidence, not new test runs or a substitute for Friday's peer results. Check the November sources first: several October failures later passed locally, so an October failure is not proof of a current defect.

- **16 November — backend CI:** after feed-image cleanup PR [#288](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/pull/288), the [Django suite](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/actions/runs/43972299633), Ruff and Pylint passed on merged `dev` commit `57a1b95`. The [dev database migration workflow](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/actions/runs/43973165307) succeeded, while [Release - dev](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/actions/runs/43972299786) was skipped. This is backend/CI evidence, not proof of production deployment or an end-to-end browser pass.
- **13 November — targeted PostgreSQL review:** seed draft [Backend #281](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Backend/pull/281) records 1,154 local PostgreSQL 18 tests and a concurrency check at its then-current candidate. This covers the seed candidate, not a seed run on Neon or all user journeys.
- **5–6 November — local E2E and re-execution:** [November local matrix](https://lab.ferramos.com/noviembre-2026/matriz), [6 November re-execution](https://lab.ferramos.com/noviembre-2026/reejecucion-octubre), and [individual Chromium results](https://lab.ferramos.com/noviembre-2026/pruebas-chromium-06.html). The re-execution recorded **243 PASS, 13 FAIL, 23 NOT RUN** across 279 mixed checks on frontend `0553ba6b` and backend `df7d4f48` with isolated PostgreSQL 18 and synthetic data. These include route checks, API checks and mocked browser tests; they are not 279 end-to-end journeys. In that run UI action registration, the audit queue, notifications and session refresh passed locally; admin catalog changes and the profile API badge field still had failures. Verify each on the deployed version.
- The separate **217 Chromium results** recorded **203 PASS / 14 FAIL** and mostly used mocked API responses. The [November 5 local matrix](https://lab.ferramos.com/noviembre-2026/matriz) documents real local UI/API flows for action registration and audit, campaigns, clans, feed, profiles and notifications, while recording gaps such as real GCS, production login and cross-browser behavior. The local backend suite recorded 1,072 passing tests on the tested revision. The 5 November and 6 November backend revisions differ; consult each page rather than combining their results into a single run.
- **5 November — focused frontend reviews:** [#103](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/pull/103#pullrequestreview-5789734092) recorded 32 Chromium notification tests passing. [#107](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Frontend/pull/107#pullrequestreview-5789734101) recorded a passing type-check and temporary long-text expand/collapse test, with a remaining fixture issue in the existing catalog tests. These are scoped PR checks, not production acceptance.

- **1 October:** local walkthrough, 31 recorded checks; the [archived QA hub](https://lab.fernandoramos.work/) and [Infra QA wiki](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Infra/wiki/QA) preserve its evidence and limitations. The run used synthetic data and did not validate real Microsoft login or deployment.
- **8 October:** local Chromium, Django and PostgreSQL 18 run, 68 recorded checks; its cases and evidence informed the subsequent 9 October reports. Real Entra, GCS uploads and deployment were not verified in that run.
- **9 October:** a separate integral local run used synthetic data plus one real Microsoft login; the later integrated-code matrix used newer frontend/backend revisions and retained the login as prior evidence. [Full matrix and individual evidence](https://lab.ferramos.com/matrix), [summary](https://lab.ferramos.com/summary.md), [recorded findings](https://lab.ferramos.com/findings.md), and [video](https://lab.ferramos.com/video/greeniteso-current-complete.mp4). The published hub is a static historical QA showcase, not the deployed product or a current test result.
- The 9 October integrated matrix identifies frontend `5930f50`, backend `1e56ffb` and Infra `30825da`. It records local PostgreSQL 18 and synthetic data; real GCS uploads, production, QR, PWA/offline, performance and full accessibility remained unverified. Recheck what applies to the current product.

The public hub contains selected sanitized evidence. Do not copy raw login recordings, local environment files, credentials, or private data into this repository or a public report.
