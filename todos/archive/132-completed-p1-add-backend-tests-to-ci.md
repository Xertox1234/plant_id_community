---
name: add-backend-tests-to-ci
status: completed
priority: p1
created: 2026-05-30
tags: [harness, ci, backend, testing]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F2"
---

# Run the backend test suite in CI

## Problem

`backend-ci.yml` runs only `pip check`, `python manage.py check`, and
`python manage.py spectacular` (OpenAPI schema validation). It does **not** run
`python manage.py test`. Pre-commit doesn't run backend tests either (only
black/flake8/isort). So the backend test suite — the very baseline the `/audit`
skill tells you to record — is gated by **no** CI workflow. A PR that breaks
backend tests merges green.

Mobile is the only stack whose tests run in CI (`mobile-ci.yml` runs
`flutter test`). Backend and web are not.

This may be partly deliberate (the suite needs postgres + redis; `backend-ci.yml`
deliberately uses sqlite for the lightweight checks). The fix is to add a proper
test job, not to hand-wave it.

## Acceptance criteria

- [x] A CI job runs `python manage.py test` (or pytest) for the backend on PRs
      touching `backend/**`, with postgres + redis services wired up (mirror the
      env the suite needs; see backend/CLAUDE.md).
- [x] The job is blocking (a failing backend test fails the PR).
- [x] Decide + document whether backend flake8/black should also run in CI (today
      they are pre-commit-only and bypassable with `--no-verify`).
- [x] Record the suite's pass count in the job log so drift is visible.

## Notes

Workflow files are not under `.claude/` — editable directly. Confirm the test
DB / service container setup against backend/CLAUDE.md before wiring. Watch the
"required status check + path filter" gotcha documented in `backend-ci.yml:12-15`.

## Work Log

### 2026-05-30 - Started by completing-todos skill (run 2026-05-30-1838)

- Picked up by automated workflow.

### 2026-05-30 - Investigation & decisions

**Runner: pytest (not `manage.py test`).** The repo's curated suite is configured
in `backend/pytest.ini`, which deliberately `--ignore`s `apps/forum_integration/tests`
and 2 `plant_identification` diagnosis test files. Those path-based exclusions
cannot be replicated under `manage.py test` (Django excludes by tag, not path), so
`manage.py test` with no args runs the known-excluded set and would go red. The
acceptance criterion explicitly allows "(or pytest)". `backend/CLAUDE.md`'s
`manage.py test` references are local-dev ergonomics (`--keepdb`), not a CI mandate.

**Postgres wiring (silent-bug guard).** Under pytest, `"test"` is NOT in `sys.argv`,
so the Postgres test branch at `settings.py:303` never fires — `pytest-django` uses
`DATABASE_URL`. Confirmed locally: with the dev `.env`, the resolved engine is
`django.db.backends.postgresql` (db `plant_community`) and cache is
`django_redis.cache.RedisCache`. CI therefore MUST set `DATABASE_URL` to the
Postgres service explicitly; `TEST_DB_*` would do nothing under pytest.

**Scope: `ENABLE_FORUM=False`.** Turning the forum on would pull
`apps.forum_integration` into `INSTALLED_APPS` and un-ignore the very tests pytest
skips. Keep it off; document the exclusion.

**Baseline (main, pytest):** `609 passed, 8 skipped` (617 collected) in ~130s,
EXIT=0 — on Postgres + Redis. Re-verifying under the exact CI env
(`ENABLE_FORUM=False`) since the dev `.env` runs with `ENABLE_FORUM=True`.

**Criterion 3 decision — flake8/black stay pre-commit-enforced; NOT added to CI
in this change.** Evidence: a full-tree `flake8 backend/apps backend/plant_community_backend`
(excluding venv/migrations) surfaces **3,179 pre-existing violations**; cleaning
that debt is explicitly out of scope (root `setup.cfg`: "do not widen these
suppressions"). The tools aren't in `requirements.txt` (pre-commit pins black
`24.1.1`, flake8 `7.0.0`); pre-commit lints incrementally on changed files, so a
faithful CI equivalent needs diff-scoped linting — added complexity not warranted
by a "add tests to CI" todo. Residual risk: `--no-verify` bypasses pre-commit;
documented with a future path (diff-scoped lint action, or debt cleanup + full gate).

**Trigger pattern.** Added as a second job in `backend-ci.yml` so it shares the
existing `on:` block (push path-filtered; PR NOT path-filtered — the required-check
rationale in `backend-ci.yml:12-15`). This overrides the todo's looser "on PRs
touching backend/**" wording, per the repo's own documented convention.

### 2026-05-30 - Verification (evidence)

**Criterion 1 — pytest job with postgres + redis.** `backend-tests` job added to
`.github/workflows/backend-ci.yml`. YAML parses; structure confirmed:

```
jobs: ['backend-checks', 'backend-tests']
triggers: ['push', 'pull_request']
services: ['postgres', 'redis']
env keys: ['DEBUG','ENABLE_FILE_LOGGING','ENABLE_FORUM','DATABASE_URL','REDIS_URL','SECRET_KEY','JWT_SECRET_KEY']
steps: 5
```

Suite runs green under the exact CI env (`ENABLE_FORUM=False`,
`DATABASE_URL=postgresql://…/plant_community`, `REDIS_URL`, CI SECRET_KEY/JWT):

```
collecting ... collected 617 items
== 609 passed, 8 skipped, 7 warnings, 10 subtests passed in 124.65s ==
EXIT=0
```

Resolved DB/cache under pytest confirmed Postgres + Redis (not sqlite/locmem):
`ENGINE: django.db.backends.postgresql`, `CACHE: django_redis.cache.RedisCache`.

**Criterion 2 — blocking.** The run step is bare `python -m pytest` with no
`continue-on-error` / `|| true` (grep confirmed only `run: python -m pytest`).
pytest exits non-zero on any failure, failing the job:

```
# throwaway failing test, outside the repo
1 failed ... PYTEST_EXIT=1
```

Note: a non-zero job already marks the PR check failed. To make it *merge*-blocking,
`backend-tests` must be added to the branch-protection required-status-checks list
(a one-time repo-admin setting, not a workflow change) — documented in the job
comment. Follow-up if not already configured.

**Criterion 3 — flake8/black decision.** Documented (decided: NOT in CI, stay
pre-commit) in the `backend-ci.yml` top-of-file comment and the Investigation entry
above. Evidence basis: 3,179 pre-existing project-code flake8 violations
(venv/migrations excluded), frozen by root `setup.cfg`.

**Criterion 4 — pass count recorded.** pytest's summary line ("609 passed, 8
skipped") is emitted to the job log on every run; the run-step comment also pins the
wiring-time baseline (609/8) for drift comparison.

### 2026-05-30 - Code review (completing-todos Step 4)

code-review-orchestrator routing: only `.github/workflows/backend-ci.yml` changed; no
language specialist applies to a GH Actions YAML, and the security-reviewer trigger is
grep-scoped to changed `.py` files (zero here), so it reviewed inline. Verdict:
**0 critical / 0 high / 0 medium**. Correctness confirmed (DB name match
`plant_community`→`test_plant_community`; localhost service access; valid Actions
schema; throwaway CI-only secrets, byte-identical to `backend-checks`; injection-safe
single-quoted heredoc; failing test → non-zero exit, no silent-pass path).

#### Known issues (INFO — non-blocking, accepted)

- Redis `/1` for the whole job collapses the `machina_attachments` (default `/2`) and
  `renditions` (default `/3`) caches onto db 1 in CI. Harmless — each keeps a distinct
  `KEY_PREFIX`, so no collisions. Diverges from dev/prod multi-db layout only. No action.
- `pull_request` has no path filter, so `backend-tests` runs the full postgres+redis
  suite on every PR incl. docs-only. Intentional (required-check rationale,
  `backend-ci.yml:12-15`); pure CI-minutes cost.
- Pass count is documented, not machine-enforced. The real gate is pytest's exit code
  (non-zero on failure, 5 on zero-collected). A `--strict` count assertion is optional
  future hardening.

### 2026-05-30 - Completed by completing-todos skill (run 2026-05-30-1838)

- Verification: all 4 acceptance criteria passed with quoted evidence (pytest 609
  passed/8 skipped on postgres+redis under the exact CI env; failing test → exit 1;
  flake8/black decision documented; pass count in job log).
- Review: 3 findings total, 0 blocking — 3 INFO accepted (see Known issues).
- Follow-up (not a code change): add `backend-tests` to branch-protection
  required-status-checks to make it merge-blocking.

### 2026-05-30 - Post-completion correction (advisor catch — env isolation)

**Blind spot found & fixed.** The earlier "609 passed under the exact CI env" runs
still had the dev `.env` on disk. python-decouple precedence is `os.environ` first,
**then `.env`** — so vars I didn't override fell through to `.env`. CI has no `.env`.
Re-ran with `.env` moved aside (true CI isolation): **13 failures**, all in
`apps/plant_identification/test_services.py`, root cause
`ValueError: PLANTNET_API_KEY must be set` (and Plant.id / Plant-health / Trefle
equivalents). Those services raise if their key is empty; the tests mock HTTP but
still construct the service.

**Fix:** added four placeholder API keys to the `backend-tests` env block
(`PLANTNET_API_KEY`, `PLANT_ID_API_KEY`, `PLANT_HEALTH_API_KEY`, `TREFLE_API_KEY`) —
≥32-char obvious fakes, never sent on the wire (HTTP mocked), same throwaway pattern
as the existing CI SECRET_KEY/JWT.

**Re-verified (true CI env, `.env` removed, placeholder keys present):**

```
============ 609 passed, 8 skipped, 7 warnings in 103.21s ============
EXIT=0
```

Also confirmed pg_trgm is created by migration `0013_add_search_gin_indexes.py`
(`CREATE EXTENSION IF NOT EXISTS pg_trgm;` + `TrigramExtension`), and the CI postgres
service user is superuser — so a fresh `postgres:16` container won't trip on the
trigram/GIN indexes. The gate is genuinely green, not "green with dev `.env`".

Note: the 4 placeholder-key lines were added after the Step-4 code review. They are
the same throwaway-secret pattern already cleared by that review (low-entropy,
readable `ci-placeholder-…-000…`); commit-time `detect-secrets` + `kimi-review`
gates provide the final pass.
