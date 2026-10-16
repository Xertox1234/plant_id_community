---
status: pending
priority: p3
issue_id: "617"
tags: [todo-sweep, tooling, review]
dependencies: []
owner_decision: "Implement as proposed; AC 3: KEEP the manual round-1 medium read in SKILL.md as a fallback for regressions the reviewer did not flag (2026-10-11)"
triage: ready
triaged: 2026-10-16
---

# todo-review: a medium that is a regression against main should hold the PR, not become a follow-up

## Problem

`todo-review.js` treats only `critical`/`high` as blocking (`BLOCKING`). Every `medium` becomes a follow-up,
even when it is a NEW regression that the PR introduces. So round 1 comes back `clean` and the PR heads to
round 2 and auto-merge carrying the regression. Only the main session reading every medium by hand catches it.

It has happened in four runs now:

- Run 2026-10-11-1434: round-1 `clean` hid a new regression (memory note on that batch).
- Run 2026-10-11-0401: guard regressions in round-2 mediums.
- Run 2026-10-11-2219, three of 15 PRs, each needing an owner-approved hand repair before round 2:
  - #1055 lost three detections in the requests exception guard.
  - #1061 let workers edit a recorded `stray_worktree`, the exact tree todo 577 #5 denies.
  - #1063's runbook told the operator to "keep both sides" of a todo-file conflict, which corrupts it.

The signal is already in the reviewers' prose ("flagged on main but quiet here", "regression vs main"). The
schema just has no field for it.

## Proposed Solution

- Add `regression: boolean` to the reviewer FINDINGS schema in `.claude/workflows/todo-review.js`. Prompt the
  reviewer to set it only when the PR head behaves worse than origin/main on the same input, with the probe
  as evidence.
- Treat a `medium` with `regression: true` as blocking in round 1, so the round-1 repair fixes it and the
  refuters judge it like a high.
- In round 2, a regression medium blocks like a high, so the owner sees it through `hand-round`.

## Acceptance Criteria

- [ ] The reviewer schema carries `regression` and the prompt says when to set it. A `test_workflows.js` case
      shows a medium regression entering `blocking` in round 1, and a medium without it staying a follow-up.
- [ ] Round 2: a medium regression blocks the group (`ingest-review` → blocked), with a `test_state_flow.py`
      or `test_state.py` case.
- [ ] `completing-todos` SKILL.md Stage C drops the manual "read round-1 mediums for regressions" step, or
      keeps it as a fallback, and says which.

## Work Log

### 2026-10-11 - Filed from run 2026-10-11-2219 (owner request)

The owner asked for a todo after the run's pattern review.

### 2026-10-11 - Owner decision: keep the manual read as a fallback

Implement the proposed `regression` flag as written. For AC 3, the owner chose to **keep** the manual
"read round-1 mediums for regressions" step in `completing-todos` SKILL.md Stage C, shortened to a fallback:
skim the mediums for wording like "vs main" or "flagged on main but quiet here" that the reviewer did not
flag. A reviewer can fail to set the flag, so the hand read stays as a backstop.
