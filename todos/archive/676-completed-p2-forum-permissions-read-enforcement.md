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

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: 0049 dropped `Forum.is_hidden` in the deploy that stops reading it, while Railway's preDeploy `migrate` runs under the previous release, which filters on it. 0049 now gives the column `db_default=False` and removes it from state only (expand/contract, `docs/rules/database.md`); a later migration must drop the column.
- 0048's data migration is unchanged: hidden rows still become No access grants, and its MigrationExecutor test still passes.
- The README now says the column stays until a later migration drops it.

### 2026-10-30 - Review round 1: non-blocking findings (hand fixes)

- Fixed (medium): moving a forum, or emptying a category into another, kept it hidden only when the old category was hidden from guests AND members. A forum under a guest-restricted or group-only category opened up when it moved to an open one. `keep_out_whoever_the_category_kept_out` (`services/forum_permissions.py`) now gives every principal that could not list the old category *No access* on the forum. Grants union, so afterwards the forum is readable only through a principal that could list the old category. A group the old category let in keeps the members' former role as its own row. Tests: `test_leaving_a_guest_restricted_category_keeps_guests_out` and `test_leaving_a_group_only_category_keeps_it_to_that_group` (`test_admin_forum_structure_tree.py`). Mutation-checked, both the rule and the group carry-over.
- Fixed (medium): notifications skipped the per-recipient read check whenever guests could read the post. A member whose grants deny the forum, while guests keep their default, still got notified. `eligibility.recheck` now checks every recipient's grants for any live post; `readers_of_forum` runs a constant three queries. Test: `test_a_member_denied_a_guest_readable_forum_gets_no_notification`. Mutation-checked.
- Declined (low): `pacing._count_folds` still counts folded replies in the guest view, so "N more replies" can undercount on a member-only forum. The count is only a summary: it never sends content and never leaks a forum. P3, no todo per the sweep rule.

### 2026-10-30 - Review round 2: non-blocking findings (hand fixes)

Round 2 came back clean (nothing blocking, nothing refuted).
- Fixed (low, flagged as a regression): `ForumIndex.get_context` used `visible_forums(None)`, which also applies the API's ForumIndex gate. A private or draft index served to someone Wagtail let in therefore listed no boards; main listed them. It now applies the guest grant rule without that gate, since the page being served is the index. Test: `test_a_private_forum_index_still_lists_its_forums_to_whoever_it_serves` (`test_page_serving.py`). Mutation-checked.
- Fixed (medium): changing a forum's Category on the admin edit form skipped the round-1 keep-out rule, so a forum moved out of a restricted category opened up. `ForumAdminForm` now applies `keep_out_whoever_the_category_kept_out` when an existing forum's parent changes. Test: `test_changing_the_category_on_the_edit_form_keeps_guests_out`, through the edit view. Mutation-checked.
- Fixed (low): `docs/rules/forum.md` still said `_visible_boards()` filters on `is_hidden`. It now describes grants, categories, password unlocks and the `request=` rule.
- Still declined, re-rated medium by two round-2 reviewers: `pacing._count_folds` counts folded replies in the guest view. Since round 1's `recheck` change, a coalesced push on a member- or group-only forum says "1 reply" where there were N. The decline still stands: the count is a summary in a notification that is already allowed, it sends no content and leaks no forum, and the fix needs a per-recipient fold count. P3, no todo.
- Declined (low): the AI surfaces (topic summary and its task, similar topics, RAG retrieval) still use the guest view, so a member-only forum's topic has no summary (404). That fails closed and leaks nothing; members-only AI coverage is a feature, not a fix.
- Owner follow-up (low): the expand/contract migration leaves the `is_hidden` column in the database (0049 removes it from state only). Dropping it is a later deploy that no todo tracks yet. It is in the morning summary for the owner.
