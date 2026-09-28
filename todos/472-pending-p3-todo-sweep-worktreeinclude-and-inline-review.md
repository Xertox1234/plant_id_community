---
status: pending
priority: p3
issue_id: "472"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep v2: `web/.env` never reaches a worker, and the review falls back inline

## Problem

Two gaps from the Task 14 pilot (todo 469, items 3 and 8) that had no acceptance
criterion there. Both are recorded in
`docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md` (rows P5 and P8).

## Findings

1. **`.worktreeinclude` delivered nothing** to either `isolation: worktree`
   checkout (P5 FAIL). Hypothesis, not verified: the harness reads the file
   from the main checkout, whose branch had no `.worktreeinclude` at the time.
   #864 mitigates `backend/.env` only (`slot_env.py` falls back to the main
   checkout's). A worker that runs Vitest or `npm run build` in a fresh
   worktree still has no `web/.env`.
2. **Both review rounds fell back to an inline review** (P8). `ranges` read
   `inline review (… no Agent tool available)`, so the deep
   `/code-review` pass never ran inside `todo-review`. `checklist_skipped` was
   false, so it didn't block anything, but each PR got a shallower review than
   the design assumes. The Part B runbook now lists such PRs in the wrap-up
   (`.claude/skills/completing-todos/SKILL.md`, Stage C step 3). That makes
   the problem visible but doesn't fix it.

## Recommended Action

1. Re-run P5 with the main checkout on a branch that has `.worktreeinclude`
   (main, since #861). If it still delivers nothing, give `slot_env.py` (or a
   worker setup step) the same main-checkout fallback for `web/.env`.
2. Read the workflow authoring docs on which tools a workflow `agent()` gets.
   Either give the review agent the Agent tool so `/code-review` can fan out,
   or run the deep pass from the main session after the workflow and record
   the choice in spec §5.3.

## Acceptance Criteria

- [ ] A fresh `isolation: worktree` checkout has `web/.env`, or a worker's
      Vitest run reads the main checkout's values; the evidence is a quoted run.
- [ ] A `todo-review` round's `ranges` shows the deep review ran (not
      `inline review`), or spec §5.3 records why it runs elsewhere.

## Work Log

### 2026-09-28 - Filed from todo 469 (items 3 and 8)

- Todo 469 closed with Part B. These two items had no criterion there, so they
  move here instead of being lost.

### 2026-09-28 - Item 2: review fan-out moved into the workflow (branch fix/todo-review-full-depth)

- Owner: reviews cannot be shallower than before v2. The pre-v2 engine routed and
  dispatched domain reviewers for every todo; v2 ran one inline bug reviewer, plus
  a route-only orchestrator for sizes m and l.
- `todo-review.js` now does every fan-out as `agent()` calls, for every size: three
  `todo-reviewer` bug lenses, orchestrator Phase 1 routing, then each routed domain
  reviewer, then two refuters per blocking file:line. Any dead reviewer → `rerun`.
  Spec §5.3, §10, §14 and the runbook's Stage C are updated.
- Stub tests and mutations pass. The criterion stays open until a live round-1 run
  shows `route:` and domain-reviewer results in its journal.
- Item 1 (`web/.env`): owner, 2026-09-28: there is no web version of the app yet,
  and no pending todo touches `web/`. Proposed re-point to a new p4 todo; waiting on
  the owner.
