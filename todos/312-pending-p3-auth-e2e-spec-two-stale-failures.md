---
status: pending
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

- [ ] `auth.spec.js:16` ("user is already logged in") passes against
      current header markup
- [ ] `auth.spec.js:107` ("shows error with invalid credentials") passes,
      with the actual root cause (timing vs. lockout vs. something else)
      identified and documented in the Work Log, not just patched blind
- [ ] `npx playwright test --project=chromium-authenticated` run twice in a
      row, both green, no flake

## Work Log

### 2026-08-17 - Filed

- Filed by Claude following Canopy PR 4 (#558, merged 2026-08-17). Both
  failures were surfaced (not caused) by that branch's Task 8 e2e run;
  filing was deferred past the merge and is done now.

## Notes

- p3: both are pre-existing e2e-only failures with no production user
  impact confirmed — `auth.spec.js`'s scope is smoke coverage, and the
  app's actual login flow is exercised successfully by
  `auth.spec.js:89` ("can login with valid credentials", which passes) and
  by every other authenticated e2e spec's `auth.setup.js` step.
- Related: Canopy PR 4 / #558
  (`docs/superpowers/plans/2026-08-16-canopy-areas.md`, Task 7/8), sibling
  todo 311 (also filed from the same PR's follow-ups).
