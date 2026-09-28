---
status: completed
priority: p4
issue_id: "432"
tags: [forum, backend, moderation]
dependencies: []
source_review: "PR #815"
triage: ready
triaged: 2026-09-28
---

# Approving a topic publishes its opening post's DB row, not a pending edit

## Problem

Todo 422's forward link (`signals._publish_counterpart`, topic → never-published
opening post) publishes `obj.save_revision()`, a revision built from the post's
DB row. If the author edited the opening post while it was still pending, that
edit exists only as a revision: `submit_edit_for_moderation` never writes the
row. So the ORIGINAL body goes live when a moderator approves the topic, and
publishing cancels the edit's workflow state.

## Findings

- Raised as non-blocking by the round-2 review of PR #815.
- Narrow: it needs an edit to a post that was never published.

## Recommended Action

For the post side, publish `opening.get_latest_revision()` when it is newer
than the row, else `save_revision()`. Keep `save_revision()` for the topic
side: its row carries freshly recounted counters that a stale revision would
overwrite (see the todo 422 work log).

## Acceptance Criteria

- [x] Test: pending opening post, author edits it (revision only), moderator
      publishes the topic → the EDITED body is live.

## Work Log

### 2026-09-24 - Filed from PR #815 round 2

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-0839)

- `signals._publish_counterpart` takes `prefer_latest_revision`; the topic ->
  opening post link passes it, so a latest revision newer than the row (an edit
  that only exists as a revision) is what goes live. Otherwise it still
  publishes `save_revision()`, and the topic side is unchanged (its row carries
  the recounted counters).
- Two tests in `tests/test_topic_approval.py`: the pending edit goes live on
  admin approval, and a row saved after its latest revision still wins.
- Tests not run in this worker: the worktree has no `backend/.env`, and the
  sandbox blocks the local Postgres socket.

### 2026-09-28 - Verified by the main session (pilot, run 2026-09-28-0839)

- The worker came back `blocked` (no `backend/.env` in its worktree; fixed by
  #864's `slot_env` fallback). `blocked` is terminal in the run file, so the
  main session re-ran the tests by hand in this worktree with the #864
  `slot_env.py`, tree `91794619` unchanged before and after.
- AC0: `slot_env.py 1 -- pytest tests/test_topic_approval.py tests/workflow/test_edit_moderation.py --create-db -v`

  ```
  tests/test_topic_approval.py::test_admin_publishing_a_topic_publishes_its_opening_posts_pending_edit PASSED
  22 passed, 3 warnings in 22.20s
  ```

- Also `test_topic_approval.py` + `workflow/test_edit_moderation.py` +
  `api/test_post_revisions.py`: `37 passed, 3 warnings in 21.63s`.

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-0839)

- Archived by `land.py archive`; review is on the PR.
