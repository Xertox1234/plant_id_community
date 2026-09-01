---
status: completed
priority: p3
issue_id: "312"
tags: [web, e2e, playwright, auth]
dependencies: []
---

# Two pre-existing auth.spec.js e2e failures (stale selector + error-copy regex)

## Problem

`web/e2e/auth.spec.js` has two tests that fail on the current codebase,
unrelated to any recent change. Both were surfaced by Canopy PR 4's
(#558, merged 2026-08-17) Task 8 full-project Playwright run, which shares
the same `chromium-authenticated` project these tests already ran under —
Task 7 of that plan only widened the project's `testMatch`, it didn't touch
`auth.spec.js` or cause either failure.

## Findings

- **`auth.spec.js:16`** — `user is already logged in (from auth.setup.js)`.
  Its assertion at `auth.spec.js:22` locates
  `[data-testid="user-menu"]` (also used at `:48` and `:64`). Confirmed via
  `git show main:web/src/layouts/AppShell.test.tsx` that this testid only
  ever existed as a Vitest mock stand-in
  (`web/src/layouts/AppShell.test.tsx:25`: `default: () => <div
  data-testid="user-menu" />`) — it was never real markup, even on `main`
  before any Canopy work. `grep -rn 'data-testid="user-menu"' web/src`
  confirms zero matches outside that one test mock. The real header
  markup uses different structure (restyled again under Canopy PR 4 Task 5,
  but was already testid-less before that).
- **`auth.spec.js:107`** — `shows error with invalid credentials`. Its
  assertion at `auth.spec.js:118-121` waits (5s timeout, swallowed via
  `.catch(() => false)`) for `text=/invalid|incorrect|failed/i` to become
  visible after submitting a wrong password, then asserts `errorVisible`
  is truthy. Root cause NOT fully diagnosed — flagging both plausible
  causes for whoever picks this up, rather than guessing:
  - The rendered failure copy is `'Login failed. Please try again.'`
    (`web/src/pages/auth/LoginPage.tsx:134`,
    `web/src/services/authService.ts:87`) — that string *does* contain
    "failed" and should match the regex if it renders in time. So this may
    be a **timing** issue (the error render happens after the 5s window,
    or via a toast/transition Playwright's `text=` locator doesn't catch)
    rather than a copy mismatch.
  - Alternatively, this could be an **account-lockout** interaction: the
    seeded `e2e_test_user` (`backend/apps/users/management/commands/create_test_user.py`)
    accumulates failed-login attempts across repeated local Playwright
    runs (this spec's own "invalid credentials" test deliberately fails a
    login every run), and `security/authentication.md`'s documented
    lockout mechanism may substitute a different message (e.g. "Account
    locked...") that doesn't match `/invalid|incorrect|failed/i` once the
    threshold is crossed. Needs a controlled repro against a
    freshly-`create_test_user`'d account to confirm or rule out.
- Both failures reproduced twice in a row in Task 8's verification (see
  `.superpowers/sdd/2026-08-16-canopy-areas/task-8-report.md` §"Test
  commands run" — Step 4, run twice, identical `8 passed, 2 failed` both
  times, same two failures).
- Not caused by, and out of scope for, Canopy PR 4's 8 tasks — none of them
  touch `auth.spec.js`, `AppShell.tsx`'s header markup structure, or
  `LoginPage.tsx`'s error handling beyond what's cited above (which
  predates the branch).

## Recommended Action

1. **Selector fix (straightforward):** update `auth.spec.js:22/48/64` to
   target real current header markup instead of the never-real
   `[data-testid="user-menu"]`. Either add a real `data-testid="user-menu"`
   to the header's user-menu trigger in `AppShell.tsx` (and update the
   Vitest mock comment noting it's now real), or change the e2e selector to
   whatever the current accessible markup exposes (e.g. a role/name query
   matching the visible user-menu button).
2. **Error-copy assertion (needs investigation first):** run the login
   test suite against a freshly reset `e2e_test_user`
   (`python manage.py create_test_user`) immediately before the "invalid
   credentials" test, in isolation, to rule out lockout-state pollution
   from prior runs. If the error still doesn't appear within 5s on a clean
   account, add tracing (screenshot / `page.content()` on failure) to see
   what actually rendered, then fix either the assertion's timeout/locator
   or the regex to match whatever's genuinely wrong.

## Technical Details

- `web/e2e/auth.spec.js:16-33` (stale-selector test)
- `web/e2e/auth.spec.js:107-127` (error-copy test)
- `web/src/layouts/AppShell.test.tsx:25` (the mock that originated the
  testid, never mirrored in real markup)
- `web/src/pages/auth/LoginPage.tsx:134`, `web/src/services/authService.ts:87`
  (actual rendered failure copy: "Login failed. Please try again.")
- `backend/apps/users/management/commands/create_test_user.py` (fixture
  user, bypasses the collection-creation signup hook — unrelated detail,
  noted for whoever touches this user next)

## Acceptance Criteria

- [x] `auth.spec.js:16` ("user is already logged in") passes against
      current header markup
- [x] `auth.spec.js:107` ("shows error with invalid credentials") passes,
      with the actual root cause (timing vs. lockout vs. something else)
      identified and documented in the Work Log, not just patched blind
- [x] `npx playwright test --project=chromium-authenticated` run twice in a
      row, both green, no flake

## Work Log

### 2026-08-17 - Filed

- Filed by Claude following Canopy PR 4 (#558, merged 2026-08-17). Both
  failures were surfaced (not caused) by that branch's Task 8 e2e run;
  filing was deferred past the merge and is done now.

### 2026-08-31 - Fixed; real root causes were neither of this todo's two hypotheses

**Failure 1 (stale selector)** was as diagnosed: `[data-testid="user-menu"]`
never existed in real markup — only in `AppShell.test.tsx`'s mock of
`UserMenu`. Added the real `data-testid="user-menu"` to `UserMenu.tsx`'s
trigger button.

**Failure 2 ("shows error with invalid credentials")** was neither a timing
issue nor SecurityMonitor account lockout — both hypotheses this todo raised
were ruled out by tracing the actual response bodies:
- Lockout copy ("Too many failed login attempts...") *also* contains "failed",
  so it would have matched the test's own regex — it was never disqualifying.
- SecurityMonitor clears failed attempts on every successful login
  (`apps/core/security.py`), and each run does 2 successful logins before the
  1 failed one, so the lockout counter never accumulates.

The real cause: login is rate-limited 5/15m per IP
(`apps/plant_identification/constants.py`), no DEBUG/test exemption. One
`--project=chromium-authenticated` run does 3 login POSTs (setup's real login
+ "valid credentials" + "invalid credentials" tests); two runs in a row — the
AC's own bar — is 6, over budget. A tripped limit returns
`{"message": "Rate limit exceeded..."}` with no `errors.detail`
(`apps/core/exceptions.py`), which `authService.ts` surfaces verbatim — text
that matches none of `/invalid|incorrect|failed/i`. Fixed by adding a new
DEBUG-gated `reset_ratelimits` management command
(`cache.delete_pattern("rl:*")`) invoked automatically from `auth.setup.js`
before every run — not a manually-documented step, since the exhaustion is
deterministic on run 2's third request and a step a human has to remember
can't satisfy "run twice in a row."

**A second, previously-undiagnosed bug surfaced only by actually running the
suite** (not found by tracing code): fixing the testid activated a dormant
branch in "can logout successfully" (it always vacuously passed via its
`else` branch before, since the testid never matched). That branch's
`text=/logout/i` locator doesn't match the rendered `"Log out"` (with a
space) — fixed via `getByRole('menuitem', { name: /log ?out/i })`
(`UserMenu.tsx`'s logout control already carries `role="menuitem"`).

**A third, also previously-undiagnosed issue, found empirically on the first
real end-to-end run**: even with rate-limiting and the selectors fixed, both
the login and logout tests failed twice in a row with the submit button
stuck on "Signing in..." past the assertion's fixed timeout (confirmed via
failure screenshots + backend request logs — both POSTs succeeded server-side,
just not within the test's hardcoded 2-5s DOM-poll windows). Root cause:
`chromium-authenticated`'s `testMatch` also runs `forum-authenticated.spec.js`
and `canopy-areas-authenticated.spec.js` in the same invocation, and under
`fullyParallel: true` (5 workers locally) they all hit one `manage.py
runserver` process concurrently — real, reproducible contention, not flakiness
in the traditional sense (it reproduced identically twice, warm server or
cold). Fixed by waiting on the actual `page.waitForResponse(...)` for the
login/logout POST before polling the DOM, instead of padding the fixed
timeouts with a guessed number — removes the race entirely regardless of
backend latency. This also let the rate-limit check become precise
(`response.status() === 429`) instead of a fragile text-based sniff.

First verification round: `npm run test` (982/982), `npm run type-check`
(clean), `python manage.py test apps.users --keepdb` (133/133, incl. 3 new
`reset_ratelimits` tests), and `npx playwright test
--project=chromium-authenticated` green **three** times in a row with nothing
manual between runs (10/10 passed each time).

Filed todo 329 for the broader, distinct concern this surfaced: a *full*
`npx playwright test` (all 7 projects) runs `auth.spec.js`'s login attempts
under more projects than just the two authenticated ones, and could still
exceed the rate-limit budget even with the setup-time reset — needs its own
investigation, out of scope for this todo's AC (which only requires
`--project=chromium-authenticated`).

### 2026-08-31 - Code review (react-typescript-reviewer, django-drf-reviewer,
cross-cutting-reviewer via code-review-orchestrator)

Dispatched per the `completing-todos` skill's review step against the full
changed-file set. `react-typescript-reviewer`: 0 findings (verified single
`UserMenu` mount site, no strict-mode risk from the new testid).

`django-drf-reviewer` — 4 findings on the new `reset_ratelimits.py`/its test,
all medium/low, all **repaired**:
- (medium) `deleted == 0` printed as an unqualified `SUCCESS` could mask a
  real REDIS_URL/db-index mismatch between the command's process and
  `runserver`'s — now prints a `WARNING` naming that exact failure mode.
- (medium) No test exercised the `delete_pattern`-returns-`None` branch (the
  command's own stated motivating design decision, per its docstring) — added
  `test_errors_when_delete_pattern_returns_none`, patching
  `django_redis.cache.RedisCache.delete_pattern` at the class level (not the
  `cache` proxy, which forwards attribute access onto the live instance).
- (low) Cache alias/prefix (`'default'` / `'rl:'`) were hardcoded instead of
  reading `RATELIMIT_USE_CACHE`/`RATELIMIT_CACHE_PREFIX` the way
  `django_ratelimit.core.get_usage()` itself does (verified exact resolution:
  `getattr(settings, 'RATELIMIT_USE_CACHE', 'default')` /
  `getattr(settings, 'RATELIMIT_CACHE_PREFIX', 'rl:')`) — now mirrors that
  exactly, via `caches[cache_alias]` instead of the bare `cache` import.
- (low) A test left `"unrelated-key"` residue in the shared dev/CI Redis
  instance — added `addCleanup`.

`cross-cutting-reviewer` — 3 findings, 2 high + 1 medium:
- (**high**, repaired) `"can login with valid credentials"` still used a bare
  `page.click()` + fixed `waitForURL(10000)` — it makes the same real,
  rate-limited login POST as its sibling but never got the
  `waitForResponse`/429-diagnostic treatment. Fixed identically.
- (**high**, accepted-and-deferred) A *full* unfiltered `npx playwright test`
  runs `auth.spec.js` under all 7 projects (measured via `--list`, not just
  claimed — see todo 329), yielding 15 real login POSTs against the 5/15m
  budget in one invocation; the once-per-invocation reset this todo ships
  can't close that regardless of where it fires. This is a real gap, but
  fixing it properly means a coverage-scoping decision on
  `playwright.config.ts` (which browsers `auth.spec.js` should run under at
  all) that deserves its own explicit pass, not a rushed addition here — this
  todo's own AC is scoped to `--project=chromium-authenticated`, which is
  fully satisfied and verified. Rolled into todo 329 (raised to p3) with the
  exact measured numbers.
- (medium, accepted-and-deferred) The `mode: 'serial'` fix only serializes
  tests *within* one project; `chromium-authenticated` and
  `firefox-authenticated` share the same `.auth/user.json` storageState with
  no dependency between the two projects, so a full-suite run could still
  race a logout's token-blacklist against the other project's still-running
  tests. Same root cause as the above (auth.spec.js's project coverage) —
  folded into todo 329 rather than a separate fix.

Repairs applied, re-verified: `python manage.py test
apps.users.tests.test_reset_ratelimits_command` (4/4, incl. the new
None-branch test), full `apps.users` suite (134/134), `npm run type-check`
(clean), and `npx playwright test --project=chromium-authenticated` green
**three more** consecutive times post-repair (6 total across both rounds,
10/10 each).

### 2026-08-31 - Completed

- Verification: all three acceptance criteria passed with quoted command
  output above — both spec tests pass, root cause documented (rate limit +
  a second timing race, neither of the todo's original two hypotheses), and
  `--project=chromium-authenticated` green 6/6 consecutive runs across two
  review rounds.
- Review: 7 findings total (react-typescript-reviewer 0; django-drf-reviewer
  4 medium/low, all repaired; cross-cutting-reviewer 2 high + 1 medium — the
  high `"can login with valid credentials"` consistency gap repaired, the
  other high plus the medium finding accepted-and-deferred to todo 329 with
  explicit rationale, since fixing them requires a `playwright.config.ts`
  coverage-scoping decision beyond this todo's `--project=chromium-authenticated`
  AC scope).

## Notes

- p3: both are pre-existing e2e-only failures with no production user
  impact confirmed — `auth.spec.js`'s scope is smoke coverage, and the
  app's actual login flow is exercised successfully by
  `auth.spec.js:89` ("can login with valid credentials", which passes) and
  by every other authenticated e2e spec's `auth.setup.js` step.
- Related: Canopy PR 4 / #558
  (`docs/superpowers/plans/2026-08-16-canopy-areas.md`, Task 7/8), sibling
  todo 311 (also filed from the same PR's follow-ups).
