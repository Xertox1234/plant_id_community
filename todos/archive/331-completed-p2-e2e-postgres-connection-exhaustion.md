---
status: completed
priority: p2
issue_id: "331"
tags: [web, e2e, playwright, backend, database, infra]
dependencies: []
---

# A full `npx playwright test` run exhausts Postgres connections, failing ~60 tests

## Problem

A full unfiltered `npm run test:e2e` cannot pass on a developer machine: the
threaded Django dev server opens a DB connection per request thread, and under
Playwright's default parallelism (5 workers x 7 browser projects) Postgres hits
`max_connections` within seconds. The backend then 500s on arbitrary requests
and ~60 tests fail with misleading assertion errors (`expect(page).toHaveURL`,
`toBeTruthy`) that name the symptom, never the cause.

This is **not** the login rate-limit problem — that was todo 329, which is fixed.
This was discovered while verifying 329's AC-3 ("`npm run test:e2e` twice in a
row, both green"), which is blocked solely by this.

## Findings

All measured on 2026-09-01 against `fix/329-e2e-auth-spec-project-scoping`
with a freshly restarted Django server.

- **The error, verbatim**, 134–136 times per full run in the Django log:
  `django.db.utils.OperationalError: connection to server at "localhost" (::1),
  port 5432 failed: FATAL: sorry, too many clients already`
- **`max_connections = 100`**, and **36 connections are already held at idle**
  (27 in state `idle`) before any test starts — measured via
  `select count(*) from pg_stat_activity`. So the headroom is ~64, not 100.
- **Failure counts are load-dependent, not logic-dependent.** Two consecutive
  full runs: 59 failed / 152 passed, then 61 failed / 150 passed. The set is not
  stable between runs.
- **Isolation proves the tests themselves are fine.**
  `--project=chromium-authenticated` alone passes **7/7 in 8.7s**, including the
  three `auth.spec.js` tests that fail inside the full run.
- **Pre-existing, and worse before todo 329.** Same command on unmodified `main`
  (same machine, same servers, browsers installed): **78 failed, 234
  `too many clients`** vs **61 failed, 136** on the 329 branch. 329 reduces the
  load (it removes `auth.spec.js` from 5 projects) but does not address this.
- **Failures concentrate** in `forum-responsive.spec.ts` (16),
  `example.spec.js` (7), `forum-golden-path.spec.ts` (2) — forum pages doing the
  most DB work per page load. 72 of the messages are
  `expect(page).toHaveURL(expected)`: navigation lands on an error page.
- `debug_toolbar` is in every traceback frame, so `DEBUG=True` local settings add
  per-request SQL panel overhead on top of the connection cost.

## Proposed Solutions

### Option 1: Cap Playwright workers locally (Recommended)

- **Implementation:** set `workers` in `web/playwright.config.ts` for the
  non-CI branch (currently `process.env.CI ? 1 : undefined`, i.e. 5 on a
  10-core machine) to a value the backend can serve — measure, don't guess.
- **Pros:** one line, no backend change, no infra change, fixes the documented
  default local command for every developer.
- **Cons:** longer wall-clock for a full local run; masks rather than removes
  the underlying per-thread connection cost.
- **Effort:** minutes to change, ~30 min to measure the right number.
- **Risk:** low — test-config only.

### Option 2: Raise Postgres `max_connections`

- **Implementation:** raise it in the local Postgres config; document in
  `backend/CLAUDE.md` as an E2E prerequisite.
- **Pros:** keeps full parallelism and current run time.
- **Cons:** per-developer machine setup that cannot be enforced from the repo;
  each connection costs real memory; 36 idle connections at rest suggests
  something is also *leaking*, which this would hide.
- **Effort:** minutes, but unenforceable.
- **Risk:** medium — papers over the idle-connection question below.

### Option 3: Find and fix the 36 idle connections

- **Implementation:** attribute the at-rest connections
  (`select application_name, state, count(*) from pg_stat_activity group by 1,2`)
  and close whatever holds them; check `CONN_MAX_AGE`.
- **Pros:** addresses a real anomaly rather than the symptom; recovers ~36% of
  the budget for free.
- **Cons:** unknown scope until the attribution query is run; may be other local
  processes rather than anything in this repo.
- **Effort:** unknown — start with the query.
- **Risk:** low to investigate.

Options 1 and 3 are complementary; do 3 first since it is diagnostic.

## Recommended Action

1. Run the attribution query above and identify the 36 at-rest connections.
   Anything owned by this repo's processes is the first fix.
2. Measure the highest `workers` value that keeps a full run green, and set it
   for the non-CI branch in `web/playwright.config.ts` with a comment naming
   this todo.
3. Re-verify with `npm run test:e2e` twice in a row and record both summaries.
4. When green, tick todo 329's AC-3 too — that AC is blocked only by this.

## Technical Details

- `web/playwright.config.ts` — `workers: process.env.CI ? 1 : undefined`,
  `fullyParallel: true`, 7 non-setup projects.
- Django dev server is threaded by default; `runserver --nothreading` serializes
  but would very likely blow the 30s per-test timeout.
- Reproduce the count:
  `grep -c "too many clients already" /tmp/django-e2e.log` while a full run is in
  flight against a `runserver` whose stdout is captured.
- Connection stats:
  `echo "from django.db import connection…" | python manage.py shell`
  (see Findings for the exact queries).

## Acceptance Criteria

- [x] The 36 at-rest connections are attributed, and any owned by this repo closed
      — they *were* the bug, not a separate leak: `CONN_MAX_AGE=600` on a
      thread-per-request dev server. At true rest the count is 9 (8 of them
      Postgres's own background workers).
- [x] `npm run test:e2e` (no `--project` filter) completes with zero
      `too many clients already` in the backend log — 136 → **0**
- [x] `npm run test:e2e` run twice in a row, both green, no flake —
      213 passed / 4 skipped / **0 failed**, exit 0, both runs
- [x] Todo 329 closed out: its AC-3 ticked, `status: blocked` → `completed`, file
      renamed to match, and archived

## Work Log

### 2026-09-01 - Completed

**The root cause was not what this todo assumed.** The "36 at-rest connections"
were not a separate leak to hunt — they were the same bug decaying. At true rest
the count is 9, 8 of which are Postgres's own background workers.

`plant_community_backend/settings.py` passed `conn_max_age=600` unconditionally.
That is correct for production (gunicorn holds a bounded number of worker
processes) but wrong for `runserver`, which spawns a **thread per request**: each
thread's connection is then held for 10 minutes, so under parallel Playwright load
threads are created far faster than connections expire. `CONN_MAX_AGE` now defaults
to 0 when DEBUG is on and stays 600 otherwise, overridable via `DB_CONN_MAX_AGE`;
Railway and CI are unchanged.

Neither Proposed Solution was taken. Option 1 (cap Playwright workers) would have
capped the symptom and slowed every local run; Option 2 (raise `max_connections`)
would have hidden the real defect behind more headroom.

| | before | after |
|---|---|---|
| `too many clients already` per full run | **136** | **0** |
| failing tests | 61 | 51 → 0 (see below) |

**A third defect stood behind this one.** With the connections fixed, 51 failures
remained — 13 distinct tests, each failing identically on `main`, so none were
introduced by todos 329/331. Rather than file a fourth layer of the same
recursion, they were fixed here (see the commit for the full analysis):

1. **A real app bug**: AppShell's search button is `flex-1` without `min-w-0`, so
   its `min-width: auto` floored it at intrinsic width and pushed the header's auth
   actions to x=387 in a 375px viewport. Verified fixed at 320–1920px with the
   430px desktop cap intact.
2. Unscoped forum link selectors (7 tests) — the trap `docs/rules/testing.md`
   already documents from PR #536/#537. Now a single shared `FORUM_CONTENT_LINK`,
   with **prefix** exclusions: a board page's CTA is `/forum/new-thread?category=…`,
   which an exact-match `:not()` fails to exclude.
3. The theme spec wrote `data-mode` directly and ThemeContext's mount effect
   reapplied its own state over it — so only the tests expecting the DEFAULTS
   passed, and the rest were asserting against an unchanged page.
4. Stale post-Canopy markup, including a forum assertion that counted deleted
   Tailwind classes and passed on a "loading" fallback — green whether or not the
   forum worked.

Also removed a latent race in the browse→board→thread hop: `toHaveURL` resolves
when the SPA updates the URL, before the board's markup replaces the index's, so
the second click could re-hit a stale board card.

Final: `npm run test:e2e` twice in a row, **213 passed / 4 skipped / 0 failed**,
exit 0 both times, 0 `too many clients`, 0× 429, 4 login POSTs per run. The 4
skips are pre-existing deliberate `isMobile` guards. Vitest 1004 passed.

Prerequisite worth recording: this is only observable after
`npx playwright install firefox webkit` — those binaries were missing, so 4 of the
7 projects had been failing at launch and never contributed load.

### 2026-09-01 - Filed

- Split out of todo 329 while verifying its AC-3. 329's own fix (login rate-limit
  budget 15 POSTs -> 4, and per-project auth state) is complete and independently
  verified; this is the unrelated defect standing between it and a green suite.
- Filed p2 rather than p3: `npm run test:e2e` is the documented default local
  command in `web/CLAUDE.md` and currently cannot pass for anyone, which makes
  every future E2E change hard to verify.

## Notes

- **This todo is todo 329's only carrier.** 329 is `status: blocked`, and every
  sweep skill filters on `^status: pending` (`todo-next`, `todo-sweep`,
  `completing-todos` — grep them), so 329 will never be picked up on its own. Its
  AC-3 is satisfied the moment this todo's are, which is why closing it out is an
  AC here rather than a note.
- Only visible on this machine after installing the Firefox and WebKit browser
  binaries (`playwright install firefox webkit`) — they were missing, so
  `firefox`, `webkit`, `Mobile Safari` and `firefox-authenticated` had been
  silently failing to launch and never contributed load. Any developer without
  those binaries will see far fewer failures and a very different picture.
- E2E is excluded from CI (`web/CLAUDE.md`), so this is local-only today. It
  would become a CI blocker the moment E2E is added to the pipeline.
