---
status: pending
priority: p4
issue_id: "497"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: non-blocking follow-ups from PR #880

## Problem

PR #880 (todos 473–484) went through three review rounds. The third, owner-approved, came after the
round-2 blocker was fixed in 793d29a5: a cleared critical held again when round 2 reworded it. The git-guard
findings are todo 496. The rest are here.

## Findings

Line numbers are as of PR #880's merge (fd7305de).

1. **The location-keyed hold clear trades one miss for two others** (`scripts/todos/state.py:884`–`889`,
   793d29a5). `_open_criticals` now compares `severity: file:line`, so a cleared critical re-reported in
   other words does not hold again. Round 3 found both edges of that key:
   - **It fails open.** A *different* critical that both refuters dismiss at the same severity, file and
     line merges into the cleared line's `also` and never holds. That breaks "a refutation alone never
     clears a critical" and `clear_hold`'s own "a new one in round 2 holds again". (Reported twice.)
   - **It fails closed.** A round-1 repair committed after `clear-hold` can shift lines. Round 2 then
     reports the same critical at `d.py:6`, not `d.py:4`, and it holds again.

   Suggested: keep the cleared phrasings per location. Skip the hold when a cleared location only gains
   a phrasing, but name the new phrasing in the outcome reason and the refuted comment. Add tests for a
   distinct critical at a cleared location and for a line moved by the repair.
2. **`_merge_refuted` splits `also` on `" | "`** (`state.py:955`). A phrasing that contains `" | "`
   breaks into pieces, is never found again, and is appended again each round. Keep the phrasings as a
   list in the run file and render the line only for output. (low)
3. **`ingest-review` is not idempotent for an incomplete round** (`state.py:999`, `_incomplete`).
   todo-resume re-ingests round-1 output that was "never ingested", and the stage check still passes at
   `pr_open`. So re-ingesting one rerun or residue output raises `review_reruns` to 2 and blocks the
   group after one real incomplete round. Record which output was counted, or have todo-resume check
   `review_reruns` first.
4. **A group blocked by two incomplete rounds has no documented exit** (`state.py:1004`). It has a PR,
   so `_reopen` refuses it, and `clear-hold` refuses it because the reason is not a hold. Document the
   recovery in completing-todos and todo-resume, or add a `state.py` command for it. (low)
5. **Two messages point the owner the wrong way** (`state.py:1084`). A failed round-1 repair with
   criticals says "which the owner must clear", but `clear-hold` refuses that reason. `refuted_comment`
   says "holds the PR until the owner clears it" even for lines already in `hold_cleared`; mark those
   "cleared by the owner". (low)
6. **`dirtyOnly` needs every reason to start with the dirty-tree text**
   (`.claude/workflows/todo-execute.js:120`). A re-run verifier that lists the dirty paths as separate
   `reasons` entries, or adds any other reason, makes the check false. The worker retry then runs on the
   dead verifier's leftovers, which todo 476 exists to prevent.
7. **The clean checks fold untracked directories** (`.claude/agents/todo-verifier.md:24`–`26`, and
   `todo-worker.md` Finish step 2). Bare `git status --porcelain` prints a new directory as one `?? dir/`
   line. `UNTRACKED_BEFORE` comes from `--untracked-files=all` and lists files. So a pre-round untracked
   directory fails spuriously, and a repair's new file inside it hides behind the same line. Use
   `--untracked-files=all` in step 1 and step 6, and in the worker's Finish check.
8. **`slot_env.web_env`** (`scripts/todos/slot_env.py:85`–`91`):
   - It reads `MAIN/web/.env` inside a `try` that catches only `CalledProcessError`, so an unreadable
     file raises a traceback.
   - It exports every `web/.env` key, not only `VITE_*`, into every `slot_env` command, backend pytest
     included. python-decouple reads `os.environ` before `backend/.env`, so a key with the same name
     overrides the worktree's backend value. Keep only `VITE_*`.
9. **No test covers residue in the two-strike counter** (`scripts/todos/test_state_flow.py:1462`). Every
   counter test uses a rerun. Assert that a residue outcome sets `review_reruns`, and that residue then a
   rerun in one round blocks. (low)

## Acceptance Criteria

- [ ] Findings 1–9 are fixed, or each has a line in this todo saying why not.
- [ ] Findings 1, 3, 6 and 8 each have a test that fails when the fix is removed.

## Work Log

### 2026-09-29 - Filed from PR #880 review rounds 2 and 3

Round 2 never repairs, and round 3 (the owner's call) did not either. All were rated non-blocking.
Finding 7 was first reported in round 2's wrap-up but never written to the run file; round 3 re-found
it.
