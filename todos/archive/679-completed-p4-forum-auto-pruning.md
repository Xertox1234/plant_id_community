---
status: completed
priority: p4
issue_id: "679"
tags: [forum, forum-categories, backend, celery, cron]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
owner_decision: "Ship days-since-last-post pruning only. No last_viewed_at field and no days-since-viewed rule. (owner, 2026-10-30)"
---

# Forum categories slice 13: per-forum auto-pruning

## Problem

phpBB can prune old topics per forum on a schedule (days since last post / since viewed, optionally sparing polls, announcements and pinned topics).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB prune settings).
- Nightly cron service already exists (`forum-prune-cron`, see root CLAUDE.md `FORUM_LINK_PREVIEWS_ENABLED`).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Fields: `prune_enabled`, `prune_days_since_last_post`, `prune_days_since_viewed` (optional), `prune_pinned` (default no), `prune_polls` (default no).
2. Management command `prune_forums --dry-run`, run from the nightly cron; prune = unpublish (soft) first, matching existing take-down semantics, with a log line per forum.
3. Admin *Pruning* tab.

## Technical Details

- New management command in `wagtail_forum/management/commands/`, `.railway/railway.ts` cron schedule if needed.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: only topics past the threshold are pruned; pinned/poll topics spared by default; `--dry-run` changes nothing.
- [x] Test: disabled forums are untouched.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Ship days-since-last-post pruning only. No last_viewed_at field and no days-since-viewed rule.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- Forum fields `prune_enabled`, `prune_days_since_last_post`, `prune_pinned`, `prune_polls` on a *Pruning* tab; days since last post only, no viewed rule (owner decision).
- `manage.py prune_forums [--dry-run]` unpublishes (soft, `UnpublishAction`) live topics with no post for that many days, sparing pinned and poll topics by default, one `[PRUNE]` line per forum.
- Added to the nightly `forum-prune-cron` start command in `.railway/railway.ts` (a no-op until a forum enables pruning).
- Tests: `tests/test_prune_forums.py`.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_prune_forums.py::test_only_topics_past_the_threshold_are_pruned_and_pinned_and_polls_spared packages/wagtail_forum/wagtail_forum/tests/test_prune_forums.py::test_pinned_and_poll_topics_are_pruned_when_the_forum_says_so packages/wagtail_forum/wagtail_forum/tests/test_prune_forums.py::test_dry_run_changes_nothing --create-db` — evidence `.sweep-evidence/g1/679-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 2 warnings in 19.85s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_prune_forums.py::test_forums_with_pruning_disabled_are_untouched --create-db` — evidence `.sweep-evidence/g1/679-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 19.54s ========================
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: `prune_enabled`, `prune_pinned` and `prune_polls` (added by 0047) now have `db_default=False` in the model and the migration, so the previous release can insert forums while this one migrates.
- No behaviour change to pruning; every criterion was re-run.

### 2026-10-30 - Review round 1: non-blocking findings (hand fixes)

- Fixed (medium): one topic that failed to unpublish crashed `prune_forums`. The cron chains its jobs with `&&`, so that would also skip `flushexpiredtokens` and `expire_unverified_accounts`. Each unpublish now runs in its own savepoint, and a failure is logged (`[ERROR] prune failed …`), counted in the summary and skipped. Test: `test_a_topic_that_fails_to_unpublish_does_not_stop_the_rest`. Mutation-checked.
