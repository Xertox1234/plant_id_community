---
status: pending
priority: p4
issue_id: "528"
tags: [todo-sweep, engine]
dependencies: []
triage: needs-research
triaged: 2026-10-10
blocked_on: "Find out whether the workflow runtime's agent() reports the isolation worktree path when it returns null. If not, pick a fallback such as scanning git worktree list."
owner_decision: "If agent() cannot report a dead worker's worktree path, the workflow creates the worktree itself and passes the path in, so it is always known (2026-10-10)"
---

# Sweep worker loses finished work when its summary overruns an unstated 600-character cap

## Problem

The `todo-execute` workflow's WORKER schema caps `summary` at 600 characters
(`.claude/workflows/todo-execute.js:27`). The worker is never told that limit:
`.claude/agents/todo-worker.md:116` lists `summary` among the fields to return,
with no length. Reviewer prompts state 300 and keep the schema at 600 as
headroom (`todo-review.js:31`); the worker gets no such margin.

In run 2026-10-02-0335 the first worker for todo 518 finished its work, staged
it, overran the cap by four characters and returned nothing. The workflow then
records the group with `worker: null` and `worktree: null`
(`todo-execute.js:161-162`), so:

- the group fails and needs a full retry (a new worker in a new worktree);
- the dead attempt's worktree (`.claude/worktrees/wf_78c1dc6c-a09-2`, 12 changed
  paths) is recorded nowhere in the run file, so `state.py worktrees` cannot
  list it for cleanup.

## Proposed fix

1. State the limit in the worker's instructions with headroom, as the reviewer
   prompts do (for example "summary: at most 400 characters"), in
   `todo-worker.md` and in the implement prompt `todo-execute.js` builds.
2. When a worker returns nothing, keep the worktree path the workflow created
   for it on the result, so `ingest-execute` records it under the group and
   `state.py worktrees` lists it.

## Acceptance Criteria

- [ ] The worker's instructions state a summary limit below the schema's
  `maxLength`, and a test pins that the stated limit is smaller.
- [ ] A worker that returns nothing leaves its worktree path in the run file,
  and `state.py worktrees` lists it (test with a `worker: null` result).

## Work Log

- 2026-10-04: Filed from the codify pass after runs 2026-10-02-0335 and 2343
  (`docs/LEARNINGS.md` 2026-10-02 entry, PR #959).
