---
status: pending
priority: p4
issue_id: "479"
tags: [harness, todo-sweep, web]
dependencies: []
triage: blocked-owner
triaged: 2026-09-28
blocked_on: "A pending todo that touches web/, which the owner says starts the work. Then re-run pilot check P5 with the main checkout on main."
owner_decision: "Re-run pilot check P5 now; .worktreeinclude on main already lists web/.env (2026-09-28)"
---

# Todo sweep: `web/.env` in worker worktrees, once web work starts

## Problem

A todo-sweep worker runs in a fresh `isolation: worktree` checkout. In the Task 14
pilot, `.worktreeinclude` delivered nothing to either checkout (P5 FAIL). #864 fixed
this for `backend/.env` only: `slot_env.py` falls back to the main checkout's copy.
Nothing does the same for `web/.env`, so a worker that runs Vitest or `npm run build`
in a fresh worktree has no web environment.

Owner, 2026-09-28: there is no web version of the app yet, and no pending todo
touches `web/`. So this does not block any sweep today. Moved here from todo 472
item 1, so it is not lost.

## Findings

- Hypothesis, not verified: the harness reads `.worktreeinclude` from the main
  checkout, and that checkout's branch had no `.worktreeinclude` at the pilot.
  `.worktreeinclude` has been on main since #861.
- `web/` reads `import.meta.env` in 9 files under `web/src/`. The main checkout's
  `web/.env` is 63 bytes.

## Recommended Action

Do this once a todo touches `web/`:

1. Re-run pilot check P5 with the main checkout on main. If `.worktreeinclude` now
   delivers `web/.env`, record that and close this todo.
2. If not, give `slot_env.py`, or a worker setup step, the same main-checkout
   fallback for `web/.env` that #864 gave `backend/.env`.

## Acceptance Criteria

- [ ] A fresh `isolation: worktree` checkout has `web/.env`, or a worker's
      Vitest run reads the main checkout's values; the evidence is a quoted run.

## Work Log

### 2026-09-28 - Moved from todo 472 item 1

- The owner confirmed there is no web product yet, so this stays at p4 until web
  work starts.
