---
status: pending
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

- [ ] A file a reviewer creates or edits in the PR worktree during round 1 stops the
      repair, with the paths named; a test covers it.
- [ ] The same check runs at the end of round 2, with a test.
- [ ] An unchanged worktree still repairs normally; a test covers it.

## Work Log

### 2026-09-28 - Filed from todo 478

- Split out of 478 finding 5 at the owner's request, and re-pointed there.
