---
status: pending
priority: p3
issue_id: "524"
tags: [tooling, todo-sweep]
dependencies: []
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

- [ ] Findings 1–3 are fixed in `land.py` (or the worker/verifier contract) with tests, so a Land's
      Verified entry has no `/Users/` and no worktree name.
- [ ] Finding 4: 086 has no conflict markers and one `status:` line, and
      `scripts/check_archived_todo_status.py` still passes.

## Work Log

- 2026-10-01: Filed from the main session of todo-sweep run 2026-10-02-0118.
