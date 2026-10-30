---
status: completed
priority: p3
issue_id: "674"
tags: [forum, forum-categories, backend, web, wagtail, moderation]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
blocked_on: "A design choice on how forum moderators get access and get scoped across Wagtail admin and the API"
owner_decision: "Moderators can be users or groups. They moderate through the existing Wagtail admin (queue, reports, topic snippets), scoped to their forums by a permission policy. A topic move is allowed only when they moderate both the source and the destination forum. (owner, 2026-10-30)"
---

# Forum categories slice 10: per-forum moderators and a 'Moderators:' line

## Problem

phpBB assigns moderators per forum and lists them on each forum row. Today moderation rights are global Wagtail model permissions.

## Findings

- Global moderation check: `backend/packages/wagtail_forum/wagtail_forum/admin_views.py:305` `user_can_moderate_pending`.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Model `ForumModerator(forum, user | group)`; admin *Moderators* tab on the forum.
2. A forum moderator may moderate (pending queue, reports, hide/lock/pin/move) only in their forums; global moderators unchanged.
3. API exposes moderators for the forum row; web shows 'Moderators: …'.

## Technical Details

- `admin_views.py` moderation queue filters, report actions, `api/views.py` moderation endpoints.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: a forum moderator can act on a topic in their forum and is refused in another forum.
- [x] Test: the moderation queue shows a forum moderator only their forums' items.
- [x] Web Vitest: moderators line renders.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Moderators can be users or groups. They moderate through the existing Wagtail admin (queue, reports, topic snippets), scoped to their forums by a permission policy. A topic move is allowed only when they moderate both the source and the destination forum.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- New `ForumModerator(forum, user | group)` and a *Moderators* tab on the forum form (usernames plus group checkboxes).
- `permissions.ForumScopedPermissionPolicy`, registered for Topic, Post and Report: forum moderators get view/change/publish/unpublish/lock/unlock in their forums only (never add/delete); `scope_object_urls` makes every other snippet object URL 403; listings, the pending queue (approve/reject included) and the reports queue are narrowed to their forums.
- A topic move offers only forums the moderator moderates (`TopicAdminForm`), so both ends are theirs (owner decision).
- `GET /forum/categories/` rows carry `moderators` (one aggregated subquery, the index stays at two queries); web `ForumCard` renders the "Moderators:" line.
- Deferred, not built: the API-side moderator predicate (`_is_forum_moderator`, revisions and block bypass) stays global.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_a_forum_moderator_can_act_on_a_topic_in_their_forum_only packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_a_group_moderator_is_scoped_the_same_way packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_a_move_is_offered_only_to_forums_the_moderator_moderates --create-db` — evidence `.sweep-evidence/g1/674-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 3 warnings in 19.92s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_the_pending_queue_shows_a_forum_moderator_only_their_forums packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_the_reports_queue_shows_a_forum_moderator_only_their_forums packages/wagtail_forum/wagtail_forum/tests/test_forum_moderators.py::test_the_topic_listing_shows_a_forum_moderator_only_their_forums --create-db` — evidence `.sweep-evidence/g1/674-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 3 warnings in 20.47s ========================
  ```

- AC 3: `cd web && ./node_modules/.bin/vitest run src/components/forum/ForumCard.test.tsx -t 'Moderators line'` — evidence `.sweep-evidence/g1/674-ac2.txt` (not committed), last lines:

  ```text
     Duration  1.39s (transform 54ms, setup 115ms, import 677ms, tests 21ms, environment 502ms)

  (!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
    - `__dirname` (vitest.config.ts:62:25). Use `import.meta.dirname` instead
  Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
