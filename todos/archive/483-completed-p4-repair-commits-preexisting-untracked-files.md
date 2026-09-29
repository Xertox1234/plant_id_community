---
status: completed
priority: p4
issue_id: "483"
tags: [harness, todo-sweep]
dependencies: []
triage: needs-design
triaged: 2026-09-28
blocked_on: "Owner choice between option 1 (review-args refuses untracked files) and option 2 (the repair stages only the paths it changed, and the verifier checks)."
owner_decision: "Option 2: the repair stages only the paths it changed, and the verifier checks nothing else is staged (2026-09-28)"
---

# Todo sweep: a round-1 repair commits untracked files the worker left before review

## Problem

The round-1 repair worker runs `git add -A` in the PR worktree. Todo 480 stops that from
committing what a *reviewer* left, by comparing the worktree with a baseline taken when the
round starts. But the baseline itself can hold untracked files: Land commits only the index,
and `_unstaged_outside_land` deliberately ignores untracked test artifacts. Those files are in
the baseline, so the residue check passes them, and the repair's `git add -A` commits them into
the PR.

Filed from todo 480 (PR review of the design, 2026-09-28).

## Recommended Action

Pick one:

1. `review-args` refuses a worktree with untracked, non-ignored files, naming them, the way
   `ensure-worktree` already refuses unstaged tracked changes outside Land's paths.
2. Or the repair stages only the paths it changed, not `git add -A`, and the verifier checks
   that nothing else is staged.

## Acceptance Criteria

- [x] An untracked, non-ignored file present when round 1 starts is never committed by the
      round-1 repair; a test covers it.

## Work Log

### 2026-09-28 - Filed from todo 480

- Found while designing 480's baseline: it keeps pre-existing untracked files by design.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Option 2, as the owner chose. `review-args` lists the round's pre-existing untracked files as
  `untracked_before` (from the baseline's `??` entries). The repair prompt names them and tells the worker to
  stage only the paths it changed, never `git add -A`; `todo-worker.md` says the same for `MODE: repair`.
- The post-repair verifier gets `FILES_CHANGED` and `UNTRACKED_BEFORE`: its clean checks ignore exactly those
  untracked paths, and any staged path outside `FILES_CHANGED` fails it (`todo-verifier.md`).
- In code, `ingest-review` refuses a round-1 repair that staged a file untracked when the round started
  (`git diff --cached --name-only HEAD` against the baseline), so it is never committed. Test in
  `test_state_flow.py` against a real git worktree: staging `notes.txt` blocks; staging only the change passes.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/483-ac0.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
