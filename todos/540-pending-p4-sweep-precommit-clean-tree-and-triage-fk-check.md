---
status: pending
priority: p4
issue_id: "540"
tags: [todo-sweep, engine]
dependencies: []
source_todo: "537"
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

- [ ] A worker's verified tree passes `pre-commit run --files <staged paths>`, or Black's reformat is a tolerated
      fixer in `ensure-worktree` (test either way).
- [ ] The triager's instructions tell it to check `ForeignKey`/`on_delete` on any model a todo deletes.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.
