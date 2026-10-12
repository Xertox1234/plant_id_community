---
status: pending
priority: p4
issue_id: "603"
tags: [docs, todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Add a dated correction entry to archived 583's Work Log quoting the current grep output; leave the old quote (2026-10-11)"
---

# Follow-ups from PR #1048 (todo 583, the todo-466 AC 4 evidence correction)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1048 (todo 583, the todo-466 AC 4 evidence correction). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1048 (todo sweep run 2026-10-11-2219, group g1, todos 583); follow-ups: verified.

1. **low** `todos/archive/583-completed-p4-chore-466-evidence-followups.md:55` The quoted AC 1 output does not match its command. The command names todos/archive/583-completed-...md, but the last quoted line prints todos/583-pending-...md:38, a path that no longer exists. This is the same command/output mismatch todo 583 was fixing.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1048 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g1`.
