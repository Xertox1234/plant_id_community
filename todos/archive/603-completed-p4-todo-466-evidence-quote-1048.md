---
status: completed
priority: p4
issue_id: "603"
tags: [docs, todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Add a dated correction entry to archived 583's Work Log quoting the current grep output; leave the old quote (2026-10-11)"
---

# Follow-ups from PR #1048 (todo 583, the todo-466 AC 4 evidence correction)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1048 (todo 583, the todo-466 AC 4 evidence correction). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1048 (todo sweep run 2026-10-11-2219, group g1, todos 583); follow-ups: verified.

1. **low** `todos/archive/583-completed-p4-chore-466-evidence-followups.md:55` The quoted AC 1 output does not match its command. The command names todos/archive/583-completed-...md, but the last quoted line prints todos/583-pending-...md:38, a path that no longer exists. This is the same command/output mismatch todo 583 was fixing.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1048 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g1`.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)

- Finding 1 (AC 1 quote in archived 583 prints the pre-archive path `todos/583-pending-...md:38`): fixed as a
  doc correction per the owner decision, no behaviour change, so no test.
- Appended a dated correction entry to the Work Log of
  `todos/archive/583-completed-p4-chore-466-evidence-followups.md`, quoting the full output of the same AC 1
  `grep` re-run on origin/main `9c1a6145`; every 583 line in it now prints the archived path.
- Land's original quoted block is left untouched; the new entry supersedes it and notes that the command
  matches its own quoted evidence, so a later re-run prints more lines.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `grep -n -E 'AC 1 evidence corrected|^  todos/archive/583-completed-p4-chore-466-evidence-followups.md:38:|Implemented by the todo sweep \(run 2026-10-12-0349\)|Finding 1 \(AC 1' todos/archive/583-completed-p4-chore-466-evidence-followups.md todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md` — evidence `.sweep-evidence/g4/603-ac0.txt` (not committed), last lines:

  ```text
  todos/archive/583-completed-p4-chore-466-evidence-followups.md:62:### 2026-10-11 - AC 1 evidence corrected by the todo sweep (run 2026-10-12-0349, todo 603)
  todos/archive/583-completed-p4-chore-466-evidence-followups.md:76:  todos/archive/583-completed-p4-chore-466-evidence-followups.md:38:- Finding 1 (AC 4 evidence of todo 466 out of order, nothing from 582): fixed as
  todos/603-pending-p4-todo-466-evidence-quote-1048.md:35:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  todos/603-pending-p4-todo-466-evidence-quote-1048.md:37:- Finding 1 (AC 1 quote in archived 583 prints the pre-archive path `todos/583-pending-...md:38`): fixed as a
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - AC 1 evidence corrected by the todo sweep (run 2026-10-12-1724, todo 629)

- The quoted AC 1 output above does not match its command: its lines 52-53 print
  `todos/603-pending-p4-todo-466-evidence-quote-1048.md:35` and `:37`, the pre-archive path,
  while the command names `todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md`.
  The quote is left as Land wrote it; this entry supersedes it.
- The same command, re-run on origin/main `7559dc57` before this entry was added, prints in full:

  ```text
  todos/archive/583-completed-p4-chore-466-evidence-followups.md:62:### 2026-10-11 - AC 1 evidence corrected by the todo sweep (run 2026-10-12-0349, todo 603)
  todos/archive/583-completed-p4-chore-466-evidence-followups.md:76:  todos/archive/583-completed-p4-chore-466-evidence-followups.md:38:- Finding 1 (AC 4 evidence of todo 466 out of order, nothing from 582): fixed as
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:35:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:37:- Finding 1 (AC 1 quote in archived 583 prints the pre-archive path `todos/583-pending-...md:38`): fixed as a
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:47:- AC 1: `grep -n -E 'AC 1 evidence corrected|^  todos/archive/583-completed-p4-chore-466-evidence-followups.md:38:|Implemented by the todo sweep \(run 2026-10-12-0349\)|Finding 1 \(AC 1' todos/archive/583-completed-p4-chore-466-evidence-followups.md todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md` — evidence `.sweep-evidence/g4/603-ac0.txt` (not committed), last lines:
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:50:  todos/archive/583-completed-p4-chore-466-evidence-followups.md:62:### 2026-10-11 - AC 1 evidence corrected by the todo sweep (run 2026-10-12-0349, todo 603)
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:52:  todos/603-pending-p4-todo-466-evidence-quote-1048.md:35:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:53:  todos/603-pending-p4-todo-466-evidence-quote-1048.md:37:- Finding 1 (AC 1 quote in archived 583 prints the pre-archive path `todos/583-pending-...md:38`): fixed as a
  ```

- Lines 35 and 37 of this file are still the Implemented heading and its "Finding 1" bullet, now printed under
  their archived path, which is what the old quote meant to show.
  The command matches its own quoted evidence, so a re-run after this entry prints more lines than shown here.
