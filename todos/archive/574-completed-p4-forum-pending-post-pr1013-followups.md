---
status: completed
priority: p4
issue_id: "574"
tags: [forum, backend, docs, follow-ups, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1013 (todo 471, forum pending-post revision notes)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1013. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1013 (todo sweep run 2026-10-11-0401, group g2, todos 471); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `backend/docs/patterns/domain/forum.md:1066` The 'Pending opening posts' section says approval publishes whichever is newer, the revision or the row, so a full-row save drops the edit. That holds only for signals._publish_counterpart. The /cms/ pending-queue Approve (admin_views.approve_pending_post) always publishes latest_revision, so on that path a newer row edit is the one dropped. | also: The new hazard note (forum.md:1080) says approval of a pending opening post publishes whichever is newer, so a full-row save drops the edit. That holds only on the topic-publish path (_publish_counterpart). The /cms/ pending-queue Approve (admin_views.approve_pending_post:543) always publishes latest_revision and ignores the row.
2. **low** `backend/packages/wagtail_forum/wagtail_forum/signals.py:272` The hazard rule (no full-row post.save() over a pending revision) is only in the _publish_counterpart docstring and the pattern doc. Nothing enforces it, so a future full-row save on a pending post would still drop the edit silently.
3. **low** `backend/docs/patterns/domain/forum.md:1087` The doc says a re-screen 'never publishes', but that is only a recorded owner decision with no test or code pinning it. The rule that save_revision() or a bare post.save() must not bump updated_at is also unenforced, and no triggers.json entry exists.
4. **low** `backend/docs/patterns/domain/forum.md:1080` The new hazard note says approval of a pending opening post publishes whichever is newer, so a full-row save drops the edit. That holds only on the topic-publish path (_publish_counterpart). The /cms/ pending-queue Approve (admin_views.approve_pending_post:543) always publishes latest_revision and ignores the row.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- F1/F4 (one fix): the "Pending opening posts" section of `backend/docs/patterns/domain/forum.md` now says topic approval (`_publish_counterpart`) publishes whichever is newer, while the pending page's Approve always publishes the held revision and ignores the row; `test_queue_approve_publishes_the_revision_even_when_the_row_is_newer` pins the second.
- F2: the hazard is live since todo 579 opened the author's API edit, so it is enforced at edit time by the `forum-full-row-post-save-over-pending-revision` trigger in `docs/rules/triggers.json` (tests in `scripts/inject/test_match_triggers.py`) rather than a runtime guard in `Post.save`, which would change behaviour on every save.
- F3: "a re-screen never publishes" is now code and tests (todo 579), and `test_an_edit_to_a_pending_opening_post_never_moves_its_row` pins that the edit path leaves `updated_at` and the row's body alone.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py -k 'never_moves_its_row or row_is_newer or row_newer_than_its_revision or pending_opening_post' --create-db -v -p no:cacheprovider && python3 scripts/inject/test_match_triggers.py ForumFullRowPostSaveTrigger -v && grep -n 'pending-queue Approve\|pending page.s Approve' backend/docs/patterns/domain/forum.md` — evidence `.sweep-evidence/g2/574-ac0.txt` (not committed), last lines:

  ```text
  ----------------------------------------------------------------------
  Ran 3 tests in 0.004s

  OK
  1083:- **The pending page's Approve** (`admin_views.approve_pending_post`) never
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
