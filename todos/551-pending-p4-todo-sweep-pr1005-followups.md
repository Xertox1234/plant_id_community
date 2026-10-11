---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
