---
status: blocked
priority: p3
issue_id: "329"
tags: [web, e2e, playwright, auth]
dependencies: ["331"]  # AC-3 only: needs a green full suite (Postgres connections)
---

# A full `npx playwright test` run may still exceed the shared login rate-limit budget

## Problem

Todo 312 fixed `web/e2e/auth.spec.js`'s two stale failures for
`--project=chromium-authenticated` specifically, including a new
`reset_ratelimits` management command auto-invoked from `web/e2e/auth.setup.js`
(the `setup` project) to clear the backend's shared IP-based login rate limit
(5/15m, `apps/plant_identification/constants.py`) before each run.

That fix is scoped and verified only for `--project=chromium-authenticated`,
because that's the todo's own AC. It's an open question — not yet
investigated — whether a single **full** `npx playwright test` invocation
(all 7 projects, no `--project` filter) can still exceed the same budget even
with the setup-time reset, since `auth.spec.js` is matched by more than the
two authenticated projects.

## Findings

- **Measured, not just theorized** (`./node_modules/.bin/playwright test
  --project=<name> --list`, run against every project individually): all 7
  non-`setup` projects — `chromium`, `firefox`, `webkit`, `Mobile Chrome`,
  `Mobile Safari`, `chromium-authenticated`, `firefox-authenticated` — include
  `auth.spec.js`'s full 6-test file, not just the 2 authenticated projects it
  was designed for. Root cause: the 5 unauthenticated projects'
  `testIgnore: /(auth\.setup|forum-authenticated\.spec|canopy-areas-authenticated\.spec)\.js/`
  excludes `auth.setup.js` but not `auth.spec.js` (the regex names are
  adjacent but distinct files).
- **Login POST budget, computed from the above**: the "Protected Routes
  (Unauthenticated)" describe block (2 real login POSTs: valid + invalid)
  runs once per project × 7 projects = 14, plus the shared `setup` project's
  1 real login (deduped to a single execution across the invocation per
  Playwright's dependency semantics — confirmed in todo 312) = **15 total
  `POST /api/v1/auth/login/` requests in one `npx playwright test`
  invocation**, against the 5/15m rate-limit budget. 3x over, and todo 312's
  `reset_ratelimits` call (wired into `auth.setup.js`, gated behind the
  `setup` project) only resets ONCE per invocation — it can't prevent this,
  regardless of where in the run it fires, because 15 requests in one budget
  window exceeds 5 no matter when the single reset happens.
- **A second, separate, unconfirmed issue surfaced by the same `--list` run**:
  `auth.spec.js`'s "Authentication Flows" describe block (`user is already
  logged in`, `can access protected routes when authenticated`, `can logout
  successfully`) assumes a logged-in session but is NOT restricted to the 2
  authenticated projects — it also lists under `chromium` / `firefox` /
  `webkit` / `Mobile Chrome` / `Mobile Safari`, none of which load the
  `storageState: '.auth/user.json'` those tests need. Whether these actually
  fail under those projects (rather than degrading gracefully via their own
  `isVisible().catch(() => false)` fallbacks) is **not yet confirmed** —
  flagging for whoever picks this up rather than guessing further.
- **Also surfaced in todo 312's code review, same root question**: even
  restricted to the 2 authenticated projects, `chromium-authenticated` and
  `firefox-authenticated` both load the identical `.auth/user.json`
  storageState with no dependency on each other, so under `fullyParallel:
  true` one project's "can logout successfully" can blacklist the shared
  refresh token while the other project's tests are still relying on it.
  Todo 312's `test.describe.configure({mode: 'serial'})` fix only serializes
  tests *within* one project's execution, not across the two authenticated
  projects when both run in the same invocation (e.g., the plain
  `npm run test:e2e` case this todo is already about).
- Ruled out as budget contributors (todo 312's investigation):
  `web/e2e/example.spec.js` and `quick-test.spec.js` only check login-page
  rendering and client-side validation — no real POST to `/api/v1/auth/login/`.

## Recommended Action

The root cause of both the rate-limit and the storageState-race findings is
the same: `auth.spec.js` runs under 7 projects when it was designed for 2.
Fix `web/playwright.config.ts`'s `testIgnore` regexes on the 5 unauthenticated
projects to also exclude `auth.spec.js` (matching how `forum-authenticated`
and `canopy-areas-authenticated` are already excluded there) — this is a
project-coverage decision (removes cross-browser exercise of the login/logout
smoke tests on firefox/webkit/mobile) that should be called out explicitly
when picking this up, not silently changed.

If that's judged too broad a coverage cut, the narrower alternative is
resetting the rate limit budget per-project rather than once per invocation
(more complex — no existing Playwright hook runs once per project before that
project's tests start) — weigh both before choosing.

Then verify: `npm run test:e2e` (no `--project` filter, the documented
default local command per `web/CLAUDE.md`) run twice in a row, both green.

## Acceptance Criteria

- [x] Confirmed whether "Authentication Flows" tests actually fail under the
      5 unauthenticated projects (not just budget-starved) — **they do**, 2 of 3;
      measured 2026-09-01, see Work Log
- [x] Fix landed (playwright.config.ts testIgnore scoping, or a per-project
      reset mechanism) for both the rate-limit and storageState-race findings
- [ ] `npm run test:e2e` run twice in a row, both green, no flake — **blocked by
      todo 331**, an unrelated pre-existing defect (Postgres connection
      exhaustion). The rate-limit property this todo is about *was* verified
      twice in a row: 4 login POSTs, 0x 429, both runs.

## Work Log

### 2026-09-01 - Implemented and verified

**AC-1 answered first, before any edit** (once the config change lands, the
question is no longer observable). Each test run individually under
`--project=chromium` — a single `-g "Authentication Flows"` run would have stopped
at the first failure under `mode: 'serial'` and answered only a third of it:

| Test | Verdict |
|------|---------|
| `user is already logged in` | **FAILS** — no user menu, no username |
| `can access protected routes when authenticated` | **FAILS** — redirected to `/login` |
| `can logout successfully` | passes **vacuously** via its own `else` branch |

So 2 of the 3 were genuinely failing under all 5 unauthenticated projects, not
merely budget-starved. Confirmed at 0 login-POST cost.

**Root cause, sharper than this todo's framing.** `auth.spec.js`'s two describe
blocks want *opposite* project sets: `Authentication Flows` needs the setup
`storageState`; `Protected Routes (Unauthenticated)` explicitly clears it and is
the only real consumer of the login budget. One file cannot be scoped two ways,
which is why the Recommended Action's `testIgnore`-only fix would have landed at
exactly 5/5 (zero headroom) *and* left the storageState race untouched.

**What shipped** (decisions confirmed with the user before implementing):

- Split by audience: `Protected Routes (Unauthenticated)` moved verbatim to a new
  `web/e2e/login.spec.js`, scoped to the `chromium` project alone; `auth.spec.js`
  keeps `Authentication Flows` and is matched only by the 2 authenticated projects.
- Per-project auth state: `setup` became `setup-chromium` + `setup-firefox`, each
  logging in separately and writing its own `.auth/user-<browser>.json` via a new
  `authFileFor()` in `e2e/config.js`. Kills the race structurally rather than
  ordering around it.

**Measured before vs after** — same machine, same servers, full unfiltered
`npm run test:e2e`, login POSTs counted from the Django access log:

| | `main` | this branch |
|---|---|---|
| `POST /api/v1/auth/login/` | **15** (2x401, 2x500, 3x200, **8x429**) | **4** (3x200, 1x401) |
| 429s | **8** | **0** |

15 is exactly the count this todo predicted. Two consecutive runs on the branch
both gave 4 POSTs / 0x 429.

**The race is verified gone, not merely untriggered.** A green run is consistent
with a shared token that simply didn't race, so the direct check: the two state
files carry *distinct* `refresh_token`, `access_token` and `csrftoken` values.

**Two things found along the way:**

- Firefox and WebKit browser binaries were never installed on this machine, so
  `firefox`, `webkit`, `Mobile Safari` and `firefox-authenticated` had been
  silently failing to launch. Installed (`playwright install firefox webkit`) —
  without them none of this is observable.
- AC-3 is blocked by **todo 331**: Postgres connection exhaustion under full
  parallelism (`FATAL: sorry, too many clients already`, 136x per run). Verified
  pre-existing and *worse* on `main` (78 failed / 234 errors) than on this branch
  (61 / 136), and verified not to be a defect in this change —
  `--project=chromium-authenticated` alone passes 7/7. Filed rather than folded
  in: it is a different defect with its own trade-offs.

### 2026-08-31 - Filed, then measured precisely during todo 312's code review

- Split out from todo 312 while fixing `auth.spec.js`'s two stale failures.
  That todo's own AC only required `--project=chromium-authenticated`, which
  is now fixed and verified (six consecutive green runs across two review
  rounds); this broader, distinct question about the full unfiltered suite
  was explicitly out of scope there.
- Originally filed as a rough p4 hypothesis. `cross-cutting-reviewer`'s
  review of todo 312's diff surfaced concrete, measured evidence (the exact
  project list and the 15-POST computation above) plus the related
  cross-project storageState-blacklist race — both accepted-and-deferred out
  of todo 312 rather than rushed into that PR, since the real fix
  (`playwright.config.ts` coverage-scoping) is a consequential decision, not
  a mechanical one. Raised to p3 given `npm run test:e2e` — the documented
  default local command — is now confirmed structurally guaranteed to exceed
  the rate-limit budget 3x over in a single run.
