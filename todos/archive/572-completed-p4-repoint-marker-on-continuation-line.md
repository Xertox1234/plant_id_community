---
status: completed
priority: p4
issue_id: "572"
tags: [todo-sweep, scripts]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "parse() joins a criterion's continuation lines the way ac_lines does, so hand-written markers are covered too (2026-10-11)"
---

# A re-point marker on a criterion's continuation line passes the engine but fails `land.py archive`

## Problem

The two acceptance-criteria parsers disagree about wrapped criteria:

- `scripts/todos/todofile.py` `ac_lines()`, behind `state.criteria_problem`,
  joins a criterion's indented continuation lines into one text.
- `scripts/check_archived_todo_status.py` `parse()`, used by `land.py archive`
  and CI, matches `REPOINT_RE` per physical line. Only the `- [ ]` line counts.

In sweep run 2026-10-11-0053, todo 386's AC 4 was re-pointed during triage with
the `→ todo 547 (re-pointed …)` marker at the end of its wrapped second line.
The engine's checks accepted it. `land.py archive` refused with "1 unchecked
criteria". Land then hand-joined the criterion onto one line and dropped a
trailing period. On the next review round `criteria_problem` blocked the group:
"criterion 3 was edited". The verified repair had to be committed by hand, and
PR #998 left the engine.

## Acceptance Criteria

- [x] `check_archived_todo_status.parse()` treats a wrapped criterion as one
      unit, joining continuation lines the way `todofile.ac_lines` does. A
      marker anywhere in the criterion then counts as a re-point. Alternatively,
      re-pointing in the triage step always puts the marker on the checkbox
      line. Either way, a test covers the wrapped-marker case end to end:
      `criteria_problem` passes, and `archive` accepts it.
- [x] The completing-todos runbook's stale/supersede step says where the marker
      goes.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- `scripts/check_archived_todo_status.py` `parse()` now reads a criterion as its checkbox line plus its wrapped lines, using the same `continues()` rule as `todofile.ac_lines` (moved into the checker, which todofile imports), so a re-point marker anywhere in the criterion counts. A fenced line never continues one.
- `state.repoint` tests the joined criterion for an existing marker too; its docstring no longer claims the tripwire reads the checkbox line only.
- Tests: `scripts/test_check_archived_todo_status.py` (wrapped marker, wrapped bare criterion, a marker in a new bullet below, a fenced line) and an end-to-end case in `scripts/todos/test_land.py`: `criteria_problem` passes before and after flip-acs, flip-acs skips the re-pointed criterion, and `archive` accepts the todo, whose archived file passes the tripwire.
- `todos/archive-status-allowlist.yml`: dropped the unchecked-AC grandfather entry for `todos/archive/383-completed-p2-firebase-hardening-carryover.md`. Its two open criteria carry `RE-POINTED to todo 387` on a wrapped line, so they now read as re-points and the entry went stale (the checker fails a stale entry).
- The completing-todos runbook's Supersede step says the marker goes at the end of the checkbox line or of the criterion's last wrapped line.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `python3 scripts/test_check_archived_todo_status.py && python3 scripts/todos/test_land.py && python3 scripts/check_archived_todo_status.py --fail-over 0` — evidence `.sweep-evidence/g11/572-ac0.txt` (not committed), last lines:

  ```text
  ARCHIVED_HOME_PATH        38          0
  TOTAL                    100          0
  62 grandfathered for unchecked acceptance criteria
  38 grandfathered for a home path in the Work Log
  6 file(s) skipped: no frontmatter block, cannot be judged
  ```

- AC 2: `grep -n 'todo 572' .claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g11/572-ac1.txt` (not committed), last lines:

  ```text
  94:| `stale` | "Supersede" / "Keep" | Supersede: re-point each open criterion (`→ todo NNN (re-pointed $TODAY)`; put the marker at the end of the criterion's checkbox line, or of its last wrapped line, since both parsers read a wrapped criterion as one unit, todo 572) and archive the todo as `superseded` inside the triage PR, then `skipped --decision "superseded: …"`. Keep: `blocked --decision …` |
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
