---
status: pending
priority: p3
issue_id: "468"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep v2 Part A: follow-ups from the final branch review

## Problem

The final whole-branch review of the todo sweep v2 engine (Part A) fixed its
Critical, Important and cheap Minor findings in one wave. Fifteen smaller
items were ruled follow-up, not fixed. None is reachable on today's backlog
or in the first pilot, but each is a real gap in a later sweep.

## Findings

Source: the final review of `feat/todo-sweep-v2-engine` (2026-09-27), and
the controller rulings on it. Line numbers are at the fix-wave commit.

- **apply_triage is not transactional.** A mid-batch failure leaves earlier
  todos renamed, and the reset-stranded `git mv` is not idempotent on re-run
  (`scripts/todos/state.py:220`).
- **ingest_review does not validate stage or round order.** A re-ingest of a
  stale round-1 output can overwrite `tree_id` and `verified_ac` on a group
  that is already reviewed (`scripts/todos/state.py:486`).
- **The review doc is not a single-lane resource.** Two groups sourced from
  one `docs/reviews/*.md` can both check it off and race the `-COMPLETED`
  rename (`scripts/todos/group.py:18`, `scripts/todos/land.py:391`).
- **The triager reads the local checkout.** `triage_args` passes no root, so
  the triager reads the main checkout, which can be behind origin/main
  (`scripts/todos/state.py:133`, `.claude/workflows/todo-triage.js:33`). The
  Task 15 runbook must run triage from a fresh origin/main tree.
- **`.worktreeinclude` delivery is unverified.** Nothing has shown that
  `backend/.env` and `web/.env` reach an `isolation: worktree` checkout
  (`.worktreeinclude:5-6`). This is pilot check P5.
- **A failed tree check leaves the re-added worktree on disk.** It is
  non-destructive, and the message names the path
  (`scripts/todos/state.py:600-605`).
- **The workflow harness does not schema-validate its fixtures.** The triage
  stub `{ id: 'WRONG', class: 'ready' }` is not a valid TRIAGE record
  (`scripts/todos/test_workflows.js:78`).
- **`source_review` dangles after a COMPLETED rename.** Only the archiving
  todo's own `source_review` follows the rename. Other archived todos that
  name the same review doc keep the old path (`scripts/todos/land.py:403`).
- **m1: `needs-design` and `stale` todos are re-asked every sweep.** Scan
  skips only `triage: blocked-*` (`scripts/todos/scan.py:139`), and
  apply-triage writes the triager's class verbatim
  (`scripts/todos/state.py:229`).
- **m6: worktree re-add has no `origin/<branch>` fallback.** When the local
  branch is gone, recovery fails even though the branch is pushed
  (`scripts/todos/state.py:590-594`).
- **m7: the guard allows `git -C <MAIN> add/mv/rm`.** A worker that confuses
  MAIN with WT can stage into the owner's main checkout
  (`scripts/todos/worker_git_guard.py:31`).
- **m8: review-stage reviewers are prompt-bound only.** The `general-purpose`
  and `code-review-orchestrator` reviewers are not guarded
  (`.claude/workflows/todo-review.js:157-160`,
  `scripts/todos/worker_git_guard.py:30`). Consider a guarded
  `todo-reviewer` agent type.
- **m12: three Part B carry-forwards are missing from the Task 15 text**
  (`docs/superpowers/plans/2026-09-27-todo-sweep-v2.md:3862`): triage from
  an origin/main tree; spec §7.2's "rebase on origin/main before push, and a
  non-mechanical conflict stops the group"; and pilot P1 recording that the
  isolation worktree's HEAD equals origin/main.
- **The verifier gets ids and the claimed tree id only in prose.** No
  verifier step consumes `CLAIMED_TREE`; the main session compares tree ids
  (`.claude/agents/todo-verifier.md:18`,
  `.claude/workflows/todo-execute.js:90`).
- **Retry fires only on an explicit `fail`.** A null verdict goes to
  `failed`, and the runbook retries it in a fresh worktree instead of the
  same one (`.claude/workflows/todo-execute.js:123`).

## Recommended Action

1. Make `apply_triage` skip the `git mv` when the pending path already exists
   and the old one is gone, and add a re-run test.
2. Guard `ingest_review` on `stage == pr_open` and
   `review_round == round - 1`.
3. Add a `review:<path>` lane before the first `docs/reviews`-sourced batch,
   and rewrite sibling `source_review` values on a COMPLETED rename.
4. Add a `root` field to `triage_args` and a `ROOT:` line to the triage
   prompt, pointing at a scratch origin/main worktree. Add the three m12
   items to the Task 15 runbook text.
5. Record the pilot results for P1 and P5 in the pilot log.
6. Remove a re-added worktree when its tree check fails, or name it in the
   wrap-up.
7. Add a tiny fixture validator to `test_workflows.js` once pilot P6 shows
   real record shapes.
8. Skip `needs-design` and `stale` todos that have an `owner_decision` and no
   change since, or write `blocked-owner` when Decide blocks them.
9. Fall back to
   `git worktree add --no-track -b <branch> <target> origin/<branch>`.
10. Deny an allowed write subcommand whose `-C` target is outside the
    agent's worktree, and add a guarded `todo-reviewer` agent type.
11. Decide whether the verifier should compare `CLAIMED_TREE` itself, and
    whether a null verdict should retry in the same worktree.

## Technical Details

- Engine: `scripts/todos/state.py`, `scan.py`, `group.py`, `land.py`,
  `worker_git_guard.py`.
- Agents: `.claude/agents/todo-worker.md`, `todo-verifier.md`,
  `todo-triager.md`.
- Workflows: `.claude/workflows/todo-execute.js`, `todo-review.js`,
  `todo-triage.js`.
- Spec: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`
  (§4.1, §5.2, §7.2).
- Tests: `python3 scripts/todos/test_<module>.py`,
  `node scripts/todos/test_workflows.js`,
  `bash .claude/hooks/test-guard-todo-worker-git.sh`.

## Acceptance Criteria

- [ ] Re-running `apply-triage` after a mid-batch failure succeeds, with a test.
- [ ] `ingest-review` refuses an output whose round does not follow the
      group's `review_round`, with a test.
- [ ] Two groups sourced from one review doc never share or neighbour a wave,
      with a test.
- [ ] Triage reads todos from an origin/main tree, and the Task 15 runbook
      says so.
- [ ] Pilot P5 records whether `backend/.env` and `web/.env` reach a worker
      worktree.
- [ ] A failed tree check in `ensure-worktree` leaves no new worktree behind,
      or the wrap-up lists it.
- [ ] `test_workflows.js` rejects a fixture that does not match its schema.
- [ ] Archiving the last finding of a review doc updates every archived
      todo's `source_review` that named it.
- [ ] A `needs-design` or `stale` todo the owner already answered is not
      re-asked by the next sweep, with a test.
- [ ] `ensure-worktree` recovers from `origin/<branch>` when the local branch
      is gone, with a test.
- [ ] The guard denies `git -C <MAIN> add`, `mv` and `rm` for guarded agents,
      with a test.
- [ ] Review-stage reviewers run as a guarded agent type, or the decision
      not to is recorded here.
- [ ] The Task 15 runbook text carries the three m12 carry-forwards.
- [ ] The verifier either consumes `CLAIMED_TREE` or the prompt drops it,
      and the decision is recorded here.
- [ ] The retry-on-null-verdict decision is recorded here.

## Work Log

### 2026-09-27 - Filed from the final branch review

- The final review of todo sweep v2 Part A ruled these fifteen items
  follow-up. The fix wave on `feat/todo-sweep-v2-engine` fixed C1, I2-I5
  and m2-m5, m9-m11.

## Notes

p3: none of these is reachable on today's backlog or in the first pilot.
m12 and the triage-root item should land before Part B's first real sweep.
