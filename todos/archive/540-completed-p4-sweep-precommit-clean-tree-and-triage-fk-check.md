---
status: completed
priority: p4
issue_id: "540"
tags: [todo-sweep, engine]
dependencies: []
source_todo: "537"
triage: ready
triaged: 2026-10-10
owner_decision: "Finding 1: the worker runs pre-commit run --files <staged> with SKIP=kimi-review and re-stages before write-tree; ensure-worktree is not taught to tolerate Black (2026-10-10)"
---

# Todo sweep: workers stop with a pre-commit-clean tree; triage checks FKs on deleted models

## Problem

Two sweep-engine findings from run 2026-10-10-0234, parked in todo 537 and promoted here on 2026-10-10.
The owner sent 537's engine items to todo 529, but these two are outside 529's scope (follow-up ranking), so
they got their own todo; 537's engine finding 3 went to 529.

## Findings

1. **Workers stop with a tree that fails pre-commit** (low). On g4 (#978) the verified tree hit Black (one line
   join) and detect-secrets (a fake `?token=` test URL). `ensure-worktree` tolerates only the
   trailing-whitespace/EOF fixers, so Land had to hand-patch with owner approval and re-record `tree_id`.
   Suggested: have the worker run `pre-commit run --files <staged>` before stopping, or add Black's reformat to
   the tolerated fixers.
2. **Triage missed an FK** (low). Triage for 532 said "the model has no FK", but `created_by` was an FK to `User`,
   and the worker caught it. Suggested: the triager prompt should check `ForeignKey`/`on_delete` on any model
   being deleted.

## Acceptance Criteria

- [x] A worker's verified tree passes `pre-commit run --files <staged paths>`, or Black's reformat is a tolerated
      fixer in `ensure-worktree` (test either way).
- [x] The triager's instructions tell it to check `ForeignKey`/`on_delete` on any model a todo deletes.

## Resolution

Run 2026-10-10-2307:

- Finding 1 (owner decision 2026-10-10): todo-worker.md Finish step 2 runs `pre-commit run --files` on the
  staged paths with `SKIP=kimi-review`, re-stages any fixer rewrite and repeats before `write-tree`.
  `ensure-worktree` is unchanged. `scripts/todos/test_workflows.js` pins the order, and this group's own
  staged tree passes the same command.
- Finding 2: todo-triager.md step 2 tells the triager to check `ForeignKey`, `OneToOneField`,
  `ManyToManyField` and `on_delete` on a model a todo deletes and on every model that points at it.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-2307)

- Added the pre-commit step to the worker's Finish, before `write-tree`, and noted it in the Land runbook.
- Added the relation check to the triager's classify step, with a doc test for both instructions.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-2307)

- AC 1: `bash -c 'set -eo pipefail; cd . && /usr/bin/git diff --cached --name-only --diff-filter=d -z -- . ":(exclude).claude/agents" | SKIP=kimi-review xargs -0 pre-commit run --files; /usr/bin/git diff --cached --name-only --diff-filter=d -z -- .claude/agents | SKIP=kimi-review,end-of-file-fixer xargs -0 pre-commit run --files; for f in .claude/agents/todo-worker.md .claude/agents/todo-verifier.md .claude/agents/todo-triager.md; do test -z "$(tail -c1 "$f" | tr -d "\n")" || { echo "no final newline: $f"; exit 1; }; done; echo "final newline present on the three agent docs"; node scripts/todos/test_workflows.js | grep -E "540 AC1|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/540-ac0.txt` (not committed), last lines:

  ```text
  kimi-review staged-diff gate (CRITICAL blocks)............................Skipped
  - hook id: kimi-review
  final newline present on the three agent docs
    PASS  540 AC1: todo-worker.md Finish runs pre-commit (kimi-review skipped) on the staged paths, after staging and before write-tree, and re-stages what a fixer rewrote
  All checks passed.
  ```

- AC 2: `bash -c 'set -eo pipefail; cd . && grep -n -A3 "deletes a model" .claude/agents/todo-triager.md; node scripts/todos/test_workflows.js | grep -E "540 AC2|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/540-ac1.txt` (not committed), last lines:

  ```text
  30-   `ManyToManyField` and `on_delete` in it and in every model that points at it (todo 540: a triage once said
  31-   "the model has no FK" while `created_by` was an FK to `User`). Name each relation and its `on_delete` in
  32-   `evidence`, or say you found none; a relation means a migration and a data question the worker must plan for.
    PASS  540 AC2: todo-triager.md tells it to check ForeignKey/on_delete on a model a todo deletes
  All checks passed.
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-2307)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
