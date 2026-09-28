---
name: todo-next
description: Pick and complete the single highest-priority pending todo. Daily-driver workflow. Use when the user says "/todo-next", "do next todo", or "pick up next task".
---

# Todo Next

Runs the `completing-todos` engine on one todo: the top-priority open todo whose dependencies are done,
that nobody has in flight and that isn't stranded.

1. Announce, then follow `completing-todos` with selector `next` and `--workers 1`.
2. There's no separate triage PR. The triage fields are written into the todo's own PR during Land (see the engine's
   "Triage PR" section). If triage finds it blocked, record the decision, then offer the next candidate from
   `scan.py --selector sweep --dry-run`.
