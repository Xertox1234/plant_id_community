---
name: completing-todos
description: Work through pending todo files in todos/ — one, many, or all. Drives each through implementation → verification → code review → archival. Use when the user says "complete the pending todos", "clear todos", "finish todo NNN", or invokes /completing-todos.
---

# Completing Todos

Drive `status: pending` todo files in `todos/` through implementation, verification, code review, and archival. Reuse `code-review-orchestrator` for the review step; never reimplement its routing.

**Announce at start:** "I'm using the completing-todos skill to work through pending todos."

## Trigger phrases

- `/completing-todos`
- "complete the pending todos"
- "work through the todos"
- "clear all todos"
- "finish todo NNN" (single-todo mode — parse `NNN` and treat as `--ids NNN`)

## Filter flags

Parsed from the user's invocation message:

- `--priority p1` — restrict to one priority (default: all)
- `--ids 050,052,056` — restrict to specific issue_ids
- `--skip 053,054` — exclude specific issue_ids
- `--dry-run` — print the plan and per-todo prompts; touch nothing

Natural-language id references ("finish todo 050", "do 052 and 056") normalize to the equivalent `--ids` flag during Phase 0.

## Workflow

The skill runs in three phases. Phase 0 confirms scope. Phase 1 loops per todo. Phase 2 wraps up.

(Phase sections appear below — populated in subsequent commits.)

## Phases

### Phase 0 — Scope Confirmation

(populated in Task 5)

### Phase 1 — Per-Todo Loop

(populated in Tasks 6–7)

### Phase 2 — Wrap-Up

(populated in Task 5)

## Resumability

(populated in Task 5)

## Safety Rails

(populated in Task 8)
