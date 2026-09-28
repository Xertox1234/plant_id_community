---
name: todo-batch
description: Filter pending todos by priority, tags, or IDs and sweep through the matching subset. Use when the user says "/todo-batch", "batch todos", "sweep p3 todos", or "do all blog todos".
---

# Todo Batch

Like `todo-sweep`, restricted to a subset. The `completing-todos` engine does the work.

1. Parse filters from the message: `--priority pX`, `--ids A,B`, `--tag name`, `--exclude-ids A,B`, plus
   `--workers N` (1–3), `--limit N`, `--retriage`, `--dry-run`. Natural language maps to flags:
   "batch all p3 blog todos" → `--priority p3 --tag blog`; "do todos 074, 075" → `--ids 074,075`.
2. If no filter was given, say so and suggest `todo-sweep` instead. Do not guess a filter.
3. Announce, then follow `completing-todos` with selector `batch` and the flags.
