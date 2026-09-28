---
name: todo-sweep
description: Batch through all pending todos in priority order. Use when you want to clear the backlog — when the user says "/todo-sweep", "sweep todos", "clear all pending todos", or "batch complete todos".
---

# Todo Sweep

Selects every open todo and runs the `completing-todos` engine on it (todo sweep v2).

1. Parse flags: `--workers N` (1–3, default 3), `--limit N`, `--retriage`, `--dry-run`.
2. Announce "I'm using todo-sweep; the completing-todos engine does the work." Then follow `completing-todos`
   with selector `sweep` and those flags.

Todos triaged `blocked-*` are skipped until their file changes or you pass `--retriage`. Todos in flight
elsewhere (a branch, worktree or open PR) are listed but not touched.
