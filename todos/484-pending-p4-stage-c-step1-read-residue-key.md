---
status: pending
priority: p4
issue_id: "484"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
---

# Todo sweep: Stage C step 1 should read review-args' `residue` key

## Problem

Since PR #875 (todo 480), `state.py review-args` leaves a group whose worktree still holds
review residue out of `prs` and lists it under `residue`. Only `completing-todos` Stage C step 5
mentions that key. Steps 1 and 2 don't tell the operator to read it, so a held group is not lost
(it stays due for the round), but it only surfaces when someone notices it hasn't advanced.

Filed from PR #875 review round 2 (non-blocking note).

## Recommended Action

Add one line to Stage C steps 1 and 2: if `review-args` prints a non-empty `residue`, those
groups were left out; handle them per step 5.

## Acceptance Criteria

- [ ] Stage C steps 1 and 2 of `.claude/skills/completing-todos/SKILL.md` tell the operator to
      read `review-args`' `residue` key and point to step 5.

## Work Log

### 2026-09-28 - Filed from PR #875 review round 2

- Non-blocking note from the round-2 verify; the review loop budget files it here.
