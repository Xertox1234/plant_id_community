---
status: pending
priority: p4
issue_id: "492"
tags: [harness, todo-sweep]
dependencies: []
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
