---
status: completed
priority: p4
issue_id: "361"
tags: [code-quality, logging, backend]
dependencies: []
source_review: "github-issues-185-186"
---

# Log-prefix and stale-comment cleanup (surviving half of issues #185/#186)

## Problem

GitHub issues #185 and #186 (both filed 2025-11-11 by a "Pattern Recognition
Specialist" audit, both LOW) sat untouched for ten months. They are converted
here so the todo sweeps can see them — but **most of #185 is already dead**, and
importing it verbatim would have created make-work.

## Findings

Verified against the tree on 2026-09-06 before conversion, not taken on trust:

| Source | Item | Verified state |
| --- | --- | --- |
| #185 (1) | `console.error` in `web/src/utils/csrf.ts` | **Already fixed.** The file now uses `logger.error`/`logger.debug`/`logger.warn` throughout, all with `[CSRF]` prefixes (`csrf.ts:66,72,81,88,91`). Nothing to do. |
| #185 (2) | `backend/apps/forum/constants.py:133-134` cache-key prefixes | **Obsolete.** `apps/forum` was retired in the wagtail_forum rebuild; the path no longer exists and `CACHE_PREFIX_TRUST_LIMITS` / `CACHE_PREFIX_DAILY_ACTIONS` appear nowhere in `backend/`. The "requires cache invalidation after deployment" warning is likewise moot. |
| #185 (3) | Stale `# TODO 040 fix` comments | **Still present** — `backend/apps/blog/signals.py:69, 99, 129` (the issue said 67/99/134; lines have drifted). Todo 040 is long complete. |
| #186 | Unprefixed log statements | **Partly valid.** `apps/plant_identification/services/plant_id_service.py` has 3 unprefixed `logger.*("...")` calls against 1 prefixed. The issue's repo-wide "5%" figure was never re-measured and should not be trusted as scope. |

So two of the four original items are closed by time, and two survive.

## Recommended Action

1. Delete the three `# TODO 040 fix` trailing comments in
   `backend/apps/blog/signals.py` (lines 69, 99, 129). Comment-only change.
2. Re-measure the log-prefix gap before doing anything about it — count
   unprefixed `logger.*` calls across `backend/apps/`, rather than inheriting
   the stale 5% claim. If the real count is small, add the bracketed prefixes;
   if it is large, split it out and re-rate.
3. Do **not** revisit #185 items 1 and 2. They are recorded above as resolved
   and obsolete so the next reader does not re-derive that.

## Technical Details

- Prefix convention in use: `[CACHE]`, `[PERF]`, `[ERROR]`, `[CIRCUIT]`,
  `[RATE_LIMIT]`, `[SPAM]`, `[CSRF]`. Prefixes exist to make logs filterable.
- Caution when re-measuring: `apps.*` loggers in this project run with
  `propagate=False`, so they are invisible to `caplog` — a test asserting on
  prefixes needs the handler attached directly, not `caplog` alone.
- Original sources: GitHub issues #185 and #186, both closed on 2026-09-06 with
  a pointer to this file.

## Measurement (2026-09-13) — AC 2

AST parse of every non-test `.py` under `backend/apps/` (316 files), matching
`logger|log|_logger . debug|info|warning|error|exception|critical` and testing
the first argument's literal leading text against `^\s*\[[A-Z0-9_]+\]`.
Multi-line calls, f-strings and `%`-format strings are all handled.

| Scope | Prefixed | Unprefixed | Unprefixed share |
| --- | --- | --- | --- |
| `backend/apps/` (non-test) | 412 | **357** | **46.4%** |
| `backend/packages/` (wagtail_forum) | 26 | 1 | 3.7% |

Per-app unprefixed count, across **41 distinct files**:

| App | Unprefixed | Prefixed |
| --- | --- | --- |
| `plant_identification` | 182 | 96 |
| `users` | 84 | 12 |
| `core` | 62 | 5 |
| `blog` | 22 | 84 |
| `garden_calendar` | 4 | 51 |
| `forum_host` | 3 | 72 |
| `garden` | 0 | 92 |

### Two inherited claims are falsified by this

1. **The issue's "5%" is really 46.4%** — off by roughly 9x. It was never
   re-measured, exactly as this todo suspected.
2. **This todo's own spot-check was also wrong.** It recorded
   `plant_id_service.py` as "3 unprefixed against 1 prefixed". The real figure
   is **7 unprefixed against ~20 prefixed** (unprefixed at lines 85, 308, 314,
   317, 405, 537, 542).

### Detector was positive-controlled

Not only negative-controlled: `plant_id_service.py:120`
`logger.info("[LOCK] ...")` is correctly classified *prefixed*, and all 7
unprefixed hits were confirmed against grep — including three multi-line calls
that a line-based regex would miss.

### Outcome: re-scoped, not swept

This is the "large" branch of Recommended Action 2 ("if it is large, split it
out and re-rate"), so AC 3 is satisfied via its explicit *"or the item
explicitly re-scoped with a reason"* clause. Successor: **todo 388**.

Reason, in short: 357 semantic prefix decisions across 41 files is not a p4, and
it cannot be mechanized. A logging `Filter`/`Formatter` deriving the prefix from
the logger name was considered and rejected — `plant_id_service.py` alone emits
`[LOCK]`, `[CACHE]` and `[QUOTA]` from one module, so a module-derived prefix
would flatten all three *and* double-prefix the 412 already-correct calls.

## Acceptance Criteria

- [x] No `TODO 040` string remains in `backend/apps/blog/signals.py`
- [x] Actual repo-wide unprefixed-logger count recorded in this file before any
      prefix work begins
- [x] Prefixes added to whatever that count identifies, or the item explicitly
      re-scoped with a reason
- [x] Backend suite still green

## Notes

p4, dropped from the issues' original P3/LOW: half the original scope no longer
exists, and what remains is three comment deletions plus an unmeasured tidy-up.
Recorded rather than discarded only because the stale comments actively mislead
— they point at a todo that has been done for months.

## Work Log

### 2026-09-06 - Converted from GitHub issues #185/#186

- Converted during a GitHub cleanup sweep so the backlog lives in `todos/`
  where the sweep skills can see it; GitHub issues cannot be swept.
- Each of the four original items was checked against the current tree first.
  Two were already resolved or obsolete and are deliberately not carried
  forward as work.

### 2026-09-13 - Completed

**AC 1 — stale comments deleted. The finding table under-counted: 6 sites, not 3.**

`backend/apps/blog/signals.py:69,99,129` were the three known trailing comments.
A repo-wide grep found **three more in `backend/apps/blog/api/viewsets.py`**
(356, 379, 430) that the conversion missed. Swept both files — same "actively
mislead" rationale, comment-only. Recording rather than silently widening: the
AC names only `signals.py`.

`viewsets.py:356` needed care — it is **inside the `popular` action's
docstring**, not a trailing comment, and carried a real fact. A blanket `sed`
of `TODO 040 fix` would have mangled it. It also sat in a contiguous run of
three identically-shaped stale attributions, so all three were rewritten to
keep their facts and drop the completed-todo pointers:

```
BLOCKER 3 fix: Uses constants instead of magic numbers.        -> Uses constants instead of magic numbers.
TODO 037 fix: Optimized with prefetch_related to eliminate...  -> Optimized with prefetch_related to eliminate...
TODO 040 fix: Added caching to reduce database load (30min).   -> Cached for 30min to reduce database load.
```

Verification:

```
$ grep -rn "TODO 040" backend/apps/
exit=1 (no matches)
```

The `[CACHE]` logs at `signals.py:70,100,130` and the `[PERF]` logs at
`viewsets.py:384,435` were deliberately left untouched — they are asserted on by
`test_blog_viewsets_caching.py:147,195`.

**Left in place, out of scope:** 7 further stale fix-attribution markers of the
same family survive in `backend/apps/blog/` — `BLOCKER 3` x4
(`constants.py:36`, `middleware.py:109,144,153`), `BLOCKER 1`
(`middleware.py:98`), `BLOCKER 2` (`tests/test_analytics.py:15`) and `TODO 037`
(`tests/test_analytics.py:487`). This todo's AC scopes it to `TODO 040`, so they
are carried to todo 388 rather than swept here.
`backend/todos/archive/005-...md` is untouched (historical record).

**AC 2 / AC 3 — see the Measurement section above.** 357 unprefixed (46.4%),
not 5%. Re-scoped to todo 388 rather than swept.

**AC 4 — backend suite.** Comment/docstring-only diff. Run locally in an
isolated worktree:

```
$ pytest apps/blog --create-db -q
273 passed, 7 skipped, 13 warnings in 96.96s (0:01:36)

$ pytest apps/blog/tests/test_blog_viewsets_caching.py \
         apps/blog/tests/test_ai_cache_service.py \
         apps/blog/tests/test_blog_signals.py --reuse-db -q
59 passed, 10 warnings in 40.88s
```

The second run is the targeted check on the tests that assert log-message
content near the edited lines. **Scope of that evidence: the blog app only** —
full-suite proof is the required `Run backend test suite` CI gate on the PR, not
this local run.

**Deliberately skipped: the source-review checkoff.** Frontmatter carries
`source_review: "github-issues-185-186"`, which is a pseudo-value rather than a
path, and there is no `source_finding`. Both issues were closed 2026-09-06
pointing at this file, so there is no `## Finding Status` line to tick.

**Unrelated finding, filed not fixed:** `backend/plant_community_backend/settings.py:839-851`
is a dead duplicate of the `ENABLE_FILE_LOGGING` cleanup block — it runs before
`LOGGING` is defined (`:1015`), raising `NameError` swallowed by a bare
`except Exception: pass`. The live copy is `:1112-1123`. Noted in todo 388.
