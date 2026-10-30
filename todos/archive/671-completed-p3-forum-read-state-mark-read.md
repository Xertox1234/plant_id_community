---
status: completed
priority: p3
issue_id: "671"
tags: [forum, forum-categories, backend, web]
dependencies: ["665"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 7: per-forum unread markers, mark forum read, mark all forums read

## Problem

phpBB shows an unread marker per forum and offers 'mark forum read' and 'mark all forums read'. We have per-topic read state only.

## Findings

- Exists: per-topic reads `backend/packages/wagtail_forum/wagtail_forum/models/topic_reads.py`; unread annotation `api/views.py:197-230` using `ForumProfile.read_watermark_at` (`models/profiles.py:138`).
- Missing: nothing advances `read_watermark_at` after profile creation — its only writers are creation defaults (`models/profiles.py:188`, `signals.py:175`), verified 2026-10-28 — so there is no mark-all-read; no per-forum read mark.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Add a per-user per-forum mark (`ForumRead(user, forum, marked_at)`), used as a floor in the unread annotation alongside the global watermark.
2. Endpoints: mark one forum read; mark all read (advances `read_watermark_at`).
3. Forum rows and category rows report `has_unread` (any visible topic newer than the user's effective floor), with a bounded query count.
4. Web: unread dot on forum rows, 'Mark forum read' on the forum page, 'Mark all read' on the index.

## Technical Details

- `models/topic_reads.py`, `api/views.py` `_annotate_topic_unread`, new endpoints, web index + thread list.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: marking a forum read clears its topics' unread flags and not other forums'.
- [x] Test: mark all read advances the watermark and clears every forum.
- [x] Test: anonymous users get no unread markers and the endpoints require auth.
- [x] Test: the index unread computation has a fixed query count.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-0417)

- New `ForumRead(user, forum, marked_at)` (monotonic `mark_read`, like `TopicRead`); `POST /forum/boards/{slug}/read/` marks one forum, `POST /forum/read-all/` advances `ForumProfile.read_watermark_at` (never backwards). Both `IsAuthenticated`, mounted and throttled host-side (`apps/forum_host/api.py`: `forum_mark_read` 60/m, `forum_mark_all_read` 30/m).
- `_annotate_topic_unread` now takes the GREATEST of the TopicRead, ForumRead and watermark floors (it was a COALESCE that let an older TopicRead beat a newer mark, so marking could not clear a topic read before it). Each floor is Coalesced to the base first so a missing row never NULLs the result.
- `/forum/categories/` forum rows and categories carry `has_unread`: one correlated `EXISTS` per row inside the existing prefetch (same floors and hidden authors as the topic list), constant false for anonymous, so the query count stays fixed. `/forum/boards/` (Flutter) is unchanged.
- Web: unread dot on `ForumCard`, "Mark all read" on the index (signed in), "Mark forum read" on the thread list (shown only while something is unread, which only a signed-in member sees).
- `test_forum_categories_api.py` key sets gained `links`/`has_unread` (additive contract change). Seen once, not caused here: `test_topic_detail.py::test_topic_detail_is_subscribed_for_authenticated_user` flaked 7 vs 8 queries in one file run and passed on rerun.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-0417)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_forum_read.py -k "marking_a_forum_read or reply_after_the_mark or hidden_forum_or_a_category" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/671-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================= 4 passed, 6 deselected, 3 warnings in 19.98s =================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_forum_read.py -k "mark_all_read or category_reports_unread" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/671-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================= 3 passed, 7 deselected, 3 warnings in 20.18s =================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_forum_read.py -k "anonymous or require_auth" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/671-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================= 2 passed, 8 deselected, 3 warnings in 19.92s =================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_forum_read.py packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py -k "fixed_query_count or categories_query_count_is_flat" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/671-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 2 passed, 20 deselected, 3 warnings in 19.27s =================
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-0417)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Review round 1: non-blocking findings

- **Declined:** `ForumRead.mark_read`'s `get_or_create` could race two first POSTs into an IntegrityError. Django's `get_or_create` already catches that IntegrityError inside a savepoint and re-reads the row, and the follow-up `GREATEST` update is atomic.
- **Declined:** "Mark forum read" shows only when a topic on the loaded page is unread. Low UX edge; the index offers "Mark all read" whenever anything is unread.
- **Declined:** the "Mark forum read" handler has no stale guard if the user navigates mid-request. It only clears client-side markers, and the next fetch corrects them.
- **Declined:** the query-count pin wants a docstring and a 1-vs-N comparison. The existing small-vs-big equality test already pins flatness.
