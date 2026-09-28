---
status: completed
priority: p3
issue_id: "480"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: stop a round-1 repair if the review changed the PR tree

## Problem

A `todo-review` round now runs 8 or more Bash-capable agents in or against the PR
worktree: the orchestrator, the domain reviewers, 3 bug lenses, and 2 refuters per
blocking finding. The git guard blocks their git writes (commit, stash, add), but not
other file writes: a Python or shell one-liner, a test run that writes a cache or a
report, or a stray `>` redirect. The round-1 repair worker then runs `git add -A` in
that worktree, so any residue a reviewer left gets staged and committed with the
repair. The verifier checks the repair's criteria, not unrelated new files.

The repo has hit this shape before: review agents that stall leave MUTANT or probe
residue (memory: review-agent mutation residue).

Filed from todo 478 finding 5 (PR #873 live runs). The owner asked for it as its own todo
(2026-09-28).

## Recommended Action

1. `state.review_args` records each PR worktree's `git write-tree` and
   `git status --porcelain` when the round starts, and passes them in the PR record.
2. Before the repair, the workflow has the repair worker (or a small guarded
   check agent) compare the worktree against that snapshot. If anything changed,
   there is no repair, the round is incomplete (`reviewers_ok: false`), and a reason
   names the changed paths.
3. Also check at the end of round 2, so residue can't ride along into a clean round
   either.

## Acceptance Criteria

- [x] A file a reviewer creates or edits in the PR worktree during round 1 stops the
      repair, with the paths named; a test covers it.
- [x] The same check runs at the end of round 2, with a test.
- [x] An unchanged worktree still repairs normally; a test covers it.

## Work Log

### 2026-09-28 - Filed from todo 478

- Split out of 478 finding 5 at the owner's request, and re-pointed there.

### 2026-09-28 - Done (branch fix/todo-480-review-residue)

- `state.review_args` records a baseline once per round on each entry (`review_baseline`):
  HEAD, plus every path `git add -A` would take (`status --porcelain -z --untracked-files=all`,
  so a new directory is named file by file) with its content hash (`git hash-object`, which
  writes nothing). The hash catches a further edit to a file already modified or untracked at
  the baseline, which `status` alone shows unchanged. `write-tree` was dropped from the plan:
  it hashes only the index, and reviewers cannot stage (git guard).
- A rerun keeps the round's baseline. Retaking it would absorb the residue, and the repair
  would then commit it. Until the worktree matches, `review-args` leaves the group out of `prs`
  and lists it under `residue`, so one held group never stalls its wave (PR #875 review round 1).
- Round 1 with a repair: the workflow sends a `todo-reviewer` to run `state.py residue RUN G`
  (read-only, never saves the run) and relay `{"changed": [...]}`. The comparison is code. A
  dead or failed check, or any path, means no repair and `reviewers_ok: false`.
- No repair (round 1 clean or incomplete, and all of round 2): `ingest_review` compares in
  code itself. A repair without the workflow's check fails closed. Anything found → outcome
  `residue`, the paths on each entry (`review_residue`), nothing else from the round kept.
- Evidence: `python3 scripts/todos/test_state_flow.py` (163 checks; 20 new `480` checks against
  a real git worktree, one per AC: `480 AC1`, `480 AC2`, `480 AC3`) and
  `node scripts/todos/test_workflows.js` (207 checks; 6 new `review 480`). 13 mutants on a
  scratch copy, all killed (rerun retakes baseline, no in-code check, repair without check,
  no content hash, HEAD move ignored, git error passes, outcome dropped, wrong-round baseline,
  `--untracked-files=normal`, and four workflow mutants).
- Runbooks: `completing-todos` Stage C step 5 (`residue`: show the paths, ask the owner before
  removing or restoring any, rerun once `residue` prints an empty list); `todo-resume`; spec §5.3.
- Out of scope, filed as todo 483: untracked files a worker leaves before review are in the
  baseline, so the round-1 repair's `git add -A` still commits them.
