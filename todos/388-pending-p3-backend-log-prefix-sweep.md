---
status: pending
priority: p3
issue_id: "388"
tags: [code-quality, logging, backend, tech-debt]
dependencies: []
source_review: "todos/archive/361-completed-p4-logging-and-stale-comment-cleanup.md"
---

# Backend log-prefix sweep — 357 unprefixed calls across 41 files

## Problem

`docs/rules/api.md:13-14` makes bracketed log prefixes a binding rule:

> - **Bracketed log prefixes** — `logger.info("[CACHE] ...")`, `[AUTH]`, `[PLANT_ID]`
>   — so logs are greppable by subsystem.

`backend/apps/` is **46.4% non-compliant**: 357 of 769 judgeable `logger.*`
calls carry no prefix. This was promoted out of todo 361, which measured it and
re-scoped rather than sweeping 41 files inside a p4.

**The debt is legacy-only.** `backend/packages/wagtail_forum` — the newest code
— is 26 prefixed / 1 unprefixed (96% compliant). The convention holds in new
code; it was never retrofitted to the older apps.

## Measured scope (2026-09-13, todo 361)

AST parse of every non-test `.py` under `backend/apps/`, testing each
`logger.*` call's first-argument literal against `^\s*\[[A-Z0-9_]+\]`.
Multi-line calls, f-strings and `%`-format strings handled. Detector was
positive-controlled against a known-prefixed call, not only negative-controlled.

| App | Unprefixed | Prefixed | Suggested slice |
| --- | --- | --- | --- |
| `plant_identification` | 182 | 96 | 3 slices (services / views / rest) |
| `users` | 84 | 12 | 1 slice — **auth-sensitive, review carefully** |
| `core` | 62 | 5 | 1 slice — includes `core/security.py` (19) |
| `blog` | 22 | 84 | 1 slice |
| `garden_calendar` | 4 | 51 | fold into another slice |
| `forum_host` | 3 | 72 | fold into another slice |
| `garden` | 0 | 92 | nothing to do |

Top files: `users/firebase_auth_views.py` 21, `plant_identification/services/trefle_service.py` 21,
`core/security.py` 19, `users/services.py` 19, `users/oauth_views.py` 18,
`plant_identification/services/species_lookup_service.py` 18.

Prefix tokens already in use (~30): `[CACHE]` 80, `[ERROR]` 58, `[FIREBASE]` 32,
`[PERF]` 31, `[FCM]` 31, `[QUOTA]` 27, `[CIRCUIT]` 17, `[SECURITY]` 17,
`[RATE_LIMIT]` 9, plus `[LOCK]`, `[AUTH]`, `[PLANT_ID]`, `[SPAM]`, `[CSRF]`, `[EMAIL]`, `[CELERY]`.

## Do not re-derive these

Two claims inherited from GitHub issues #185/#186 were **falsified** by the
todo-361 measurement. They are recorded here so nobody re-inherits them:

1. The issue's **"5% of log statements are unprefixed" is really 46.4%** — off
   by ~9x, and never re-measured before todo 361.
2. Todo 361's own spot-check of `plant_id_service.py` ("3 unprefixed against 1
   prefixed") is really **7 unprefixed against ~20 prefixed**.

**A structural fix was considered and rejected.** A logging `Filter`/`Formatter`
that injects a prefix derived from the logger name cannot reproduce this
convention: `plant_id_service.py` alone emits `[LOCK]` (:120), `[CACHE]`
(:176, :414) and `[QUOTA]` (:189) from a single module. A module-derived prefix
would flatten all three *and* double-prefix the 412 already-correct calls.
Prefixes are semantic per call site, so they can only be added by hand. (There
are also no custom logging Filter/Formatter classes in the repo today — one
would be the first.)

## Recommended Action

1. Sweep app by app, smallest first, one PR per slice. `garden` needs nothing.
2. **Add a `docs/rules/triggers.json` entry** for the unprefixed-logger rule —
   see the gap below. Do this *first* so new code stops adding to the debt while
   the sweep runs.
3. Re-run the todo-361 detector after each slice to show the count dropping.

## Technical Details

### The rule is documented but unenforced

`docs/rules/api.md:13-14` and `docs/rules/caching.md:13` state the convention in
prose, and both are auto-injected by `inject-patterns.sh`. But **no
`triggers.json` entry enforces it**. Only two logging-adjacent triggers exist:

- index 81 `caplog-on-non-propagating-logger` (domain `testing`)
- index 93 `connection-url-in-log` (domain `security`)

Per this repo's convention, a recurring mistake gets a trigger, not just prose.
Note the 8800-byte injection cap: `api.md` must stay under it for the rule to
actually reach an edit, so prefer a `triggers.json` entry over lengthening the
rule file.

### Tests that read log content — 17 assertions across 11 files

**Adding a prefix to a currently-unprefixed call is safe for all 17. Rewording
the message is not.** Do not reword while prefixing.

*Prefix-sensitive (6)* — assert a bracket token is present:
`apps/forum_host/tests/test_rag_index_tasks.py:126,308` (`[CELERY]`),
`apps/blog/tests/test_blog_viewsets_caching.py:146,191` (`[PERF]` + "cached response"),
`apps/blog/tests/test_ai_cache_service.py:191` (`[CACHE]`),
`packages/wagtail_forum/.../test_digest.py:428` (`[EMAIL] forum digest failed` — prefix *and* prose).

*Prose-sensitive (11)*: `forum_host/tests/test_signals.py:722,827,854`,
`test_topic_redirects.py:196,360,583`, `test_search_hits.py:88`,
`test_tasks.py:864`, `wagtail_forum/.../test_image_references.py:80-82,101,110`,
`plant_identification/tests/test_error_body_exposure.py:127-128`,
`core/tests/test_ratelimit_client_ip.py:188-200`,
`users/tests/test_ip_spoofing_protection.py:184-186`.

### The `caplog` trap

`apps.*`, `django.*` and `plant_community_backend.*` all set `propagate=False`
(`backend/plant_community_backend/settings.py:1086-1107`), so **bare `caplog`
never sees those records** and a "logs a prefixed warning" assertion passes
green-by-emptiness. Existing tests work around it with
`log.addHandler(caplog.handler)` (`test_search_hits.py:79`,
`test_topic_redirects.py:187`) or a private StreamHandler
(`test_error_body_exposure.py:66-76`). `triggers.json` index 81 already guards
this — heed it when writing any new prefix test.

### Unrelated dead code found while measuring

`backend/plant_community_backend/settings.py:839-851` is a verbatim duplicate of
the `ENABLE_FILE_LOGGING` cleanup block at `:1112-1123`. The first copy runs
*before* `LOGGING` is defined (`:1015`), so when `ENABLE_FILE_LOGGING` is False
it raises `NameError` — silently swallowed by a bare `except Exception: pass`
at `:850-851`. It has no effect, and reads as functional to anyone editing the
logging config. Delete it as a drive-by in whichever slice touches settings.

## Acceptance Criteria

- [ ] A `docs/rules/triggers.json` trigger flags an unprefixed `logger.*` call
      in `backend/**/*.py`, and its target path is confirmed to route by running
      it through `scripts/inject/route_domains.py`
- [ ] `plant_identification`, `users`, `core` and `blog` unprefixed counts all
      reach 0, verified by re-running the todo-361 detector
- [ ] No log message was **reworded** during prefixing (only prefixed) — the 17
      content assertions above still pass
- [ ] Backend suite green on each slice

## Notes

p3, not p4: the count is 9x what the source issue claimed, it spans
security-sensitive (`core/security.py`) and auth (`users/`) logging, and the
rule is binding but unenforced so the debt grows. Sliceable per app by design —
this is not a parking epic, and promote-all is the only terminal state if it
ever becomes one.

## Work Log

### 2026-09-13 - Promoted out of todo 361

- Todo 361 measured the gap (AC 2) and took its explicit "or the item explicitly
  re-scoped with a reason" branch (AC 3) rather than sweeping 41 files in a p4.
- Carried forward: corrected counts, per-app breakdown, both falsified claims,
  the rejected structural fix, the test-assertion constraint, and the `caplog`
  trap — so none of it has to be re-derived.
