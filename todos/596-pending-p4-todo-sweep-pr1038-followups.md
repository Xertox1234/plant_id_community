---
status: pending
priority: p4
issue_id: "596"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1038 (todos 572, 577, 578)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1038 (todo-sweep re-point markers, follow-up dedup and land cwd tracking). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

Note from the run: items 3, 4, 6 and 7 were fixed on the PR before it merged (the guard allows a worktree
while a run has an `executing` todo with none recorded, and land.py reads `-C` only from git's global options;
see the dropped list). Item 1 is fixed only for the retry case; its other two points (an unreadable run file
elsewhere, and `previous` attempts not being read) are still open. The fixed items stayed only because of item 2's
pool-counting gap, which this run reproduced in nine groups.

## Findings

PR #1038 (todo sweep run 2026-10-11-1448, group g11, todos 572, 577, 578); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/todos/worker_edit_guard.py:618` The guard fails closed for `wf_*/agent-*` worktrees no run file records: a retry/repair worker whose run file sits elsewhere or is unreadable is denied mid-run, and recorded_worktrees ignores each entry's "previous" attempts.
2. **medium** `scripts/todos/state.py:1477` Pool counting makes each returned phrasing cover only one stored line. If the curator merges two identical phrasings (or one in the returned line's own `also`) and lists the text once, the second stored line comes back uncovered and is filed again as a duplicate.
3. **medium** `scripts/todos/land.py:360` `_GIT_C_RE` treats any later -C as `git -C <dir>`, subcommand options included. Probed: `git grep -C 2 foo <wt>/backend/x` gives `../backend/x` and `git diff -C <wt>/web/a <wt>/web/b` gives `../b`. Both are wrong paths in the Work Log; before this change they were right.
4. **medium** `scripts/todos/worker_edit_guard.py:901` Retry worker is denied on the harness-isolated fallback path. With no brief worktree, todo-execute.js gives the first worker a `wf_*` worktree, then runs the retry from the main checkout. The run file does not record that worktree until ingest-execute, after the workflow, so the guard denies the 551 #2 case.
5. **low** `scripts/check_archived_todo_status.py:274` The archive tripwire now runs REPOINT_RE's unanchored `.*` alternatives over a criterion's whole joined text, so a wrapped criterion like 'Port X from todo 12 / must not be re-pointed' passes as moved by accident.
6. **low** `scripts/todos/land.py:261` `_GIT_C_RE` matches any `-C <word>` in a git part, including git's copy-detection flag. So `cd <wt>/backend && git diff -C HEAD <wt>/web` reads HEAD as a directory and rewrites the path to `../../web` (probed); the correct path is `../web`. | also: `_GIT_C_RE` matches any `-C <arg>` in a git part, including the subcommand flag in `git log -C`, `git diff -C` or `git blame -C`. The next path is then taken as a directory, and later paths are rebased against it, which is wrong.
7. **low** `.claude/hooks/test-guard-todo-worker-edit.sh:11` This edit is justified: the 551 #2 allow cases now get a run file under the 577 #5 rule. But it pre-seeds the record, so no test covers a harness worktree that is used before ingest records it. That is the gap in the first finding.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: scripts/todos/worker_edit_guard.py:128 The 577 #5 'recorded' check denies the 551 #2 retry worker. With no brief worktree, todo-execute gives the worker a `wf_*/agent-*` worktree; the retry edits it from main before ingest_execute records it, so every retry edit is denied. (fixed on main: origin/main decide() also allows when awaiting_a_worktree(*roots): any run entry with stage 'executing' and no worktree, so the unrecorded retry worktree is allowed.; the refuter agreed: origin/main decide() (worker_edit_guard.py:136-138) also allows when awaiting_a_worktree(): any run entry stage 'executing' without a worktree. execute-args transitions to 'executing' (state.py:836) before the workflow, so the unrecorded retry worktree is allowed; test covers it.)
- medium: scripts/todos/land.py:248 `_GIT_C_RE` matches any -C after `git`, including subcommand options (`git grep -C 3`, `git diff -C`, `git log/blame -C`), so later paths are rebased against a non-directory and wrong paths go into the Work Log. (fixed on main: `_GIT_C_RE` is gone on origin/main; `_git_c_events` walks only global options between `git` and the subcommand (stops at first non-option word), with `_GIT_GLOBAL_WITH_VALUE`, so subcommand -C is ignored.; the refuter agreed: `_GIT_C_RE` is gone. `_git_c_events` (land.py:362-380) scans only tokens after `git`, records -C values only among global options, and breaks at the first non-option word (the subcommand), so `git grep -C 3` / `git diff -C` are ignored.)
- low: .claude/hooks/test-guard-todo-worker-edit.sh:89 Pre-seeding a run file recording $AGENT/$WF makes the 551 #2 fixture test only the 'already recorded' case; no test covers an unrecorded same-run retry worktree used before ingest records it. (fixed on main: origin/main test lines 125-129 write a run file with {"7":{"stage":"executing"}} and assert_allow a retry edit on the unrecorded `wf_*` worktree (PR #1038 case).; the refuter agreed: origin/main test adds a case writing {"7":{"stage":"executing"}} and asserting allow for an unrecorded `wf_*` retry edit, plus a deny once stage is 'verified'. The unrecorded same-run retry is now tested.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1038 (todos 572, 577, 578).
