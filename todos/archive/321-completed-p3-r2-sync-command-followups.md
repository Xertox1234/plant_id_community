---
status: completed
priority: p3
issue_id: "321"
tags: [backend, infra, media]
dependencies: []
---

# sync_media_to_r2 / R2 config follow-ups (non-blocking review findings)

## Problem

`/code-review high` on PR #591 (todo 305 PR 1 — flag-gated R2 object
storage) surfaced two findings that are real but not blocking for the
actual migration (prod media is seed-only, one clean sync run against an
empty bucket). Filed rather than a third review round, per the project's
review-loop budget.

## Findings

1. **No single source of truth for the required R2 env-var list.** It's
   hand-duplicated three ways: `settings.py`'s `STORAGES["default"]["OPTIONS"]`
   construction, `validate_environment()`'s own tuple (both in
   `plant_community_backend/settings.py`), and `sync_media_to_r2.py`'s
   `missing` check — the last one is a deliberate 4-var subset (it omits
   `R2_CUSTOM_DOMAIN`, which only feeds Django's URL generation and isn't
   needed for the command's direct boto3 calls), but nothing marks that
   as intentional vs. drift at a glance. Adding/renaming a required var
   later means remembering all three locations plus the docs
   (`CLAUDE.md`, `railway.md`, `secret-management.md`).

2. **`sync_media_to_r2.py`'s `CACHE_CONTROL` constant is a literal
   duplicate** of `settings.py`'s
   `STORAGES["default"]["OPTIONS"]["object_parameters"]["CacheControl"]`,
   synced only by a code comment, not enforced. Same family as #1.

## Recommended Action

Low-effort version: extract a small shared module (e.g.
`plant_community_backend/r2_config.py` or a constant in
`apps/core/constants.py`) holding the required-var tuple and the
`CACHE_CONTROL` string; import it from `settings.py` and
`sync_media_to_r2.py`. Keep the sync command's narrower need
(no `R2_CUSTOM_DOMAIN`) as an explicit slice of the shared tuple rather
than a separately hand-typed list, with a one-line comment explaining why.

Not urgent — worth doing before this pattern is copied for a second
storage backend or a second sync-style command.

## Acceptance Criteria

- [x] One shared definition of the required R2 env vars, used by
      `settings.py` and `sync_media_to_r2.py`.
- [x] One shared `CACHE_CONTROL` constant, used by both.
- [x] Existing tests (`test_r2_storage.py`, `test_sync_media_to_r2.py`)
      still pass unchanged in behavior.

## Work Log

### 2026-08-30 - Filed

- Split out from PR #591's `/code-review high` findings (todo 305 PR 1).
  Two other findings from the same review (an uncaught
  `S3UploadFailedError` on upload failures, and a `decouple.config()`
  `.env`-fallback footgun that would have broken the "missing R2 vars"
  tests on any machine with real credentials in `backend/.env`) were
  fixed directly in that PR, not deferred here.

### 2026-09-01 - Started by completing-todos skill (run 2026-09-01-1453)

- Picked up by automated workflow on branch `fix/321-r2-config-single-source`
  (off `origin/main` @ 86aeb5a).
- Exploration found the drift surface is **five** sites, not the three the
  Findings section names. Confirmed with the user: fix the full surface.

  | # | Site | Duplicates |
  |---|------|-----------|
  | 1 | `settings.py:439-444` (`STORAGES` OPTIONS) | 5 var names, `region_name="auto"` |
  | 2 | `settings.py:1443-1449` (`validate_environment()`) | 5 var names |
  | 3 | `sync_media_to_r2.py:79-84` (`missing` check) | 4 var names (deliberate subset) |
  | 4 | `test_r2_storage.py:45-52` (env-blanking loop) | 6 names (5 + `USE_R2`) |
  | 5 | `test_sync_media_to_r2.py:19-24` (`REQUIRED_ENV`) | 4 var names |

  Same family: `region_name="auto"` in `settings.py:443` + `sync_media_to_r2.py:99`.
- Also found a coverage gap: the **settings-side** `CacheControl` is asserted by
  no test at all (`test_r2_storage.py` checks `bucket_name`, `custom_domain`,
  `querystring_auth`, `file_overwrite`, `default_acl` — never `object_parameters`).

### 2026-09-01 - Implemented

New module `backend/plant_community_backend/r2_config.py` — pure literals, zero
imports — owns `R2_BOTO3_REQUIRED_VARS`, `R2_URL_ONLY_VARS`, `R2_REQUIRED_VARS`,
`R2_CACHE_CONTROL`, `R2_REGION_NAME`. Consumed by `settings.py` (STORAGES +
`validate_environment()`), `sync_media_to_r2.py`, and both test modules.

Three decisions worth recording:

1. **Project package, not `apps/core/constants.py`.** Both were on the table in
   the Recommended Action. Reason is dependency direction, not importability:
   apps read settings, not the reverse, and `settings.py` has no app-level import
   today. (I first justified this on `sys.path` grounds and that was wrong —
   anything that can import `plant_community_backend.settings` necessarily has
   `backend/` on `sys.path`, so `apps.core.constants` resolves too. Verified
   empirically from `cwd=/`.) The real hazard is that `apps.core.constants` is
   only *safe* at settings-import time while `apps/__init__.py` and
   `apps/core/__init__.py` stay empty — a model import or app-config added to
   either later would break settings load with an `AppRegistryNotReady` pointing
   nowhere near the cause. `apps/core/constants.py` is also docstring-scoped to
   security constants and had exactly one importer repo-wide.
2. **Composed, not sliced.** The Recommended Action suggested "an explicit slice
   of the shared tuple". `SHARED[:4]` is index-dependent — inserting a var in the
   wrong position later would silently change what the sync command requires,
   which is the exact drift being removed. Building *up*
   (`R2_REQUIRED_VARS = R2_BOTO3_REQUIRED_VARS + R2_URL_ONLY_VARS`) forces a new
   var to declare which set it joins.
3. **The command imports the constant; it does not read `settings.STORAGES`.**
   `sync_media_to_r2` is designed to run while `USE_R2` is still off, and
   `STORAGES["default"]["OPTIONS"]` only exists on the flag-on branch. Commented
   at the import so it isn't "simplified" later.

`STORAGES`' six `"<option>": config("R2_*", default="")` lines stay spelled out —
they map env vars onto *django-storages'* option names, which is that library's
API, not ours. That hand-written block is instead kept honest by a new drift test.

### 2026-09-01 - Verification

```
$ pytest apps/core/tests/test_r2_storage.py apps/core/tests/test_sync_media_to_r2.py
17 passed, 1 warning, 5 subtests passed in 6.03s

$ pytest apps/core -q
146 passed, 1 warning in 27.22s

$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py spectacular --file /dev/null
spectacular exit: 0
```

**Live smoke** (not just under test — proves the import path and the
tuple-driven check outside pytest; no R2 vars are set in this machine's `.env`):

```
$ python manage.py sync_media_to_r2
CommandError: Missing required env var(s): R2_BUCKET_NAME, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL. These must be set even though USE_R2 can
stay off while this command runs.
```

**AC3 — "unchanged in behavior":** no existing assertion was changed. The only
edits to existing tests were re-pointing the env-blanking loop at
`("USE_R2", *R2_REQUIRED_VARS)` and adding an import. The literal
`"public, max-age=31536000, immutable"` assertion in `test_sync_media_to_r2.py`
was deliberately **left as a literal** — it is now what pins the shared
constant's value from outside the module.

**Mutation-tested** (a drift test that cannot fail is worthless):

- Made `STORAGES` hardcode `custom_domain` instead of reading the env var →
  `AssertionError: 'sentinel-r2_custom_domain' not found in dict_values(...) :
  R2_CUSTOM_DOMAIN is in R2_REQUIRED_VARS but STORAGES never reads it`
  (`1 failed, 4 subtests passed`).
- Made `settings.py` use `"public, max-age=60"` instead of `R2_CACHE_CONTROL` →
  `AssertionError: 'public, max-age=60' != 'public, max-age=31536000, immutable'`.
- `settings.py` restored byte-identical after each (`diff` clean).

**Drift proof** (`git grep`, tracked + staged):

- `"public, max-age=31536000"` → 2 hits: `r2_config.py:58` and the one deliberate
  test assertion. Was 3.
- No hand-maintained *list* of R2 var names survives outside `r2_config.py`.
  Remaining string hits are a dict lookup (`env_values["R2_BUCKET_NAME"]`), test
  fixture values, and the `config("R2_*")` → django-storages option mapping,
  which the sentinel test pins.
- `CACHE_CONTROL` (the old command-local constant) → 0 hits.

### 2026-09-01 - Code review (round 1)

`code-review-orchestrator` routed to `django-drf-reviewer` +
`cross-cutting-reviewer`; both dispatched in parallel.

**Verified clean by review:** settings-import-time safety (`plant_community_backend/__init__.py`
imports `.celery` and fully executes before the `settings` submodule loads, so
the package is already in `sys.modules` — no cycle possible); every local in the
restructured command correctly re-sourced; `validate_environment()` order; no
`settings.STORAGES` dependency in the command.

**Fixed (3 findings):**

1. *(medium ×2, both reviewers independently)* The drift test asserted
   `assertIn(sentinel, options.values())` — presence somewhere in the dict, not
   correct wiring. A swapped `access_key`/`secret_key` in `STORAGES` would have
   passed. Replaced with an explicit `VAR_TO_OPTION` map asserted **by key**,
   plus a guard that `tuple(VAR_TO_OPTION) == R2_REQUIRED_VARS` so a new var
   can't be added without stating which option it feeds.
2. *(medium)* Nothing anchored the **shrink** direction: emptying
   `R2_URL_ONLY_VARS` would stop production requiring `R2_CUSTOM_DOMAIN`, and
   every test derived its expectations from `R2_REQUIRED_VARS`, so they'd shrink
   along with it and stay green. Added
   `assertIn("R2_CUSTOM_DOMAIN is required", result.stderr)` to
   `test_missing_r2_vars_fails_fast_in_production` — an anchor outside the
   composition. (This adds an assertion to an existing test; it strengthens, and
   does not alter, what that test pins.)
3. *(low)* `_print_storages` didn't blank R2 vars the way `_run_check` does — it
   relied on every caller passing all five. Since it prints `STORAGES` to stdout,
   a future partial-override caller on a machine following the R2 rotation
   runbook would dump real credentials into test output. Now blanks first,
   applies overrides second.

Plus two doc corrections: `r2_config.py`'s "Order is load-bearing" was
overstated (`validate_environment()` emits one message per missing var
regardless of position — order is cosmetic), and a note that `R2_CACHE_CONTROL`'s
*value* is anchored only by the hardcoded literal in `test_sync_media_to_r2.py`,
which must not be "de-duplicated" into an import.

**Rejected (2 findings, both `high`):** `django-drf-reviewer` reported isort
violations on the two test files' new imports, claiming they'd block the commit.
Contradicted by direct evidence: isort itself *wrote* that layout (the hook
reformatted both files), and `pre-commit run isort --files <both>` reports
**Passed**. The reviewer ran isort standalone from a cwd where
`plant_community_backend` resolved as first-party; pre-commit runs from the repo
root, where it does not, so no blank-line separation is expected. No change made.

**Second mutation round** on the strengthened assertions:

- Swapped `access_key`/`secret_key` in `STORAGES` →
  `STORAGES option 'access_key' should carry R2_ACCESS_KEY_ID` (the pre-fix
  assertion passed this mutation — the fix is verified, not assumed).
- `R2_URL_ONLY_VARS = ()` → `'R2_CUSTOM_DOMAIN is required' not found in ...`
  (2 failed, 7 passed).
- Both files restored byte-identical afterwards.

Final: 17 passed + 5 subtests, 146 passed across `apps/core`, `manage.py check`
clean, all scoped pre-commit hooks passed. detect-secrets flags the
`R2_SECRET_ACCESS_KEY` → django-storages option-name mapping line as a Secret
Keyword — a false positive (the mapped value is an option *name*, not a
credential), marked with an inline allowlist pragma in the test. It fires on this
doc for quoting that line too, hence the pragma here: <!-- pragma: allowlist secret -->

### 2026-09-01 - Completed by completing-todos skill (run 2026-09-01-1453)

- Verification: all 3 acceptance criteria passed with quoted evidence above.
- Review: 7 findings total (2 high rejected with evidence, 3 fixed, 2 doc
  corrections applied). No blocking finding left open.
