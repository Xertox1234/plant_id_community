---
status: completed
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

- [x] A fresh `isolation: worktree` checkout has `web/.env`, or a worker's
      Vitest run reads the main checkout's values; the evidence is a quoted run.

## Work Log

### 2026-09-28 - Moved from todo 472 item 1

- The owner confirmed there is no web product yet, so this stays at p4 until web
  work starts.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Pilot check P5 re-run in this run's own fresh `isolation: worktree` checkout: FAIL again, neither
  `web/.env` nor `backend/.env` arrived. The cause, now verified, not a hypothesis: the harness reads
  `.worktreeinclude` from ITS main checkout, `/Users/williamtower/projects/plant_id_community`, which is on
  branch `docs/kimi-review-tooling-plan` and has no `.worktreeinclude`. The sweep's own main root (the pilot
  checkout) is not the one the harness copies from, so main having the file is not enough.
- So step 2 of the Recommended Action: `slot_env.py` now also passes the main checkout's `web/.env` values
  as process environment when the worktree has none (Vite reads `VITE_*` from the environment first), and
  `todo-worker.md` says to run `npm run …` through `slot_env.py` in that case. Tests in `test_slot_env.py`.
- Evidence: `scripts/todos/web_env_probe.sh` runs a real Vitest test from the worktree's web toolchain
  with the env dir set to `WT/web`. Without slot_env it sees no `VITE_*` key and fails; through slot_env it
  sees `VITE_API_URL`, equal to the main checkout's value, and passes. It prints key names only.
- Found on the way: the pilot main root has no `web/node_modules`, so the worker doc's
  `ln -sfn MAIN/web/node_modules …` has nothing to link there (the probe used the harness checkout's), and
  bundling a TS Vite config writes into `node_modules/.vite-temp`, which the sandbox denies through that link.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `bash /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/web_env_probe.sh /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3 6` — evidence `.sweep-evidence/g8/479-ac0.txt`, last lines:

  ```text
  VITE keys seen by Vitest: VITE_API_URL
  VITE_API_URL matches the main checkout's web/.env: true
   ✓ env.test.ts > a worker Vitest run reads web env values 1ms
   Test Files  1 passed (1)
        Tests  1 passed (1)
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
