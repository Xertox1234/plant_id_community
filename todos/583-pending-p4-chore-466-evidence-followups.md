---
status: pending
priority: p4
issue_id: "583"
tags: [todos, follow-ups]
dependencies: []
---

# Follow-ups from PR #1022 (todo 466, 466 split into 580-582)

## Problem

Todo-sweep run 2026-10-11-1434 merged PR #1022 (the decision split). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1022 (todo sweep run 2026-10-11-1434, group g1, todos 466); follow-ups: verified.

1. **low** `todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md:78` The AC 4 evidence does not match its command. `grep -H` over 580, 581 and 582 prints the files in that order, but the quoted 'last lines' put 581 before 580 and show nothing from 582. So the evidence does not prove that todo 582 exists with status pending.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1022 (todo 466).
