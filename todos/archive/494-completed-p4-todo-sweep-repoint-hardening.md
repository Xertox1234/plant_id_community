---
status: completed
priority: p4
issue_id: "494"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Finding 14: document the dead-verifier re-verify case in the runbook only; no new --reverify path (2026-10-02)"
---

# Todo sweep: harden owner re-points and the verify-only reopen

## Problem

PR #885 (todo 492) added `state.py repoint` and `set … ready --reverify`. Its reviews fixed the
blocking findings, and round 2 narrowed re-verify to one-todo attempts. The non-blocking findings are
collected here.

## Findings

1. **The re-point rule is enforced only in the verifier's prompt.** Verifier step 4 accepts a criterion
   whose only change is a marker listed on the `REPOINTS:` line. Nothing in code checks it. The archive
   tripwire (`scripts/check_archived_todo_status.py`) accepts any re-point marker on an unchecked box,
   whether or not it was authorized. `state.py` already has `todofile.ac_lines` and each entry's
   `repoints`. It could compare the merge-base and current criteria in `ingest_execute` and in the review
   ingest, allowing only the listed markers.
2. **Stale re-points reach a fresh attempt.** `transition` moves failed → ready without moving
   `repoints`, so a fresh worker's brief lists a re-point whose target file existed only in the
   abandoned worktree. Move `repoints` to `previous` on that edge, or list re-points only in a re-verify
   brief and the review of its PR.
3. **`repoint` accepts any `ready` todo,** including a failed → ready retry that still has its old
   worktree recorded. It then stages the marker in that dead worktree. Require `blocked`, or `ready`
   with `reverify`.
4. **`--date` goes into the marker unvalidated.** A quote, `;` or newline would break the `REPOINTS:`
   line. Only the main session sets it, so this is hardening. Validate `YYYY-MM-DD`, and quote the
   marker with `JSON.stringify` in both workflows.
5. **Re-running `repoint` on another day is refused** as "re-pointed elsewhere", because the marker
   contains the date. Compare only `→ todo NNN`.
6. **Verifier step 4 wording.** Say that `#<index>` is 0-based (the same `index` as AC_FILE), and that
   exactly one occurrence of the marker is removed; a second occurrence is an edit.
7. **Fixed in PR #885:** `--reverify` now needs `blocked_by: worker`, which `ingest_execute` records
   only for a first worker's block.
8. **The `todo-execute` pipeline stage is synchronous on the re-verify path**
   (`b.reverify ? reverifyWorker(b) : agent(…)`). Make it `async`, so a runtime that chains with `.then`
   still gets the record.
9. **The staged tree is taken as it is at `execute-args`.** Anything staged between the block and
   then becomes the verified tree, not only the re-point and its target (a broad `git add -A` would
   stage a stray scratch file). Require `git diff-tree` between the recorded and new trees to touch
   only the todo file and each re-point's target.
10. **Error text.**
    - `repoint` on a todo whose file Land already moved raises `FileNotFoundError`, not a
      `TransitionError` naming the problem.
    - A re-verify wave that clashes with a `failed` group in the wave before gets "wait for that wave
      to merge". That group never merges until it is retried or blocked, so say so.
11. **`--reverify` can still re-judge a rejected tree (medium, round 2 of the second cycle).** The
    failed → ready retry keeps the rejected attempt's work fields. If its fresh worker then blocks with
    empty `worktree`/`tree_id` strings, `ingest_execute` keeps the old ones and records
    `blocked_by: worker`, so `--reverify` re-judges the rejected tree after the retry was spent.
    Require `attempts == 0` in `reopen_reverify`, and move the work fields and `repoints` to `previous`
    on the failed → ready edge (which also closes finding 2).
12. **Runs written before PR #885 have no `blocked_by`,** so `--reverify` refuses a todo whose first
    worker did block it (todo 423 in run 2026-09-28-2018). Document the one-time backfill,
    `state.py annotate $RUN <group> --field blocked_by=worker`, allowed only for attempts 0, no
    verdict, and a reason that is the worker's blockers.
13. **More error text.**
    - `_refuse_shared_worktree` says "reopen it without --reverify" when `execute-args` raises it. By
      then the todo is `ready`, so the recovery is to block it, then reopen it.
    - `execute-args` on a re-verify whose worktree has vanished fails inside `git write-tree`. Check
      the directory first and name the recovery.
14. **A dead verifier strands a re-verify.** Two null verdicts make the todo `failed` ("no verdict").
    It can then never be re-verified, although no verifier judged its tree. Allow that case, or say
    so in the runbook.
15. **`review_args` takes `evidence_dir` from `ac_file` for every group.** An absolute or bare
    `ac_file` from a worker turns the repair worker's `EVIDENCE_DIR` into an absolute path or the
    worktree root. Use `dirname(ac_file)` only when it is relative and under `.sweep-evidence/`.
16. **Two unmerged PRs can pick the same re-point target number** (a second re-verify, or the
    closing follow-ups PR). `repoint` checks only origin/main and HEAD. Also refuse a number another
    todo in the run already uses as a target.
17. **Tests.**
    - Nothing checks the record `reverifyWorker` builds against the WORKER schema. A missing `branch`
      would make `ingest_execute` raise a KeyError.
    - The non-numeric target check (`to="../8"`) would pass without the `isdigit` guard, because the
      glob refuses it too. Use a target like `8a` with a staged `8a-*.md` file.
    - The "missing WORK_FIELDS" refusal in `reopen_reverify` is never exercised.
    - No test calls `repoint` on a `ready` todo, so narrowing its stage check (finding 3) is unpinned
      either way.
    - Nothing drives the CLI `set --reverify` argument check or the `repoint` subcommand through
      `state.main`.
    - `busy_lanes=again_lanes[-1]` in `apply_grouping` is unpinned (it fails safe: a clash waits).
    - `repoint`'s index-bounds check and a duplicate `ac.json` entry are caught only by a crash.

## Acceptance Criteria

- [x] Findings 1–6, 8–10 and 11–16 are fixed, or each has a line in this todo saying why not.
- [x] Each gap in finding 17 has a test that fails when the guard it names is removed.

## Work Log

### 2026-09-28 - Filed from PR #885 review rounds 1 and 2

Findings 11–16 come from round 2 of the second review cycle, which never repairs.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-1537)

- Fixed in `scripts/todos/state.py`: F1 (`criteria_problem`/`git_criteria`, run by `ingest-execute` and on a kept
  round-1 repair by `ingest-review`; only a listed marker, removed once, is allowed), F2+F11 (failed → ready moves
  the attempt, re-points included, to `previous`; `reopen_reverify` needs `attempts == 0`), F3, F4 (`--date` must be
  a real YYYY-MM-DD; both workflows `JSON.stringify` the marker), F5 (compare `→ todo NNN`, keep the earlier
  marker), F8 (async stage), F9 (`diff-tree` may touch only the todo and each target), F10, F13, F15, F16. F6 is in
  `todo-verifier.md` step 4.
- Left as is, with why: F1's archive-tripwire half — `check_archived_todo_status.py` cannot know which marker the
  owner authorized; the ingest checks now refuse an unlisted one before Land. F12 and F14 — runbook only, per the
  owner's decision (SKILL.md Stage B step 5: the one-time `blocked_by=worker` backfill, and the dead-verifier case).
- F17: every gap has a test in `test_state_flow.py` (`hardening_494_tests`) or `test_workflows.js`, each run once
  against `state.py` and once against a copy with its guard removed (`mutant`/`both`, the JS `mutate`).
- Existing tests changed: the 492 re-point test unstages its stray todo 9 (the F9 guard now refuses it), and
  `reverify_grouping_tests`' fake git answers `diff-tree` with nothing.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-1537)

- AC 1: `python3 scripts/todos/test_state_flow.py | grep -E '494 F|FAIL|All checks passed' && node scripts/todos/test_workflows.js | grep -E '494 F|FAIL|All checks passed' && sed -n '/2026-10-10 - Implemented by the todo sweep/,$p' todos/archive/494-completed-p4-todo-sweep-repoint-hardening.md` — evidence `.sweep-evidence/g1/494-ac0.txt` (not committed), last lines:

  ```text
    against `state.py` and once against a copy with its guard removed (`mutant`/`both`, the JS `mutate`).
  - Existing tests changed: the 492 re-point test unstages its stray todo 9 (the F9 guard now refuses it), and
    `reverify_grouping_tests`' fake git answers `diff-tree` with nothing.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

- AC 2: `python3 scripts/todos/test_state_flow.py | grep -E '494 F17|494 F11/F17|494 F3/F17|FAIL|All checks passed' && node scripts/todos/test_workflows.js | grep -E '494 F17|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/494-ac1.txt` (not committed), last lines:

  ```text
    PASS  494 F17: reverifyWorker's record matches the WORKER schema
    PASS  494 F17: ... and that check fails when the record loses the brief's fields (no branch)
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-1537)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
