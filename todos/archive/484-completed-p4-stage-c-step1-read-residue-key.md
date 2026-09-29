---
status: completed
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

- [x] Stage C steps 1 and 2 of `.claude/skills/completing-todos/SKILL.md` tell the operator to
      read `review-args`' `residue` key and point to step 5.

## Work Log

### 2026-09-28 - Filed from PR #875 review round 2

- Non-blocking note from the round-2 verify; the review loop budget files it here.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Stage C steps 1 and 2 of `completing-todos/SKILL.md` now tell the operator to read `review-args`'
  `residue` key first: a group listed there got no review this time, and is handled per step 5.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `sed -n '/^## Stage C/,/^3. What a round runs/p' /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g8/484-ac0.txt`, last lines:

  ```text
     group to `reviewed`, then arm.
     `rerun` → run round 2 again once. A second incomplete round 2 comes back `blocked`; report it.
     `residue` → do NOT arm; see step 5.
     `blocked` → stop that PR and report it. Its reason also names any dismissed critical the owner must clear.
  3. What a round runs, for every size: three `todo-reviewer` bug lenses, plus the checklist lane.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
