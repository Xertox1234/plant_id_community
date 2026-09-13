---
status: in_progress
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

Produced by **`scripts/check_log_prefixes.py`** (committed with this todo, so
every later count is comparable to this baseline):

```
python3 scripts/check_log_prefixes.py
357 unprefixed of 769 judgeable (46.4%), 41 files
```

It AST-parses every non-test `.py` under `backend/apps/`, testing each
`logger.*` call's first-argument literal against `^\s*\[[A-Z0-9_]+\]`.
Multi-line calls, f-strings and `%`-format strings are handled; a first
argument that is not a literal is reported as undeterminable and excluded from
the ratio rather than guessed at. The script's docstring states each rule and
its limitation. It was positive-controlled against a known-prefixed call, not
only negative-controlled.

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
3. After each slice, prove the count dropped:

   ```
   python3 scripts/check_log_prefixes.py --app <name> --fail-over 0
   ```

   Exits 1 while any unprefixed call remains in that app, so it can gate CI.
   `--list` prints every remaining call site with its level and message head.

## Technical Details

### The rule is documented but unenforced

`docs/rules/api.md:13-14` and `docs/rules/caching.md:13` state the convention in
prose, and both are auto-injected by `inject-patterns.sh`. But **no
`triggers.json` entry enforces it**. Only two logging-adjacent triggers exist:

- index 81 `caplog-on-non-propagating-logger` (domain `testing`)
- index 93 `connection-url-in-log` (domain `security`)

Per this repo's convention, a recurring mistake gets a trigger, not just prose.

**The prose is demonstrably not enough here — proven, not assumed.** The
obvious hypothesis was that the 8800-byte injection cap truncates the rule away
(`api.md` is 16640 B, and `_discipline.md` takes 4426 B of the budget). It does
not. Verified 2026-09-13 by *running the hook*, not by reading
`route_domains.py`:

```
$ route_domains.py backend/apps/users/services.py
api,security,database

$ inject-patterns.sh <<< '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/services.py",...}}'
injected payload: 9192 bytes
occurrences of "Bracketed log prefixes": 1
```

The rule sits at byte offset 677 of `api.md`, survives the cut, and **is
injected on every edit to `users/services.py`** — the second-worst offender at
84 unprefixed calls. So the rule reaches the developer and is ignored anyway.
That is the argument for a `triggers.json` entry, which fires a targeted
message at the specific offending line, rather than for more prose.

### Tests that read log content — 17 assertions across 12 files

**Adding a prefix to a currently-unprefixed call is safe for all 17. Rewording
the message is not.** Do not reword while prefixing.

*Prefix-sensitive (6)* — assert a bracket token is present:
`apps/forum_host/tests/test_rag_index_tasks.py:126,308` (`[CELERY]`),
`apps/blog/tests/test_blog_viewsets_caching.py:147,195` (`[PERF]` + "cached response"),
`apps/blog/tests/test_ai_cache_service.py:193` (`[CACHE]`),
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

- [x] A `docs/rules/triggers.json` trigger flags an unprefixed `logger.*` call
      in `backend/**/*.py`, and its target path is confirmed to route by running
      it through `scripts/inject/route_domains.py`
- [ ] `plant_identification`, `users`, `core` and `blog` unprefixed counts all
      reach 0, verified by
      `python3 scripts/check_log_prefixes.py --app <name> --fail-over 0`
      exiting 0 for each of the four
      — **`core` DONE** (44 -> 0); `plant_identification` 182, `users` 84,
      `blog` 22 remain, one slice each
- [ ] No log message was **reworded** during prefixing (only prefixed) — the 17
      content assertions above still pass
- [ ] Backend suite green on each slice

Left in place, out of scope: **7 stale fix-attribution markers** of the same
family survive in `backend/apps/blog/`, verified 2026-09-13:

| Marker | Location |
| --- | --- |
| `BLOCKER 3` | `blog/constants.py:36`, `blog/middleware.py:109,144,153` |
| `BLOCKER 1` | `blog/middleware.py:98` |
| `BLOCKER 2` | `blog/tests/test_analytics.py:15` |
| `TODO 037` | `blog/tests/test_analytics.py:487` |

Todo 361 deliberately scoped itself to `TODO 040` (its AC), so these were not
swept. Clear them as a drive-by in whichever slice touches `blog`.

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

### 2026-09-13 - Trigger + the `core` slice (PR pending review)

Scoped per Recommended Action 1 ("sweep app by app, one PR per slice") and
Action 2 ("add the trigger first"). This PR is the trigger plus one slice; three
app slices remain.

**The 357 baseline was 18 too high.** Corrected to **339 of 769 (44.1%)**, 39
files. Every correction is in `core`, which read as 92.5% non-compliant and is
really 65.7% — 44 real violations, not 62. Three checker blind spots, each found
by doing the work rather than by re-reading the script:

| Shape | Count | Why it was miscounted |
| --- | --- | --- |
| `f"{LOG_PREFIX_RATELIMIT} ..."` | 15 | `apps/core/constants.py:74-83` defines ten `LOG_PREFIX_*` constants holding real bracketed values; the checker treated "f-string opens with an interpolation" as unprefixed |
| `[RATELIMIT-RESOLVE]` | 1 | the token pattern was `[A-Z0-9_]+`, so a hyphen disqualified a real prefix |
| `logger.debug("%s ...", LOG_PREFIX_SECURITY, exc)` | 2 | the prefix arrives as the first **%-format argument**; the rendered line was always compliant |

"Fixing" those 18 would have edited correct code, and the third shape would have
produced `[SECURITY] [SECURITY] username extraction failed`. Both scripts now
recognise all three.

**Two process lessons, both from output rather than from counters.**

1. The first `--apply` printed **"prefixed 46" and wrote 9.** An f-string *chunk*
   reports the `col_offset` of its own text, not of the enclosing quote — unlike
   every other shape — so the splice hit a `continue` that skipped silently while
   still counting the edit. That branch now **raises**. The shortfall was caught
   by `--fail-over 0`, which is the argument for writing an acceptance criterion
   as a command rather than as a description.
2. The double-prefix was caught by **spot-reading the diff**. Both counters
   agreed at 46 and both were wrong, so no amount of re-running them would have
   surfaced it.

Delivered:

- `docs/rules/triggers.json` — `unprefixed-logger-call`, appended as text (a
  `json.dumps` of the whole document reflows all 106 existing entries). Verified
  by **running the hook**, not `route_domains.py`: positive on an unprefixed call
  in `backend/apps`, positive on `backend/packages`, silent on a prefixed call,
  silent outside `backend`, silent on a non-literal first argument. End-to-end
  through `inject-patterns.sh` it lands in a 9411-byte payload — it survives the
  8800-byte cap — and the fire is recorded in `~/.claude/inject-fires.log`. The
  regex was unit-checked against 13 shapes, 0 mismatches.
- `scripts/check_log_prefixes.py` — all three shapes, corrected baseline.
- `scripts/add_log_prefixes.py` — the mechanical half, driven by an explicit
  per-file token table. Prefix only: no rewording, no f-string→`%s`, no
  `exception`/`error` changes, no reflowing.
- 18 pre-existing flake8 violations in `core`'s files, cleaned as their own
  commit (pre-commit lints whole staged files, so they would have blocked the
  sweep). Measured at 18 first, which is what made cleaning them the right call
  rather than `SKIP=flake8`.
- The `core` slice: **44 calls, count now 0.**

Verification (all re-run after black re-wrapped 5 files):

| Check | Result |
| --- | --- |
| `check_log_prefixes.py --app core --fail-over 0` | **exit 0** (was 44) |
| repo-wide | 339 -> **295** unprefixed, 39 -> **32** files |
| `logger.*` calls in the 7 files | 59 before, **59** after |
| second `--check` run | "would prefix 0" (idempotent) |
| double-prefix grep | none |
| `compileall apps/core` | OK |
| flake8 on the 7 swept files | clean |
| `pytest apps/core apps/users` | **357 passed** |

Deliberately not changed: `core/security.py` now reads
`"[SECURITY] SECURITY ALERT [...]"`, which is redundant. Rewording is unsafe
during a prefix sweep, so the prefix went on and the wording stayed.

Also not done here, and still open: the `blog` drive-bys (7 stale `BLOCKER`/
`TODO 037` markers) belong with the `blog` slice, and the duplicate
`ENABLE_FILE_LOGGING` block in `settings.py:839-851` belongs with whichever
slice touches settings — no slice here did.

### 2026-09-13 - A fourth checker blind spot, found while scoping the next slice

`forum_host/tasks.py:71` is `logger.info("%s (task=%s)", line, self.request.id)`
— it **relays a line from a management command's stdout**, and that line already
carries its own prefix (`test_tasks.py:857`'s fake writes
`"[EMAIL] digest frequency=..."`). Prefixing the literal would render
`[FORUM] [EMAIL] digest ...`.

This one is **not fixable by the checker**: the prefix lives in a runtime value,
so no static rule can see it, and a rule like "first argument is exactly `%s …`"
would suppress real violations. It is also not fixable by prefixing. The call is
correct as written.

Consequence: **`forum_host` cannot reach 0** — it stays at 1 of 75. That is fine;
`forum_host` is a fold-in, not one of the four apps the acceptance criteria name.
Recorded so the next person does not "fix" a working relay, and so a future
`--fail-over 0` on `forum_host` is known to be unsatisfiable.

Running total of checker corrections: 15 constant-prefix + 1 hyphen + 2
format-arg (all fixed) + 1 runtime relay (unfixable, documented).

### Next slice is blocked on this PR merging

`blog` (22 calls in `api_views.py`, `services/plant_data_lookup_service.py`,
`management/commands/populate_plant_images.py`) was scoped and is ready:
7 pre-existing flake8 violations, no overlap with PR #747 (which touches
`blog/ai_integration.py`, already at 0), and `[PLANT_DATA]` is the right token —
blog's existing vocabulary (`[CACHE]` 44, `[PERF]` 15, `[AI]` 4, …) has none for
this path, and `[AI]` would be wrong since it queries Trefle/Unsplash/Pexels
rather than a model.

It is **not** opened as a stacked PR on purpose: `scripts/add_log_prefixes.py`
exists only on this branch, and in this repo a stacked PR runs 1 CI check instead
of 17 and goes dirty the moment the parent squash-merges.

`garden_calendar` (4 calls) is deliberately **deferred**, not folded in: its only
lint blocker is an `E402` at `signals.py:156`, where a management `Command` class
and its `BaseCommand` import sit in the middle of a signals module. That is a
real structural oddity and not something to resolve inside a log-prefix sweep.
