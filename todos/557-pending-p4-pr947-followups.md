---
status: pending
priority: p4
issue_id: "557"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #947 (todo 517), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #947; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #947 (todo 517)

1. **`backend/packages/wagtail_forum/wagtail_forum/signals.py:244`** (low, defect). \_refresh\_topic\_authors .distinct() does not dedupe authors under Post.Meta.ordering, so every live post triggers its own profile recount. Post.Meta.ordering makes Django add created\_at to the SELECT DISTINCT, so `.values_list("author_id", flat=True).distinct()` returns one row per live post. On a topic publish (337) or unpublish (412), an author with N live posts gets N locked `_refresh_profile` recounts, not the one todo 431 promises. The final post\_count/trust is right (the recount is idempotent), so the cost is redundant queries and row locks that grow with topic size. No test can catch it: every `_refresh_profile` call-list pin in test\_topic\_approval.py (347, 414, 451, 496, 536, 594) gives each author at most one live post at walk time.
   Suggested: Add `.order_by()` before `.distinct()` in `_refresh_topic_authors` (or collect into a `set(...)` as `mark_topic_deleting` does). Add a test where a second author has two live replies and the approval asserts `_refresh_profile` calls equal `[(author.pk,), (other.pk,)]`; it is red today with `other` listed twice.
   Seen on main: signals.py:242-245 `Post.objects.filter(topic_id=topic_id, live=True, ...).values_list("author_id", flat=True).distinct()`, no order\_by(); models/posts.py:113 `ordering = ["created_at"]`. Probe on the repo's Django 6.1.1: SQL is `SELECT DISTINCT author_id, created_at ... ORDER BY created_at`; authors 7,7,7,8 give [7,7,7,8], with .order\_by() [7,8]. Delete path (441-445) dedupes with set().

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:560`** (low, polish). test\_topic\_approval.py: copy-pasted Revision.publish failure injector and live-reply seeding; the scheduled-post comment overstates which assertions survive a Wagtail bump. (a) The todo-517 test copies the `publish_failing_for_posts` injector (560-565 = 474-479) and the live-reply seeding (570-579 = 433-442, only the author differs); the "patch Revision.publish, not save\_revision" reason (467-469) is on the first copy only, so the copies can drift. (b) The scheduled-post comment (515-516) says that if Wagtail stops sending `published` for a scheduled first publish, "the linked\_author\_id gate ... must change, not this test". Only the board assertions survive that: today's `_refresh_profile == [(author.pk,)]` (536-538) is the nested Post receiver's 0->0 recount; with that signal gone and the gate fixed, the author has no live post and the list is `[]`.
   Suggested: Hoist a module-level `_post_publishes_fail()` context manager (carrying the 467-469 reason) and a `_live_reply(topic, author)` helper, and use them in the tests at 423, 461 and 547. Reword 515-516: the board assertions (`call_count == 1`, `(1, 0)`) are the invariant; after such a bump the gate changes and the `_refresh_profile` expectation becomes `[]`.
   Seen on main: 474-479 and 560-565 are identical (`real_publish = Revision.publish` ... `raise RuntimeError("boom")`); 433-442 vs 570-579 differ only in `author=other`/`author=author`; reason comment only at 467-469. 515-516: "gate in signals.py must change, not this test"; 536-538 pin `[(author.pk,)]`, supplied by signals.py:370-371 `if linked_topic is None: _refresh_board_and_author(post)`.

## Acceptance Criteria

- [ ] Each of its 2 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
