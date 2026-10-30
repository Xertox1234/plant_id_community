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

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: a moderator holding any other model permission (say `view_post` or `lock_post`) skipped the forum check and could edit every forum's rows. `backend/packages/wagtail_forum/wagtail_forum/permissions.py` now asks, per object URL, for the model permission that view needs (`OBJECT_URL_ACTIONS`, `change` by default); the listing is unscoped only for a non-moderator or a holder of add/change/delete/view; the topic move needs `change_topic` itself.
- A `delete_post`-only user, whom the old check counted as non-global, again gets the delete view and the full listing. New tests in `test_forum_moderators.py` cover the mixed-permission cases.
- The README's Moderators section says which model permissions widen which views.

### 2026-10-30 - Review round 1: non-blocking findings (hand fixes)

- Fixed (medium, raised three times): a post's `topic` field offered every topic, so a forum moderator could move a post into another forum. `PostAdminForm` (`wagtail_hooks.py`) narrows it to their forums unless they hold `change_post`. Tests: `test_a_post_moves_only_into_topics_of_forums_the_moderator_moderates` and `test_change_post_everywhere_still_offers_every_topic`. Mutation-checked.
- Fixed (same gap, found while fixing it): `topic` and a report's `post` render as snippet choosers, and the chooser modal is a second listing that was unscoped. It showed a forum moderator every forum's topics and posts, hidden forums' included. `scoped_chooser_viewset` runs the chooser's list through the policy's `scope()`. A report's form now offers only the moderator's own forums' posts, and never a private message (`ReportAdminForm`). Tests: `test_the_topic_chooser_lists_a_forum_moderator_only_their_forums` (both the choose and the results views) and `test_a_report_offers_a_forum_moderator_only_their_posts_and_no_message`. Both mutation-checked.
- Already fixed by the round-1 repair (medium): a global `view_topic` holder skipping the forum check. Every object URL now asks for its own action.
- Fixed (low): a docstring in `admin_views._user_can_reject` sat below new code; it is back on the first line.
- Refuted (low, "a non-numeric pk 500s"): the snippet URLs match `[0-9]+`, so a non-numeric pk never reaches the guard (`reverse` itself refuses one).

### 2026-10-30 - Review round 2: non-blocking findings (hand fixes)

Round 2 came back clean (nothing blocking, nothing refuted).
- Fixed (low): the Moderators line sorted groups by id, not by name. Users now come first, then groups, each by name. Test: `test_the_moderators_line_lists_users_then_groups_each_by_name`. Mutation-checked.
- Declined (low): Wagtail's `chosen/<pk>/` and `chosen-multiple/` chooser views still look up any topic or post by id, so a forum moderator who guesses ids can read other forums' titles. Any admin user could already do this on main. Titles only, no body, and a pick outside their forums is refused on save. P3, no todo.
- Refuted (low, "the comment cites Wagtail 8, the project pins 7.4"): `backend/requirements.txt` pins `wagtail==8.0`, and 8.0 is installed.
