---
status: completed
priority: p4
issue_id: "637"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 2: the apply-triage unblock requires an owner_decision; a plain --reset-stranded keeps the triage class and blocked_on (2026-10-12)"
---

# Follow-ups from PR #1082 (todos 614, 616, todo-sweep runbook)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1082 (todos 614, 616, todo-sweep runbook). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1082 (todo sweep run 2026-10-12-0349, group g12, todos 614, 616); follow-ups: verified.

1. **medium** `.claude/skills/completing-todos/SKILL.md:377` DIRTY step 3 uses one `<path>` placeholder for both `show :2:<path>` (needs the conflicted, archived `completed` path) and `show origin/main:<path>` (pre-archive `pending` path), then defines `<path>` as the pending path. `:2:` at the pending path fails and the unguarded `>` leaves an empty .branch copy, losing ticks. | also: Step 3 uses one placeholder `<path>` for two different paths. `show :2:<path>` needs the conflicted (archived `completed`) path, but the closing 'where `<path>` is ... its pre-archive `pending` path' reads as covering both. `:2:` at the pending path fails and leaves an empty `.branch` copy, so the branch's ticks are lost. | Step 3 uses one `<path>` placeholder for both `show :2:<path>` and `show origin/main:<path>`, then redefines `<path>` as the pre-archive pending path. For an archived todo, :2: lives at the completed path, so an operator who reads it literally gets 'path not in index' for the branch copy. | The DIRTY todo rebuild assumes git saw the archive as a rename, so the conflict and stage :2 sit at the completed path. If rename detection misses (a heavy archive edit), it is a modify/delete at the pending path. Then `show :2:<completed path>` fails and the unguarded `>` leaves an empty .branch file. | The branch-side save (`git show :2:<path> > $TMPDIR/<name>.branch`) has no success check. Only the origin/main show is gated. If `:2:` is absent, an empty .branch file is the 'saved copy' that ticks and Work Log entries get re-applied from, so they are silently dropped.
2. **low** `scripts/todos/state.py:505` The unblock fires for any needs-design/blocked-* todo past triage, including one moved to ready only by `decide ready --reset-stranded` with no --decision. The owner answered the stranded question, not the class one, yet blocked_on is dropped and triage is written ready.
3. **low** `.claude/skills/completing-todos/SKILL.md:402` SKIP_KIMI_REVIEW=1 on the DIRTY merge commit also skips kimi for hunks resolved by hand (todos/ rebuilds, .secrets.baseline line numbers); the rationale covers only what origin/main brought in. Owner-approved; detect-secrets and other hooks still run. | also: Step 6 says to 'record `kimi: skipped`' for the recovery merge commit, but the PR body is already written at this point and no state field or wrap-up line is named. The record has no defined home, so the wrap-up's `kimi: skipped` count can miss it.
4. **low** `scripts/todos/state.py:501` New comment says needs-design and blocked-* leave `triaged` only through `decide … ready`, but `state.py set <id> ready` also does so with no owner_decision. The stated invariant is wrong. The 614 #5 test (stage ready with a decision) also passes on the old code, so it is not a regression test.
5. **low** `.claude/skills/completing-todos/SKILL.md:396` DIRTY step 4 stops the group on any gate failure, but `pre-commit run --files` exits 1 whenever a fixer (trailing-whitespace, end-of-file) rewrites a resolved file, so a fixer-only rewrite disarms and aborts the recovery although step 6 has a fixer path.
6. **low** `todos/archive/614-completed-p4-todo-sweep-triage-guard-1061.md:58` The AC command runs `tests && ...; echo exit=$?; ...; sed`, so it always exits 0, and the quoted evidence tail shows no `exit=` line, so the recorded evidence cannot show the suites passed (616's AC command has the same shape).
7. **low** `todos/archive/616-completed-p4-dirty-armed-pr-recovery-1063.md:56` Work Log ordering is inconsistent: the 'Verified' and 'Completed' entries are dated 2026-10-11 but follow the 2026-10-12 'Implemented' entry of the same run 2026-10-12-0349 (614 has the same problem). Land likely used a stale `$TODAY`.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1082 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g12`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- #1 fixed: DIRTY step 3 in `.claude/skills/completing-todos/SKILL.md` now names two paths, `<branch path>` (the archived `completed` name) and `<main path>` (the `pending` name on origin/main). The branch side is read from `HEAD:<branch path>`, not stage `:2:` (which sits at the `completed` name only when git saw a rename), and must exit 0 and pass `test -s` before anything goes on. #3 fixed: the recovery's kimi skip is recorded with `state.py annotate $RUN G --field kimi_recovery=skipped`, the wrap-up counts it, and step 6 says the skip covers the hand-resolved `todos/` and `.secrets.baseline` hunks. #5 fixed: step 4 stages a fixer-only pre-commit rewrite and runs it again; only a hook that still fails stops the group. New string checks in `scripts/todos/test_state_flow.py`; the 601 and 616 #4 checks that pinned the old `<path>` / `:2:` wording now pin the new wording.
- #2 and #4 fixed per the owner decision: `_triage_fields` in `scripts/todos/state.py` unblocks a `needs-design` / `blocked-*` todo only when it has left triage and has an `owner_decision`. So `decide ready --reset-stranded` with no `--decision`, and a bare `state.py set <id> ready`, keep the triager's class and `blocked_on`, and the comment no longer claims `decide … ready` is the only way out of triage. Two new checks in `scripts/todos/test_state.py` (637 #2, 637 #4), and both fail against the old condition, so they are the regression tests that 614 #5 was not.
- #7 fixed: `land.py` gets `_log_date`, which dates each Verified, Confirmed and Completed entry no earlier than the latest dated heading already in the Work Log, so entries never go backwards in date. The likely cause (hypothesis, not verified) is that `RUN_ID` is `date -u` and `TODAY` is local, so at 03:49 UTC Land's date is still the previous day in the US. New checks in `scripts/todos/test_land.py`; the archive check fails without the fix.
- #6 declined for the archived 614 and 616 records: their evidence files were never committed, so the Work Log quotes cannot be honestly re-recorded, and an archived todo's AC cannot be edited. Fixed going forward in this todo's own evidence command, which saves the suites' exit status, prints `exit=` last and exits with that status.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `bash -c 'W=.; python3 $W/scripts/todos/test_state.py && python3 $W/scripts/todos/test_state_flow.py && python3 $W/scripts/todos/test_land.py && node $W/scripts/todos/test_workflows.js && python3 $W/scripts/todos/test_todofile.py && python3 $W/scripts/test_check_archived_todo_status.py; rc=$?; echo "--- 637 checks:"; python3 $W/scripts/todos/test_state.py | grep 637; python3 $W/scripts/todos/test_state_flow.py | grep -E "637|616 #4|601: ... rebuilding"; python3 $W/scripts/todos/test_land.py | grep 637; echo "--- Work Log entry, one line per finding:"; grep -oE "#[1-7] (and #[1-7] )?(fixed|declined)" $W/todos/637-pending-p4-dirty-runbook-paths-1082.md; echo exit=$rc; exit $rc'` — evidence `.sweep-evidence/g10/637-ac0.txt` (not committed), last lines:

  ```text
  #5 fixed
  #2 and #4 fixed
  #7 fixed
  #6 declined
  exit=0
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
