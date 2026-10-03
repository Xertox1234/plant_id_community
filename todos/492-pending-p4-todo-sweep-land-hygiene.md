---
status: pending
priority: p4
issue_id: "492"
tags: [harness, todo-sweep]
dependencies: []
triage: needs-design
triaged: 2026-10-02
blocked_on: "Owner picks the AC1 design: tick at Land from owner_decision, or record why it stays manual"
owner_decision: "AC1: land.py ticks an owner-only criterion from a dated owner_decision, quoting it into the Work Log, with the CI tripwire accepting that marker (2026-10-02); the AC4 sub-question (does todo-worker.md naming MAIN/backend/venv count as an explicit env root) was not put to the owner: the worker records its reading"
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

- [ ] An owner-only criterion with a dated owner confirmation in `owner_decision` can be closed at
      Land, with the confirmation quoted into the Work Log, and CI's archived-todo tripwire
      accepts it. Or this todo records why it must stay manual.
- [ ] Worker Work Log entries record commands relative to the repo root, with a check that fails
      on an absolute home path.
- [ ] `flip-acs` and `archive` leave no trailing whitespace, with a test.
- [ ] The env root for workers is explicit, not discovered by fallback.

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
