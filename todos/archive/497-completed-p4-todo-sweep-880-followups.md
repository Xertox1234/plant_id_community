---
status: completed
priority: p4
issue_id: "497"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Finding 4: add a new owner-gated state.py command (like clear-hold/hand-round) that releases a group blocked by two incomplete review rounds back to pr_open for one more round (2026-10-10)"
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

- [x] Findings 1–9 are fixed, or each has a line in this todo saying why not.
- [x] Findings 1, 3, 6 and 8 each have a test that fails when the fix is removed.

## Resolution

Run 2026-10-10-2307 fixed all nine; each test below lives in `scripts/todos/test_state_flow.py` unless named.

1. Fixed: a cleared critical is matched at its location and, when a repair moved it, at another line of the
   same file whose phrasings the owner all cleared (fails closed only on a new phrasing). A phrasing a cleared
   location gains is not held but is named in the refuted comment and any hold or block reason. Tests run
   against a copy with each guard removed (`497 F1`).
2. Fixed: phrasings are kept as a list (`refuted_phrasings`, `hold_cleared_phrasings`); the rendered line is
   unchanged. Test `497 F2`.
3. Fixed: `ingest-review` passes its output file as the source, and an incomplete outcome already counted for
   that file is not counted again. Test `497 F3` (with the guard removed it blocks); todo-resume says so.
4. Fixed (owner decision): `state.py release-incomplete RUN G --decision ...`, owner-gated and once per round,
   sends the group back to `pr_open` with the count reset. Documented in completing-todos and todo-resume.
5. Fixed: the failed-repair message says the criticals hold at the next round (`clear-hold` cannot clear them
   from that block), and `refuted-comment` marks a cleared line `(cleared by the owner)`.
6. Fixed: `todo-execute.js` skips the worker retry when ANY reason starts with the dirty-tree text. Tests in
   `scripts/todos/test_workflows.js` (`497 F6`, one against the old every-reason check).
7. Fixed: the worker's and the verifier's clean checks use `--untracked-files=all` (pinned in
   `test_workflows.js`).
8. Fixed: `slot_env.web_env` keeps only `VITE_*` keys and warns instead of raising on an unreadable file. Tests
   in `scripts/todos/test_slot_env.py`, each also run against a copy without the fix.
9. Fixed: tests for a residue outcome setting `review_reruns`, and residue then a rerun blocking (`497 F9`).

## Work Log

### 2026-09-29 - Filed from PR #880 review rounds 2 and 3

Round 2 never repairs, and round 3 (the owner's call) did not either. All were rated non-blocking.
Finding 7 was first reported in round 2's wrap-up but never written to the run file; round 3 re-found
it.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-2307)

- Reworked the cleared-critical key, stored phrasings as lists, made an incomplete round count once per output
  file, and added the owner-gated `state.py release-incomplete`.
- Fixed the two owner-facing messages, the dirty-tree retry check, the clean checks' untracked listing and
  `slot_env.web_env`.
- Each of findings 1, 3, 6 and 8 has a test that also runs against a copy with its fix removed.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-2307)

- AC 1: `bash -c 'set -eo pipefail; cd . && sed -n "/^## Resolution/,/^## Work Log/p" todos/archive/497-completed-p4-todo-sweep-880-followups.md; python3 scripts/todos/test_state_flow.py | grep -E "497|All checks passed|FAIL"; node scripts/todos/test_workflows.js | grep -E "497|All checks passed|FAIL"; python3 scripts/todos/test_slot_env.py | grep -E "497|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/497-ac0.txt` (not committed), last lines:

  ```text
    PASS  497 F8: web_env keeps only VITE_* keys -- and fails with the fix removed
    PASS  497 F8: an unreadable web/.env inherits nothing instead of raising
    PASS  497 F8: an unreadable web/.env inherits nothing instead of raising -- and fails with the fix removed
    PASS  497 F8: ... and slot_env still runs the command, with a warning
  All checks passed.
  ```

- AC 2: `bash -c 'set -eo pipefail; cd . && python3 scripts/todos/test_state_flow.py | grep -E "497 F(1|3)|All checks passed|FAIL"; node scripts/todos/test_workflows.js | grep -E "497 F6|All checks passed|FAIL"; python3 scripts/todos/test_slot_env.py | grep -E "497 F8|All checks passed|FAIL"'` — evidence `.sweep-evidence/g4/497-ac1.txt` (not committed), last lines:

  ```text
    PASS  497 F8: web_env keeps only VITE_* keys -- and fails with the fix removed
    PASS  497 F8: an unreadable web/.env inherits nothing instead of raising
    PASS  497 F8: an unreadable web/.env inherits nothing instead of raising -- and fails with the fix removed
    PASS  497 F8: ... and slot_env still runs the command, with a warning
  All checks passed.
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-2307)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
