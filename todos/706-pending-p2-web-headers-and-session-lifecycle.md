---
status: pending
priority: p2
issue_id: "706"
tags: [web, security, headers, cloudflare, auth]
dependencies: []
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
      max-age of at least 15552000 — record the date and both header lines.
- [ ] `curl -sI https://houseplant-md.com/settings` shows the CSP and
      `Referrer-Policy`, and the CMS blog preview still renders — record the
      date and result.
- [ ] After `/verify-email?key=…` and `/unsubscribe?token=…` load,
      `location.search` is empty (tests).
- [ ] The two-tab refresh race is reproduced or shown not to exist; if real, a
      test covers the fix.
- [ ] A Sentry event from production carries no query string — record the
      date and event id.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: headers can only be verified after a deploy, and a
  wrong `frame-ancestors` breaks the CMS preview.

## Notes

M1 is the quickest win here and needs no code.
