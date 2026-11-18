---
status: completed
priority: p2
issue_id: "706"
tags: [web, security, headers, cloudflare, auth]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Split (owner 2026-11-17): M7 replaceState, L10 OAuth origin check, report-only CSP + Referrer-Policy in web/public/_headers (frame-ancestors must allow https://api.houseplant-md.com), M18 two-tab repro ship now; Cloudflare HSTS (M1) and the post-deploy curl/Sentry checks move to todo 716"
---

# Web: HSTS, security headers, tokens in the address bar, session lifecycle

## Problem

Five web findings from the auth + legal audit of 2026-11-10 were not fixed in
its PR: two can only be checked on the live site, one is an owner console
setting, two need a design choice.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md` (rows named below).

- **M1** `houseplant-md.com` and `api.houseplant-md.com` both answer
  `strict-transport-security: max-age=0; includeSubDomains` (`curl -sI`,
  2026-11-10), which switches HSTS off, although Django sets one year
  (`settings.py:1528`). Hypothesis, not verified: the Cloudflare zone's HSTS
  setting overrides the origin.
- **M2** The web app is served with no CSP, no `frame-ancestors` and no
  `Referrer-Policy` (`wrangler.jsonc`; no `web/public/_headers`).
  `/delete-account/confirm`, `/verify-email` and `/settings` can be framed.
- **M7 (rest)** `/verify-email` and `/unsubscribe` leave the single-use token
  in the address bar and history (`VerifyEmailPage.tsx:192`,
  `UnsubscribePage.tsx:64`). The Sentry half of M7 shipped with the audit,
  checked by unit tests only.
- **M18** Two tabs refreshing at once can log one out; a network blip or 5xx
  on refresh logs out; a failed logout still shows "logged out"; no global 401
  handling (`web/src/contexts/AuthContext.tsx:253-264,401-407`). The two-tab
  race is a hypothesis, not reproduced.
- **L10** The whole user object sits in `sessionStorage` past expiry;
  cross-tab logout waits for focus + 30 s; `oauth_url` from the server is
  followed without an origin check (`authService.ts:119,198,304`,
  `GoogleSignInButton.tsx:61`).

## Recommended Action

1. M1 (owner): in the Cloudflare zone, set HSTS max-age to at least six
   months, or turn the zone setting off so the origin's header passes.
2. M2: add `web/public/_headers` with `Referrer-Policy`,
   `X-Content-Type-Options` and a CSP. The CMS frames `/blog/preview` from
   the API origin, so `frame-ancestors 'self' https://api.houseplant-md.com`.
   Ship the CSP as report-only first.
3. M7: `history.replaceState` the token away once it is read on both pages.
4. M18: reproduce the two-tab race in Playwright before changing anything;
   then one refresh at a time across tabs (Web Locks), and log out only on a
   401 from refresh.
5. L10: check `oauth_url` against the API origin before following it.

## Technical Details

- Running Playwright from a worktree: `reuseExistingServer` serves whatever is
  on :5174; stop the main checkout's server first.
- After deploy, confirm one event in Sentry has no query string (the M7 fix).

## Acceptance Criteria

- [ ] `curl -sI https://houseplant-md.com` and the API host show an HSTS
      max-age of at least 15552000 — record the date and both header lines. → todo 716 (re-pointed 2026-11-17)
- [ ] `curl -sI https://houseplant-md.com/settings` shows the CSP and
      `Referrer-Policy`, and the CMS blog preview still renders — record the
      date and result. → todo 716 (re-pointed 2026-11-17)
- [x] After `/verify-email?key=…` and `/unsubscribe?token=…` load,
      `location.search` is empty (tests).
- [x] The two-tab refresh race is reproduced or shown not to exist; if real, a
      test covers the fix.
- [ ] A Sentry event from production carries no query string — record the
      date and event id. → todo 716 (re-pointed 2026-11-17)
- [x] `web/public/_headers` sets `Referrer-Policy`, `X-Content-Type-Options`
      and a report-only CSP whose `frame-ancestors` is
      `'self' https://api.houseplant-md.com` (a test reads the file).
- [x] L10: an `oauth_url` whose origin is not `https://accounts.google.com`
      (the origin `apps/users/oauth_views.py` builds it on) is not followed (test).

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: headers can only be verified after a deploy, and a
  wrong `frame-ancestors` breaks the CMS preview.

### 2026-11-17 - Triage: split (owner decision)

- The code slice ships here: M7 replaceState, the report-only CSP and
  `Referrer-Policy` in `web/public/_headers`, the M18 two-tab repro, and the
  L10 origin check (criteria added for `_headers` and L10). The Cloudflare
  HSTS change (M1) and the three post-deploy checks move to todo 716.

### 2026-11-18 - L10 criterion corrected

- The triage wording said "outside the API origin", but the backend builds
  `oauth_url` on `https://accounts.google.com` (`oauth_views.py:141`), so an
  API-origin check would break Google sign-in. Corrected to Google's origin,
  which is what the finding (follow `oauth_url` only after an origin check)
  needs. Owner delegated the call on 2026-11-17 ("do what you think is best
  and gets the job done").

### 2026-11-18 - Implemented by the todo sweep (run 2026-11-18-0148)

- M7: new `web/src/hooks/useOneTimeSearchParam.ts` holds the token in state
  and strips it from the URL with a replace navigation (other params stay);
  `VerifyEmailPage` and `UnsubscribePage` use it. Tests use a real
  `BrowserRouter`, since `MemoryRouter` never touches `window.location`; they
  fail with the strip disabled.
- M18: the race is real, reproduced against the real view in
  `backend/apps/users/tests/test_refresh_rotation_race.py` (interleave forced:
  tab B sends the refresh cookie from before tab A's rotation and gets 401; the
  refusal clears no cookies). Fix: `refreshSession()` in `authService.ts`
  holds a Web Lock across the request, so `refreshAccessToken()` (also used by
  the live socket) is serialized across tabs; `AuthContext` logs out only on
  400/401 and keeps the session on a network error or 5xx. A Playwright repro
  was not run: no servers were up and the sandbox blocks loopback.
- M2: `web/public/_headers` sets `Referrer-Policy:
  strict-origin-when-cross-origin`, `nosniff` and a report-only CSP with
  `frame-ancestors 'self' https://api.houseplant-md.com`; no `X-Frame-Options`
  (it would break the CMS preview). Report-only blocks nothing and has no
  report endpoint, so violations show only in the browser console.
- L10: `web/src/utils/oauthOrigin.ts` compares `new URL(u).origin` exactly
  with `https://accounts.google.com`, checked in `getGoogleOAuthUrl` and again
  in `GoogleSignInButton` before `location.assign`. One existing test used
  `https://g/x` as an OAuth URL and now uses a Google URL.
- Not done here (no criterion, not in the owner's split): failed-logout UI,
  global 401 handling, the sessionStorage user past expiry, faster cross-tab
  logout.

### 2026-11-18 - Verified by the todo sweep (run 2026-11-18-0148)

- AC 3: `npm --prefix web exec -- vitest run --root web src/pages/VerifyEmailPage.test.tsx src/pages/UnsubscribePage.test.tsx --reporter=verbose` — evidence `.sweep-evidence/g5/706-ac2.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  21 passed (21)
     Start at  23:07:57
     Duration  639ms (environment 45%, tests 30%, import 13%, setup 9%, transform 3%, worker 1%)
  ```

- AC 4: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest apps/users/tests/test_refresh_rotation_race.py --create-db -v -p no:cacheprovider && npm --prefix web exec -- vitest run --root web src/services/authService.test.ts src/contexts/AuthContext.test.tsx -t "M18" --reporter=verbose'` — evidence `.sweep-evidence/g5/706-ac3.txt` (not committed), last lines:

  ```text
  ======================== 2 passed, 3 warnings in 20.88s ========================
  …

   Test Files  2 passed (2)
        Tests  13 passed | 96 skipped (109)
     Start at  23:12:36
     Duration  541ms (environment 56%, tests 28%, setup 10%, import 2%, transform 2%, worker 1%)
  ```

- AC 6: `npm --prefix web exec -- vitest run --root web src/tests/securityHeaders.test.ts --reporter=verbose` — evidence `.sweep-evidence/g5/706-ac5.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  4 passed (4)
     Start at  23:12:37
     Duration  334ms (environment 81%, setup 15%, transform 2%, worker 1%, tests 1%, import 1%)
  ```

- AC 7: `npm --prefix web exec -- vitest run --root web src/services/authService.test.ts src/components/auth/GoogleSignInButton.test.tsx -t "origin|accounts.google.com" --reporter=verbose` — evidence `.sweep-evidence/g5/706-ac6.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  15 passed | 66 skipped (81)
     Start at  23:08:04
     Duration  431ms (environment 69%, setup 12%, tests 12%, transform 3%, import 2%, worker 1%)
  ```

### 2026-11-18 - Completed by the todo sweep (run 2026-11-18-0148)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

M1 is the quickest win here and needs no code.
