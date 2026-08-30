---
status: pending
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

- [ ] One shared definition of the required R2 env vars, used by
      `settings.py` and `sync_media_to_r2.py`.
- [ ] One shared `CACHE_CONTROL` constant, used by both.
- [ ] Existing tests (`test_r2_storage.py`, `test_sync_media_to_r2.py`)
      still pass unchanged in behavior.

## Work Log

### 2026-08-30 - Filed

- Split out from PR #591's `/code-review high` findings (todo 305 PR 1).
  Two other findings from the same review (an uncaught
  `S3UploadFailedError` on upload failures, and a `decouple.config()`
  `.env`-fallback footgun that would have broken the "missing R2 vars"
  tests on any machine with real credentials in `backend/.env`) were
  fixed directly in that PR, not deferred here.
