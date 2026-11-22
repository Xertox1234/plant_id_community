---
status: pending
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

- [ ] Deleting a forum, with either choice, writes a log entry naming the acting user (a test).
- [ ] The confirm page shows the subscriber count (a test).
- [ ] Moving topics on delete leaves each source-forum watcher watching the target forum (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` L4 and L5.
