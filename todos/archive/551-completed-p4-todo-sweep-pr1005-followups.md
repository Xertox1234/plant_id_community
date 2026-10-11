---
status: completed
priority: p4
issue_id: "551"
tags: [todo-sweep, scripts, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Finding 3: the refuter judges every merged 'also' phrasing separately; only the phrasings it refutes drop, the rest stay as follow-ups (2026-10-10)"
---

# Follow-ups from PR #1005 (todo 546, the sweep engine)

## Problem

Todo-sweep run 2026-10-11-0149 merged PR #1005. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1005 (todo sweep run 2026-10-11-0149, group g3, todos 546); follow-ups: verified.

1. **medium** `scripts/check_archived_todo_status.py:233` Fence toggling now hides `## Work Log` itself: an odd fence count before it (a ```` block quoting a ``` line, or an unclosed fence) leaves fenced=True, so the heading is skipped and every home path in the Work Log goes undetected by Land and CI. Probed: both cases return [] (main finds them). | also: The fence toggle runs across the whole file, so one unclosed fence before `## Work Log` makes that heading count as fenced. The Work Log is then never scanned and home paths in it pass Land and CI. | Fence tracking toggles on any ``` or ~~~ line without matching the opening character or length. A ~~~ inside a ``` block, or a ``` inside a ```` block, inverts the state, so a real `## Work Log` heading can be read as fenced and that section is never scanned (a missed leak).
2. **medium** `scripts/todos/worker_edit_guard.py:87` When the cwd is the main checkout, edits are now allowed only in `sweep-*` worktrees. The retry worker (todo-execute.js:192) and the review repair worker run with no isolation and edit the group's recorded worktree. If that worktree is `agent-*` (no-worktree fallback, or a --reverify of a pre-528 attempt), every edit is denied. | also: WORKER_PREFIXES treats only sweep-/agent- as worker worktrees, but workflow isolation:'worktree' (todo-execute.js fallback when a brief has no worktree) creates .claude/worktrees/wf_* (pilot-results doc, land.py). Such a worker's edits in its own worktree, and a retry's, are now denied. | With the cwd in the main checkout, only `sweep-*` targets are allowed now. A repair worker for an older run whose recorded PR worktree is a harness `agent-*` or other non-sweep dir under .claude/worktrees used to be allowed and is now denied on every edit.
3. **medium** `.claude/workflows/todo-followups.js:129` A refuted item is now dropped with all of its merged `also` phrasings, and ingest_followups counts those as covered. If the curator merged a different problem from another file:line into it, that follow-up is silently lost. refutePrompt never asks the refuter to refute every phrasing. | also: Every phrasing of a dropped item now covers stored lines by exact summary text, at any location. A stored follow-up the curator left out, at another file:line with an identical summary (e.g. 'missing test'), is silently lost instead of being kept as uncovered. | Phrasings from workflow drops now count as covered without the location check applied to kept items. A refuted item, even at an invented file:line, drops every raw finding its `also` names, including a different-location one the refuter never judged. Before, those stayed as uncovered.
4. **low** `scripts/todos/worker_edit_guard.py:83` `own` counts as a worker worktree by name prefix alone. If the engine's session itself ran from an `agent-*` worktree, an inheriting worker is treated as harness-isolated, and every edit to its sweep worktree is denied.
5. **low** `scripts/check_archived_todo_status.py:101` The new `-(Users|home)-` alternative matches ordinary prose after a space, for example 'x -home-made'. The `/+home/` lookbehind no longer excludes '/', so 'apps//home/x' matches too. Both cause false ARCHIVED_HOME_PATH hits in a Work Log.
6. **low** `scripts/todos/state.py:866` The recovery hint names `<name>.aside-<today>` for both the moved directory and the renamed branch. A second collision on the same day gives a command that fails, because the target and branch already exist. It fails safely, but the hint is wrong.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0401)

- Finding 1 fixed: `scripts/check_archived_todo_status.py` gains `fenced_lines`, which closes a fence only on the same character at least as long with nothing after it, and treats an unclosed opener as plain text; `parse()` and `work_log_home_paths()` both use it. That exposed three real bare boxes in `todos/archive/2025-10-28-parallel-resolution/044-resolved-p2-pii-logging-not-enforced.md` (a python fence line quoted inside its markdown fence had flipped the old toggle and hidden them), so it joins `grandfathered_unchecked_acs` in `todos/archive-status-allowlist.yml`.
- Finding 2 fixed: `scripts/todos/worker_edit_guard.py` counts `wf_*` (workflow isolation) as a worker worktree, and from the main checkout allows any worker worktree, not only `sweep-*`, so a retry or repair worker can edit a recorded harness worktree; a human's or the session's worktree is still denied. The part about "other non-sweep dirs" is declined: the guard cannot tell such a recorded worktree from a human's, and todo 546 deliberately denies those.
- Finding 3 fixed per the owner decision: `.claude/workflows/todo-followups.js` asks the refuter to judge the summary and each `also` phrasing (`also_refuted`); only refuted phrasings drop, the rest stay kept at the item's location. `ingest_followups` in `scripts/todos/state.py` now rejects a drop at a location the review never reported, and a dropped phrasing covers a stored line only in the drop's own file. Two existing `test_workflows.js` stubs were changed only to add the now-required `also_refuted` field, and the 546 #993-6 check now sets `also_refuted: [0]`.
- Finding 4 declined: an `agent-*` cwd cannot be told apart from a harness-isolated worker's, and letting it edit sweep worktrees would reopen cross-group edits the 546 tests pin; the engine is not run from a harness worktree.
- Findings 5 and 6 fixed: the TMPDIR alternative must follow a `/` and the `/home/` alternative must start at the first slash of a run (`a -home-made fix`, `apps//home/x` no longer match); `add_worktrees` names the first free `<name>.aside-<date>[-N]` (directory and branch both checked, computed only on failure).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0401)

- AC 1: `bash -c 'cd . && python3 scripts/test_check_archived_todo_status.py && python3 scripts/check_archived_todo_status.py --fail-over 0 && python3 scripts/todos/test_state.py && python3 scripts/todos/test_state_flow.py && node scripts/todos/test_workflows.js && bash .claude/hooks/test-guard-todo-worker-edit.sh && echo ALL-SUITES-PASSED'` — evidence `.sweep-evidence/g5/551-ac0.txt` (not committed), last lines:

  ```text
  PASS: a cwd in no git checkout fails open
  PASS: malformed JSON fails open

  Results: 25 passed, 0 failed
  ALL-SUITES-PASSED
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0401)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
