---
status: completed
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

- [x] The worker's instructions state a summary limit below the schema's
  `maxLength`, and a test pins that the stated limit is smaller.
- [x] A worker that returns nothing leaves its worktree path in the run file,
  and `state.py worktrees` lists it (test with a `worker: null` result).

## Work Log

- 2026-10-04: Filed from the codify pass after runs 2026-10-02-0335 and 2343
  (`docs/LEARNINGS.md` 2026-10-02 entry, PR #959).

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-1537)

- Research: the workflow API's `agent()` has no `cwd` option and reports nothing for a null result, so the
  isolation worktree of a dead worker cannot be recovered. Per the owner's decision, `state.py execute-args` now
  creates each group's worktree (`add_worktrees`: `worktree add --no-track -b` from origin/main under
  `<main-root>/.claude/worktrees/`, `.worktreeinclude` files copied) and records it on the brief and every todo.
- `todo-execute.js` runs the implementer in that worktree without isolation, as a retry already does, and every
  result (a dead worker, or a stage that threw) carries the brief's worktree. `todo-worker.md` implement mode uses
  the given `WORKTREE`. `ingest-execute` fails a worker that reports a different worktree.
- The worker is told: summary at most 400 characters, blockers and discoveries at most 250, in `todo-worker.md`
  and in the implement, retry and repair prompts. A test pins 400 < the WORKER schema's 600 in both workflows.
- SKILL.md: `execute-args` joins the sandbox-off steps, after a `fetch origin main`.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-1537)

- AC 1: `node scripts/todos/test_workflows.js | grep -E '528 AC1|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/528-ac0.txt` (not committed), last lines:

  ```text
    PASS  528 AC1: todo-worker.md and both workflows state a summary limit below WORKER's maxLength
    PASS  528 AC1: ... and that check fails on a stated limit at the maxLength
  All checks passed.
  ```

- AC 2: `python3 scripts/todos/test_state_flow.py | grep -E '528|FAIL|All checks passed' && node scripts/todos/test_workflows.js | grep -E '528 AC2|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/528-ac1.txt` (not committed), last lines:

  ```text
  All checks passed.
    PASS  528 AC2: a worker that returns nothing leaves the brief's worktree on its result
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-1537)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
