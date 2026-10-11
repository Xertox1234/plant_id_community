---
status: completed
priority: p4
issue_id: "583"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1022 (todo 466).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Finding 1 (AC 4 evidence of todo 466 out of order, nothing from 582): fixed as
  a doc correction, no behaviour change, so no test. Appended a correction entry
  to the Work Log of `todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md`.
- The correction quotes the full AC 4 output re-run against the PR #1022 merge
  commit `9338c8a6` (580–582 are archived now), showing 580, 581 and 582 each
  with `status: pending`, in command order.
- Land's original quoted block is left untouched; the new entry supersedes it.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `grep -n -E 'AC 4 evidence corrected|58[0-2]-pending-[a-z0-9-]+\.md:status: pending|Finding 1 ' todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md todos/archive/583-completed-p4-chore-466-evidence-followups.md` — evidence `.sweep-evidence/g1/583-ac0.txt` (not committed), last lines:

  ```text
  todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md:92:### 2026-10-11 - AC 4 evidence corrected by the todo sweep (run 2026-10-11-2219, todo 583)
  todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md:103:  todos/580-pending-p3-mypy-ci-gate-one-app.md:status: pending
  todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md:106:  todos/581-pending-p3-openapi-fail-on-warn.md:status: pending
  todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md:109:  todos/582-pending-p3-openapi-request-examples.md:status: pending
  todos/583-pending-p4-chore-466-evidence-followups.md:38:- Finding 1 (AC 4 evidence of todo 466 out of order, nothing from 582): fixed as
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
