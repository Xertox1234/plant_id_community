---
status: pending
priority: p4
issue_id: "572"
tags: [todo-sweep, scripts]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "parse() joins a criterion's continuation lines the way ac_lines does, so hand-written markers are covered too (2026-10-11)"
---

# A re-point marker on a criterion's continuation line passes the engine but fails `land.py archive`

## Problem

The two acceptance-criteria parsers disagree about wrapped criteria:

- `scripts/todos/todofile.py` `ac_lines()`, behind `state.criteria_problem`,
  joins a criterion's indented continuation lines into one text.
- `scripts/check_archived_todo_status.py` `parse()`, used by `land.py archive`
  and CI, matches `REPOINT_RE` per physical line. Only the `- [ ]` line counts.

In sweep run 2026-10-11-0053, todo 386's AC 4 was re-pointed during triage with
the `→ todo 547 (re-pointed …)` marker at the end of its wrapped second line.
The engine's checks accepted it. `land.py archive` refused with "1 unchecked
criteria". Land then hand-joined the criterion onto one line and dropped a
trailing period. On the next review round `criteria_problem` blocked the group:
"criterion 3 was edited". The verified repair had to be committed by hand, and
PR #998 left the engine.

## Acceptance Criteria

- [ ] `check_archived_todo_status.parse()` treats a wrapped criterion as one
      unit, joining continuation lines the way `todofile.ac_lines` does. A
      marker anywhere in the criterion then counts as a re-point. Alternatively,
      re-pointing in the triage step always puts the marker on the checkbox
      line. Either way, a test covers the wrapped-marker case end to end:
      `criteria_problem` passes, and `archive` accepts it.
- [ ] The completing-todos runbook's stale/supersede step says where the marker
      goes.

## Work Log
