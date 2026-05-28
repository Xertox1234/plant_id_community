---
status: pending
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

- [ ] A crash mid-run does not leave the DB in a partially sanitized state.
- [ ] `--dry-run` mode cannot accidentally commit changes.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
