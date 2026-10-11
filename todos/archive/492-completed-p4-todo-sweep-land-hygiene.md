---
status: completed
priority: p4
issue_id: "492"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-10
blocked_on: "Owner picks the AC1 design: tick at Land from owner_decision, or record why it stays manual"
owner_decision: "AC2: add a refusing check - Land and CI refuse an archived todo whose Work Log still holds /Users/ or /home/; the _relativize scrub alone does not meet AC2 (2026-10-10)"
---

# Todo sweep: owner-confirmed criteria, absolute paths in Work Logs, and land-time whitespace

## Problem

Three engine gaps showed up in sweep run 2026-09-28-2018.

## Findings

1. **An owner confirmation cannot close a criterion.** 364 and 437 each had one criterion that
   only the owner could check (a prod email arrived, a raw header is present). The owner
   confirmed both in the Decide step, and the confirmation was recorded in `owner_decision`.
   `land.py flip-acs` flips only with a worker pass, verifier agreement and an evidence file, so
   both todos came back `blocked` and needed a manual close. 423 has the same shape: an on-device
   walkthrough.
2. **Work Logs commit absolute local paths.** Workers record commands and evidence as
   `/Users/<name>/projects/…/.claude/worktrees/wf_…` and main-checkout venv paths. The worktree
   is deleted after landing, so the commands can't be re-run, and the repo is public (home
   username and layout). PR #877 and #879 reviews both flagged it (447, 464).
3. **Every archive fails trailing-whitespace on the first commit.** `land.py flip-acs` or
   `archive` leaves trailing whitespace in the todo file, so each Land commit needs a
   re-stage-and-retry.
4. **The pilot checkout has no `backend/venv` or `web/node_modules`.** Every worker and verifier
   fell back to the main checkout's copies, and built a symlink farm under `WT/web/node_modules`
   so Vite could write `.vite-temp`. `slot_env.py` or the brief should name the env root
   explicitly.

## Acceptance Criteria

- [x] An owner-only criterion with a dated owner confirmation in `owner_decision` can be closed at
      Land, with the confirmation quoted into the Work Log, and CI's archived-todo tripwire
      accepts it. Or this todo records why it must stay manual.
- [x] Worker Work Log entries record commands relative to the repo root, with a check that fails
      on an absolute home path.
- [x] `flip-acs` and `archive` leave no trailing whitespace, with a test.
- [x] The env root for workers is explicit, not discovered by fallback.

## Resolution

Run 2026-10-10-2307 (owner decisions 2026-10-10 for AC1 and AC2):

- AC1, finding 1: `state.py confirm RUN ID --index I --decision ... --date D` records the owner's dated
  confirmation on the run entry (`confirmed`) and appends it to `owner_decision`. execute-args and review-args
  brief it, both workflows send a `CONFIRMED:` line, the worker records the criterion `owner-confirmed`
  instead of blocking, the verifier accepts only listed ones, and `land.py flip-acs` ticks the box and quotes
  the owner's words under their own Work Log heading. The archived box is `[x]`, so the tripwire accepts it.
- AC2, finding 2: todo-worker.md says Work Log paths are repo-relative. The refusing check is
  `check_archived_todo_status.py`'s new ARCHIVED_HOME_PATH rule (the `## Work Log` section of an archived
  todo, a home directory where a path starts) with its own grandfather list (38 files that predate it), and
  `land.py archive` refuses such a todo in phase 1.
- AC3, finding 3: already done by todo 512 (`_fence_quote`); `test_land.py` pins flip-acs and archive, and the
  new owner-confirmed path is checked for trailing whitespace too.
- AC4, finding 4: `slot_env.py --main-root MAIN` names the env root explicitly; the worker and verifier
  instructions pass it, and the brief's `main_root` is now absolute.

## Work Log

### 2026-09-28 - Filed from todo sweep run 2026-09-28-2018 (Land and review steps)

### 2026-09-28 - Slice: owner re-points and verify-only reopen (for todo 423)

- 423's worker stopped on an owner-only criterion, the on-device walkthrough. It left finished,
  staged work and no verdict. The owner moved the walkthrough to a follow-up todo to do after deploy.
  Two gaps kept 423 from landing through the engine: reopening it started a fresh worker in a new
  worktree, and the verifier read the added re-point marker as an edited criterion.
- `state.py repoint` records an owner-authorized re-point mid-run. It adds the marker on the checkbox
  line, stages it, syncs `ac.json`, and records it on the run entry. `execute-args` and `review-args`
  pass the list, and the verifier accepts only listed markers (step 4).
- `state.py set … ready --reverify` reopens a blocked todo with its staged worktree kept. The
  `todo-execute` workflow skips the planner and the worker and runs only the verifier on it.
- This slice closes none of the criteria above. Owner-confirmed criteria (364 and 437) need ticks,
  not re-points, and are still finding 1.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-2307)

- Added `state.py confirm` and the `CONFIRMED` plumbing through both workflows, the worker and verifier
  instructions and `land.py flip-acs`, so an owner-confirmed criterion is ticked at Land with its quote.
- Added the Work Log home-path rule to the archived-todo tripwire (separate pass and grandfather list) and a
  phase-1 refusal in `land.py archive`; worker instructions now ask for repo-relative paths.
- Added `--main-root` to `scripts/todos/slot_env.py` and named it in the worker and verifier toolchains.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-2307)

- AC 1: `bash -c 'set -eo pipefail; cd . && python3 scripts/todos/test_land.py | grep -E "492 AC1|All checks passed|FAIL"; python3 scripts/todos/test_state_flow.py | grep -E "492 AC1|All checks passed|FAIL"; node scripts/todos/test_workflows.js | grep -E "492 AC1|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/492-ac0.txt` (not committed), last lines:

  ```text
    PASS  492 AC1 / 541 #982-12: after Land, an owner-confirmed box may be ticked though the verifier's list does not verify it
  All checks passed.
    PASS  492 AC1: the CONFIRMED line reaches the execute verifier, the review verifier and the repair worker
    PASS  492 AC1: no CONFIRMED line without a confirmation
  All checks passed.
  ```

- AC 2: `bash -c 'set -eo pipefail; cd . && grep -n "never under" .claude/agents/todo-worker.md; python3 scripts/test_check_archived_todo_status.py | grep -E "492 AC2|All checks passed|FAIL"; python3 scripts/todos/test_land.py | grep -E "492 AC2|All checks passed|FAIL"; python3 scripts/check_archived_todo_status.py --fail-over 0'` — evidence `.sweep-evidence/g4/492-ac1.txt` (not committed), last lines:

  ```text
  ARCHIVED_HOME_PATH        38          0
  TOTAL                    100          0
  62 grandfathered for unchecked acceptance criteria
  38 grandfathered for a home path in the Work Log
  6 file(s) skipped: no frontmatter block, cannot be judged
  ```

- AC 3: `bash -c 'set -eo pipefail; cd . && python3 scripts/todos/test_land.py | grep -E "512|492 AC1: the archived|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/492-ac2.txt` (not committed), last lines:

  ```text
    PASS  512: no line of the todo ends in whitespace after flip-acs
    PASS  512: ... nor after archive
    PASS  512: the archived file still passes the CI tripwire
    PASS  492 AC1: the archived file passes the CI tripwire (no bare box) and has no trailing whitespace
  All checks passed.
  ```

- AC 4: `bash -c 'set -eo pipefail; cd . && grep -n -- "--main-root MAIN" .claude/agents/todo-worker.md .claude/agents/todo-verifier.md; python3 scripts/todos/test_slot_env.py | grep -E "492 AC4|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/492-ac3.txt` (not committed), last lines:

  ```text
    PASS  492 AC4: --main-root names the checkout whose .env a worktree without its own inherits
    PASS  492 AC4: ... in either flag order
    PASS  492 AC4: without --main-root the discovered main checkout is used, as before
    PASS  492 AC4: a --main-root naming no directory exits 2
  All checks passed.
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-2307)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
