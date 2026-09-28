---
status: completed
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

- [ ] `web/.env` in worker worktrees → todo 479 (re-pointed 2026-09-28; owner: no web version yet)
- [x] A `todo-review` round's `ranges` shows the deep review ran (not
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
  and no pending todo touches `web/`. The owner approved the move: re-pointed to
  todo 479 (p4). Its box stays open per the tracking convention.

### 2026-09-28 - Item 2 verified live; archived (PR #873)

- Live `todo-review` round 2 against PR #873's worktree (run `wf_c08058cf-f8f`,
  5 agents, 0 errors). `ranges`: `git diff origin/main...HEAD (correctness)`,
  `(security-data)`, `(contracts-tests)`, `(cross-cutting-reviewer)`, none inline.
  `routed: [cross-cutting-reviewer]`, `routing_gaps: []`, `reviewers_ok: true`,
  19 findings (8 medium, 11 low), none blocking. The orchestrator returned ROUTING
  through the schema, and the routed domain reviewer returned FINDINGS through it.
- The first live run (`wf_25180f55-a2f`) had the same routing. There,
  `cross-cutting-reviewer` died on the 300-char `summary` cap after 5 retries, and the
  round correctly came back `reviewers_ok: false`. Fixed in 51a3c7bf (600-char
  headroom, prompt asks for under 300). REFUTATION got the same fix.
- Git guard: in the first run, reviewers made 69 Bash calls. There was one denial,
  `git ls-tree` for a bug lens, which is already todo 477 finding 3.
- Not proven: this run's "worktree" was the session's own checkout, so it can't
  show that domain reviewers stay out of the main checkout. The first real sweep will.
- Item 1 re-pointed to todo 479. Non-blocking findings → todo 478.
