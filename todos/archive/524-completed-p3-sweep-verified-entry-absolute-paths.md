---
status: completed
priority: p3
issue_id: "524"
tags: [tooling, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Rewrite worktree/main-checkout prefixes to repo-relative in both the quoted command and the evidence tail; keep the .sweep-evidence pointer but label it '(not committed)'; do NOT backfill the ~102 already-archived lines (2026-10-01)"
---

# Todo sweep: archived Verified entries carry absolute worktree paths

## Problem

Todo-sweep run 2026-10-02-0118 merged todos 502–511 (#927–#935). Three of those todos (503, 509, 511)
existed only to rewrite absolute worktree paths out of earlier archived Work Logs. Then the same
run's own Land wrote new ones. Reviewers flagged it on #928, #933, #934 and #935, so it will come
back as follow-up findings on every run until it is fixed at the source.

## Findings

1. **`land.py flip_acs` quotes the worker's command verbatim** (`scripts/todos/land.py:248`).
   `todo-worker.md` (step 1, `Use absolute paths`) makes every evidence command absolute, so the
   archived `Verified by the todo sweep` entry records
   `/Users/<name>/projects/plant_id_community/.claude/worktrees/wf_…/…`. That path is gone once the
   worktree is removed, and it puts the local username into a public repo. 102 lines in 36 archived
   files already carry a worktree path (counted at origin/main before #933–#935 merged).
   Fix: in `flip_acs`, rewrite a leading `<repo>/` and `<main_root>/` in the command to repo-relative
   (or `$WT/`, `$MAIN/`) before `_sanitize`, with a test. Decide whether the existing ones are
   worth a one-off rewrite.
2. **The quoted command names the pre-archive todo path.** An AC check that greps
   `todos/NNN-pending-….md` is archived by the same Land, so the recorded command can't be re-run
   (#933, #934). Fix: when quoting, rewrite the todo's own origin path to its archived path, or
   note in the entry that paths are as of verification.
3. **The `evidence .sweep-evidence/…` pointer names a gitignored file** that is deleted with the
   worktree. The quoted tail is the durable record, so either drop the pointer or label it
   "(not committed)".
4. **`todos/archive/086-skipped-p3-drop-orphan-forum-tables.md` has merge-conflict markers**
   (4 marker lines) and two `status:` lines. Found by the 506 worker. Since #931,
   `todofile.field_problem` refuses it, so any tool that rewrites 086 will now stop. Fix by hand:
   resolve the conflict and keep one `status:`.

## Acceptance Criteria

- [x] Findings 1–3 are fixed in `land.py` (or the worker/verifier contract) with tests, so a Land's
      Verified entry has no `/Users/` and no worktree name.
- [x] Finding 4: 086 has no conflict markers and one `status:` line, and
      `scripts/check_archived_todo_status.py` still passes.

## Work Log

- 2026-10-01: Filed from the main session of todo-sweep run 2026-10-02-0118.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0255)

- `land.py` gained `_relativize`: `flip_acs` now strips `<repo>/`, any `.../.claude/worktrees/<name>/` and
  `<main_root>/` (written and resolved forms, worktree before main_root since it nests under it) from the quoted
  command and every quoted evidence-tail line, and rewrites the home directory to `~` (finding 1, owner decision).
- The command's mention of this todo's own pre-archive path is rewritten to `todofile.archived_path`, so the
  recorded check re-runs after the merge; a `REV:todos/...` read is left alone (finding 2).
- The `.sweep-evidence/...` pointer stays, labelled `(not committed)` (finding 3). The ~102 already-archived lines
  were not backfilled, per the owner decision.
- `todos/archive/086-...` conflict resolved by keeping the HEAD (archived) side: one `status: skipped` and the
  2026-05-28 "Archived as skipped" entry (finding 4). `todo-worker.md` notes that Land does the rewrite.

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0255)

- AC 1: `python3 scripts/todos/test_land.py` — evidence `.sweep-evidence/g1/524-ac0.txt` (not committed), last lines:

  ```text
    PASS  m9: the verify-only heading is 'Checked by'
    PASS  m9: no worker Work Log heading satisfies Land's Verified-note check
    PASS  m9: flip_acs's own heading still does

  All checks passed.
  ```

- AC 2: `cd . && echo "conflict marker lines: $(grep -cE '^(<{7}|={7}|>{7})' todos/archive/086-skipped-p3-drop-orphan-forum-tables.md)"; echo "status: lines: $(grep -c '^status:' todos/archive/086-skipped-p3-drop-orphan-forum-tables.md)"; python3 scripts/check_archived_todo_status.py; echo "check_archived_todo_status exit=$?"` — evidence `.sweep-evidence/g1/524-ac1.txt` (not committed), last lines:

  ```text
  ARCHIVED_UNCHECKED_AC     62          0
  TOTAL                     62          0
  62 grandfathered for unchecked acceptance criteria
  6 file(s) skipped: no frontmatter block, cannot be judged
  check_archived_todo_status exit=0
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0255)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
