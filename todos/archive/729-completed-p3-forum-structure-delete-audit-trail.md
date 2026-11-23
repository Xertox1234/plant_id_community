---
status: completed
priority: p3
issue_id: "729"
tags: [forum, wagtail, admin, moderation]
dependencies: []
triage: ready
triaged: 2026-11-22
owner_decision: "A mute is never overridden; otherwise keep the stronger level (owner 2026-11-22)"
---

# Forum structure screen: log destructive actions and warn before erasing subscriptions

## Problem

The /cms/ forum structure screen can delete a whole forum and its threads
without writing a Wagtail log entry. Deleting a forum also silently deletes
every member's watch level and read markers on it, even when its topics are
moved to another forum. Neither causes a problem with one real user, but both
are moderation-trail and member-trust gaps once the app is live.

## Findings

- **L4:** `services/forum_structure.py:261-268` (`delete_topics`) calls `topic.delete()` in a loop, and `admin/forum_delete.py:221-247` deletes the forum row directly. `change_type`, `move_forum` and `empty_category` write no log either. By contrast, `RejectPendingView` deletes through `action_registry.get_action_class(type(target), "delete")`, which logs `wagtail.delete` (`admin_views.py:936`). Source: audit 2026-11-21 (wagtail-reviewer). Paths are under `backend/packages/wagtail_forum/wagtail_forum/`.
- **L5:** `ForumSubscription.forum` (`models/subscriptions.py`) and `ForumRead.forum` (`models/topic_reads.py:112`) are `CASCADE`. On the "move the topics to …" path the topics move, but the subscriptions on the deleted source forum are erased, and the confirm page does not mention subscribers.

## Recommended Action

1. Write one `log()` entry per forum delete, including the topic count and the move-or-delete choice, plus one for each `change_type` and `move_forum`. Alternatively, route the topic deletes through the registry's delete action with `skip_permission_checks=True`, since the form has already gated them.
2. Show the subscriber count on the delete confirm page. On the move path, carry each `ForumSubscription` over to the target forum, keeping the higher level if the member already watches it.

## Technical Details

- Rule: `docs/rules/wagtail.md`. Decide whether a bulk `topic.delete()` loop should log every topic or once per forum. Once per forum is enough for an audit trail and avoids hundreds of log rows.

## Acceptance Criteria

- [x] Deleting a forum, with either choice, writes a log entry naming the acting user (a test).
- [x] The confirm page shows the subscriber count (a test).
- [x] Moving topics on delete leaves each source-forum watcher watching the target forum (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` L4 and L5.

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- L4 was half stale: the forum row's delete already went through Wagtail's registry delete action and logged a bare `wagtail.delete`. `ForumDeleteView.delete_action` (`backend/packages/wagtail_forum/wagtail_forum/admin/forum_delete.py`) now writes that one entry itself, with the acting user and, in `data`, the topic count, the move-or-delete choice, the target forum, and the subscriber counts (for a category: the forums moved and where). One entry per forum, not one per topic.
- A type change logs `wagtail_forum.forum.change_type` and a move in the tree logs `wagtail_forum.forum.move` (a move that changes nothing logs nothing); both are registered in `wagtail_hooks.py` and written in the same transaction as the change, so a refused action leaves no entry.
- L5: the confirm page shows how many members have a watch setting on the forum. On the move path `services.forum_structure.carry_subscriptions` copies each level to the target before the delete cascades. Owner rule: a mute on the target is never overridden; otherwise the stronger level stays. Judgment calls inside that rule: a source mute is carried only when the member has no level on the target, and never replaces one they chose there.
- Not done, on purpose: `ForumRead` marks are not carried (a source "mark forum read" would mark the target's own topics read), and a type change does not carry levels (the row survives, so nothing is erased). Carrying does not check that the member may read the target: the new-topic fan-out (`readers_of_forum`) and the API check grants on every read.
- Tests: `tests/test_admin_forum_delete.py` (log entry for both choices and for a category, no entry on a refused delete, subscriber count, carry-over through the view, every level pair), plus one logged and one refused case each in `tests/test_admin_forum_change_type.py` and `tests/test_admin_forum_structure_tree.py`.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_deleting_a_forum_logs_who_did_it_and_what_became_of_the_topics --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g12/729-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 2 passed, 3 warnings in 21.12s ========================
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_the_confirm_page_shows_the_subscriber_count --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g12/729-ac1.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 20.66s ========================
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_moving_topics_on_delete_leaves_each_watcher_watching_the_target --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g12/729-ac2.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 21.35s ========================
  ```

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-23 - Repaired by the todo sweep (run 2026-11-22-1957)

- Review round 1 found a regression: a member who had muted the deleted forum and had no setting on the target got a mute on the target, which hid the target's own topics from their Recent list and digest. On main they kept seeing them.
- `carry_subscriptions` (`backend/packages/wagtail_forum/wagtail_forum/services/forum_structure.py`) no longer carries a source mute at all; only tracking and watching levels are carried. This replaces the earlier judgment call "a source mute is carried only when the member has no level on the target".
- `tests/test_admin_forum_delete.py`: the `(muted, none)` case now expects no row on the target, and the first-post and tracking levels with no target row are covered too.

### 2026-11-23 - Review round 1: non-blocking findings

- **Fixed: the move log's no-op guard had no test (medium).** A new test drops a row where it
  already is and expects no log entry; logging every move fails it.
- **Fixed: the confirm page said every watch setting is carried over (low).** After the round-1
  repair a mute is not carried, so the notice now says watching and tracking settings are
  carried and a mute is not.
- **Declined: the type-change log takes its topic count from the form (low, two reviewers).** A
  topic posted between the form and the write makes the entry's count off by that topic. Staff
  only, and the delete log already uses the real count.
- **Declined: the move log reads the old position before `move_forum` takes its lock (low).** Two
  staff moving the same row at the same moment can log a stale "from". The move itself is safe.
- **Declined: the "refused writes no log entry" tests would pass without the atomic wrappers
  (low).** They fail before `log()` runs; the wrappers guard a later failure these tests do not
  reach.
- **Declined: the subscriber notice shows for a row retyped to a category or link (low).** Such
  a row keeps its subscription rows, so the count shown is true.
- **Declined: more arms of the type-change and move-delete logs are untested (low, two
  findings).** The delete, no-topics and no-subscribers arms are not pinned by a test.
