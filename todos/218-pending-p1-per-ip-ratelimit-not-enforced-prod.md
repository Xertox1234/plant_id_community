---
status: pending
priority: p1
issue_id: "218"
tags: [security, rate-limiting, deployment, railway]
dependencies: []
---

# Per-IP rate limiting is not enforced in production (django-ratelimit `key="ip"` behind Railway's proxy)

## Problem

Live verification on 2026-06-06 found that the per-IP rate limits on the auth
endpoints **do not trigger in production**. The account-lockout layer (per
username) works, but the `key="ip"` django-ratelimit decorators silently fail to
accumulate, so endpoints like login/register have **no per-IP throttling** in
prod — a security control we believe is on but isn't.

## Findings (primary-source, live)

Probed `POST /api/v1/auth/login/` against the live backend with a throwaway
username + wrong password, valid CSRF (`Origin`/`Referer` same-origin), from a
**stable** egress IP (`173.209.123.179`, confirmed constant across requests):

- **13 attempts in one 15-min window → zero `rate_limit_exceeded` 429.** The
  login decorator is `@ratelimit(key="ip", rate="5/15m")` — it should have
  blocked at the 6th. It never did.
- **The per-username lockout DID fire** — `429 {"code":"ACCOUNT_LOCKED"}` at the
  10th cumulative failure, and stayed locked thereafter. Lockout counts via the
  **same Redis cache**, so the cache and counting work — this isolates the
  failure to the **IP key**, not the cache.
- CSRF protection also confirmed working (un-origin'd POSTs got 403 before
  reaching the view).

**Root cause:** `django-ratelimit`'s `key="ip"` keys on
`request.META["REMOTE_ADDR"]`, which behind Railway's proxy is the *proxy*
address, not the real client IP carried in `X-Forwarded-For`. With no
XFF→client-IP resolution, the per-IP counter never accumulates per real client,
so the limit is ineffective. (`TRUST_PROXY_SSL_HEADER=True` only affects HTTPS
detection — it does not rewrite `REMOTE_ADDR`.)

**Blast radius:** every `key="ip"` limit — `auth_endpoints` in
`apps/plant_identification/constants.py` RATE_LIMITS: login `5/15m`, register
`3/h`, token_refresh `10/h`, firebase_token_exchange `10/m`, password_reset
`3/h`. The `key="user"` limits (garden/calendar viewsets) are unaffected (they
key on the authenticated user), and the per-username account lockout works.

## Impact

No per-IP throttling on internet-facing auth endpoints in prod:

- **Unlimited registration** (the `3/h` cap is ignored) → account/spam abuse.
- **Credential stuffing across many usernames from one IP** isn't throttled
  (single-account password guessing is still stopped by the username lockout).
- token_refresh / firebase-exchange abuse; general DoS surface.

Partially mitigated by the working per-username lockout for single-account
brute-force — but the IP layer is a deliberate control that's silently off.

## Recommended Action

1. **Confirm what prod sees** — log `request.META["REMOTE_ADDR"]` and
   `HTTP_X_FORWARDED_FOR` once on an auth request to see Railway's exact shape
   (how many proxy hops, where the real client IP sits).
2. **Key rate limits on the real client IP from a TRUSTED `X-Forwarded-For`.**
   Either (a) a custom key function in `apps/core/ratelimit.py` used in place of
   `key="ip"`, or (b) a vetted middleware (e.g. `django-ipware`) that sets
   `REMOTE_ADDR` from the trusted XFF hop so `key="ip"` works unchanged.
3. **CRITICAL — proxy trust / anti-spoofing.** `X-Forwarded-For` is
   client-controllable; a forged header must NOT let an attacker rotate the key
   and bypass the limit. Trust only the hop Railway appends (a fixed number of
   trusted proxies / the rightmost trusted entry), never the leftmost client
   value blindly.
4. **Re-verify live:** a burst from one IP must return `429 rate_limit_exceeded`
   with a `Retry-After` header after the limit, and a spoofed `X-Forwarded-For`
   must not evade it.

## Technical Details

- Decorators: `apps/users/views.py:157` (login), `:91` (register); rates in
  `apps/plant_identification/constants.py` `RATE_LIMITS["auth_endpoints"]`.
- Wrapper `apps/core/ratelimit.py` is correct (preserves the rate for
  Retry-After); handler `apps/core/exceptions.py` is correct (429 + Retry-After,
  window derived from the rate). Both are fine — the gap is purely IP resolution.
- Lockout (working): `apps/core/security.py` + `apps/users/views.py:178,260`
  (per-username, threshold 10, 1-hour lock, returns 429 `ACCOUNT_LOCKED`).

## Acceptance Criteria

- [ ] A burst above the limit from one IP returns `429 rate_limit_exceeded` +
      `Retry-After`, verified against the live backend.
- [ ] A forged `X-Forwarded-For` does NOT let a client evade the per-IP limit.
- [ ] Client-IP derivation is centralized and trusted-proxy-aware (one helper,
      reused by all `key="ip"` limits).
- [ ] A test pins the client-IP-from-XFF behavior (incl. the spoofing-rejection
      case).

## Work Log

### 2026-06-06 - Filed (verified live)

- Found while verifying todo 216 item 3. Account lockout verified working
  (429 ACCOUNT_LOCKED at 10 failures); per-IP rate limiting found NOT enforced
  (13 attempts from a stable IP, no rate_limit_exceeded). Cache works (lockout
  proves it) → root cause is the IP key behind Railway's proxy.

## Notes

p1: an internet-facing security control that's silently disabled in production,
relevant before opening to testers. Primary brute-force vector (single account)
is still covered by the username lockout, which is why this isn't p0.
