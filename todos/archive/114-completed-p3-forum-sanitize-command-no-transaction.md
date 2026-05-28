---
status: completed
priority: p3
issue_id: "114"
tags: [forum, backend, ops]
dependencies: []
---

# sanitize_forum_content management command has no transaction.atomic() — crash leaves DB partially sanitized

## Problem

`management/commands/sanitize_forum_content.py` (~26) iterates over all posts and saves
each individually with no `transaction.atomic()` wrapper. If the command crashes midway
(OOM, KeyboardInterrupt, unhandled exception), posts 1..N-1 are sanitized and posts
N..end are untouched. There is no way to resume or identify the split point. A re-run
will show zero changes for the already-sanitized posts, making it unclear what was done.

## Recommended Action

Wrap the full iteration in `transaction.atomic()` so the whole run succeeds or fails
atomically:

```python
from django.db import transaction

with transaction.atomic():
    for post in Post.objects.all():
        # sanitize and save
```

For very large datasets where a single giant transaction is impractical, process in
batches and log the last successful batch id so the run is resumable.

Also ensure `--dry-run` mode does not commit any changes.

## Acceptance Criteria

- [x] A crash mid-run does not leave the DB in a partially sanitized state.
- [x] `--dry-run` mode cannot accidentally commit changes.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

Changes (`management/commands/sanitize_forum_content.py`):
- Added `from django.db import transaction`.
- Wrapped the full `Post.objects.all().iterator()` sanitize loop in
  `with transaction.atomic()` — a mid-run crash now rolls back every sanitized
  post (all-or-nothing).
- Added `transaction.set_rollback(True)` in `--dry-run` (after the loop, inside
  the atomic block) as defense-in-depth: dry-run can never commit even if a
  future change adds an errant save.

Tests (`test_security.py::BackfillSanitizationTests`):
- `test_crash_mid_run_rolls_back_all_changes`: patches the *sanitizer* (a pure
  function, DB stays real) to raise on the 2nd post; asserts the command raises
  and BOTH posts retain their `<script>` content (the 1st save rolled back).
- AC2 covered by the existing `test_backfill_dry_run_does_not_save` + set_rollback.

Verification: `Ran 63 tests ... OK`.

Review (feature-dev:code-reviewer): 0 critical/high/medium. Confirmed atomic gives
all-or-nothing, `set_rollback` placement is correct, the iterator+atomic pattern is
fine for a one-time backfill, and the crash test genuinely discriminates old vs new
behavior. One informational note (long-held lock on huge tables) — acceptable for a
one-time backfill; batching was already noted in the todo as a future option.
