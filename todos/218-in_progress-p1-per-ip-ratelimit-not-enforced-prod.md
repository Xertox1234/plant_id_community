---
status: in_progress
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
      `Retry-After`, verified against the live backend. (LIVE-VERIFY pending —
      requires Railway deploy + setting `RATELIMIT_TRUSTED_PROXY_COUNT`.)
- [ ] A forged `X-Forwarded-For` does NOT let a client evade the per-IP limit.
      (Code-level property proven by test `test_spoof_cannot_rotate_the_key`;
      LIVE-VERIFY against the real backend still pending.)
- [x] Client-IP derivation is centralized and trusted-proxy-aware (one helper,
      reused by all `key="ip"` limits). (done 2026-06-21 — `client_ip_key` /
      `get_trusted_client_ip` in `apps/core/ratelimit.py`; all 8 `key="ip"`
      decorators across users/oauth/firebase/forum_host wired to it; `grep` shows
      0 bare `key="ip"` remain; `manage.py check` clean.)
- [x] A test pins the client-IP-from-XFF behavior (incl. the spoofing-rejection
      case). (done 2026-06-21 — `apps/core/tests/test_ratelimit_client_ip.py`,
      17 tests incl. spoof-rotation rejection, IPv6 /64 masking, and the M1
      `IP:port` / bracketed-IPv6 → REMOTE_ADDR fallback (added in PR #377 review);
      full run green with the rate-limit regression suite.)

## Work Log

### 2026-06-21 - Started by completing-todos skill (run 2026-06-21-1412)

- Picked up by automated workflow. Scope for this run: implement the centralized
  trusted-proxy-aware client-IP helper + spoofing-rejection test (acceptance
  criteria 3 & 4). Criteria 1 & 2 require live-Railway verification and are
  deferred to a deploy step — this todo stays `in_progress` after this run.

### 2026-06-21 - Implemented helper + tests (criteria 3 & 4 done); LIVE-VERIFY pending

**Implementation.** Added a trusted-proxy-aware client-IP resolver in
`apps/core/ratelimit.py`:

- `get_trusted_client_ip(request)` — reads `X-Forwarded-For`, counts
  `settings.RATELIMIT_TRUSTED_PROXY_COUNT` hops from the RIGHT, and returns the
  entry at that position (the address the outermost trusted proxy observed).
  Indexing from the right means left-prepended (spoofed) entries can't shift the
  result. Falls back to `REMOTE_ADDR` when XFF has fewer entries than the proxy
  count or the trusted-position value isn't a valid IP.
- `client_ip_key(group, request)` — django-ratelimit key callable; resolves via
  the above and masks to the rate-limit network (`_mask_ip`).
- `RATELIMIT_TRUSTED_PROXY_COUNT` added to settings (env-driven, **default 0** →
  `REMOTE_ADDR`, so dev/test/local are unchanged; clamped `max(0, …)`).
- Wired ALL 8 `key="ip"` decorators to `key=client_ip_key`: register/login/
  token_refresh (`users/views.py`), firebase_token_exchange
  (`firebase_auth_views.py`), 2× oauth (`oauth_views.py`), forum search/sync
  (`forum_host/api.py`). `grep` confirms 0 bare `key="ip"` remain; `key="user"`
  limits untouched. `manage.py check` clean.

**Code review (security/django agent) → one HIGH fixed before landing:**

- **H1 (IPv6 evasion regression) — FIXED.** django-ratelimit's own `key="ip"`
  masks IPv6 to `RATELIMIT_IPV6_MASK` (default /64) via `_get_ip`
  (verified in `django_ratelimit/core.py:53-60`). My first cut returned the full
  /128, so an IPv6 client could rotate the low 64 bits to evade the limit — a
  regression vs. the code being replaced. Added `_mask_ip` (IPv4 /32, IPv6 /64,
  same overridable settings) so `client_ip_key` is a true drop-in; added 4 IPv6
  tests (two addresses in one /64 → same bucket).
- **L1 (negative proxy count) — hardened** with `max(0, …)` in settings.
- **M1 (Railway may append `IP:port` / bracketed IPv6) — LIVE-VERIFY item.** Not
  a bypass (non-IP in the trusted slot falls back to `REMOTE_ADDR` = the proxy,
  not attacker-controlled — safe over-throttle). If prod XFF carries ports,
  strip them before validation. Confirm the real XFF shape during deploy.

**Verification:** `apps/core/tests/test_ratelimit_client_ip.py` 15 tests +
rate-limit regression = 22 passed; full auth/lockout/firebase/retry-after set
(83 tests) green earlier — no regressions.

**Still OPEN — operational, before this actually closes (criteria 1 & 2):**

1. Deploy; log one auth request's `REMOTE_ADDR` + `HTTP_X_FORWARDED_FOR` to learn
   Railway's true hop count and IP format (Recommended-Action item 1).
2. Set `RATELIMIT_TRUSTED_PROXY_COUNT` on Railway to that confirmed count. **Until
   set (default 0), the prod bug is INERT — everyone still shares the proxy's
   REMOTE_ADDR bucket.** This env step is what flips the fix on.
3. Live-verify: a burst from one IP returns `429 rate_limit_exceeded` +
   `Retry-After`; a spoofed `X-Forwarded-For` does not evade it. Then flip
   criteria 1 & 2 and complete this todo.

### 2026-06-06 - Filed (verified live)

- Found while verifying todo 216 item 3. Account lockout verified working
  (429 ACCOUNT_LOCKED at 10 failures); per-IP rate limiting found NOT enforced
  (13 attempts from a stable IP, no rate_limit_exceeded). Cache works (lockout
  proves it) → root cause is the IP key behind Railway's proxy.

## Notes

p1: an internet-facing security control that's silently disabled in production,
relevant before opening to testers. Primary brute-force vector (single account)
is still covered by the username lockout, which is why this isn't p0.
