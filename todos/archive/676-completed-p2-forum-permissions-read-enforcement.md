---
status: completed
priority: p2
issue_id: "676"
tags: [forum, forum-categories, backend, permissions, security]
dependencies: ["675"]
triage: ready
triaged: 2026-10-30
owner_decision: "Staff and forum moderators bypass a No Access grant and keep seeing every forum, as is_hidden staff handling does today. (owner, 2026-10-30)"
---

# Forum categories slice 11b: enforce forum read permissions everywhere (replaces is_hidden)

## Problem

Read permissions only matter if every read path honours them. Today one helper (`_visible_boards`) gates the API; several other paths reuse it.

## Findings

- Consumers of the visibility helper: `api/views.py:134-160`, `digest.py:160-165`, `mentions.py:86-88`, `quotes.py:46-52`, `api/notifications.py:28-57`; plus search and the live-updates socket (`visible_topics`).
- Rule from earlier audits: hidden content returns 404, never 403 (no existence leak).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Replace the helper with a per-user `visible_forums(user)` honouring list/read grants; thread it through every consumer above, search, sitemaps, the live socket and notifications.
2. Migrate `is_hidden=True` forums to a 'No Access for everyone' grant set, then drop `is_hidden`.
3. Cache per user per request; keep query counts fixed.

## Technical Details

- Files listed in Findings plus `apps/forum_host/sitemaps.py` and the live-updates consumer.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test per consumer: a user without read access gets 404 on topic, post, search hit, quote, mention, notification and digest entry; a permitted user sees them.
- [x] Test: anonymous access follows the anonymous grants.
- [x] Test: `is_hidden` forums remain invisible after the data migration.
- [x] Test: fixed query counts on the index and topic list.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Staff and forum moderators bypass a No Access grant and keep seeing every forum, as is_hidden staff handling does today.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- `_visible_boards(user=None, *, request=None)` now delegates to `services.forum_permissions.visible_forums`: grants as `Exists` subqueries (a forum needs `read` on itself and `list` on its category), so `board__in=` callers add no query. Staff, superusers, global moderators and the forum's own moderators bypass (owner decision).
- Threaded the reader through every API read path, search, quotes (writer at write time, reader at read time), mentions and quote notifications (`readers_of_forum`, constant queries), notifications, digest, bookmarks, the live socket, member dashboard stats and send-time push/email eligibility. Sitemaps, feeds, vector index, RAG and summaries keep the guest view.
- Migration 0048 turns `is_hidden` into No access for guests and members; 0049 drops the column. The structure tree's Hidden badge and the keep-hidden-on-move rule now read and write grants.
- Changed existing tests that set `is_hidden` directly to `hide_forum()` (the factory keeps an `is_hidden=` kwarg mapped to grants); `FORUM_ROW_KEYS` gained the new row keys; the live-consumer mock takes the new `user` argument.
- Tests: `tests/test_read_permissions.py` (per consumer, guests, migration, fixed query counts) and `apps/forum_host/tests/test_eligibility_forum_grants.py`.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_topic_is_404_without_read_access_and_200_with_it packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_topic_list_and_post_list_follow_the_grants packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_post_is_404_without_read_access_and_200_with_it packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_search_hits_follow_the_grants packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_a_quote_of_a_post_the_reader_cannot_read_is_unavailable packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_a_mention_notifies_only_members_who_can_read_the_forum packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_notifications_follow_the_recipients_grants packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_digest_entries_follow_the_recipients_grants --create-db` — evidence `.sweep-evidence/g1/676-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 8 passed, 3 warnings in 20.80s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_guests_follow_the_guest_grants --create-db` — evidence `.sweep-evidence/g1/676-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 19.87s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_is_hidden_forums_remain_invisible_after_the_data_migration --create-db` — evidence `.sweep-evidence/g1/676-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.51s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_read_permissions.py::test_index_and_topic_list_query_counts_are_fixed --create-db` — evidence `.sweep-evidence/g1/676-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.10s ========================
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
