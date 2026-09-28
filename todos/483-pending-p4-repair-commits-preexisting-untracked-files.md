---
status: pending
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

- [ ] An untracked, non-ignored file present when round 1 starts is never committed by the
      round-1 repair; a test covers it.

## Work Log

### 2026-09-28 - Filed from todo 480

- Found while designing 480's baseline: it keeps pre-existing untracked files by design.
