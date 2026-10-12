---
status: pending
priority: p4
issue_id: "629"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
---

# Follow-ups from PR #1073 (todos 603, 608, todo evidence quotes)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1073 (todos 603, 608, todo evidence quotes). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1073 (todo sweep run 2026-10-12-0349, group g4, todos 603, 608); follow-ups: verified.

1. **low** `todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:52` 603's AC 1 quote repeats the defect 603 fixes. The command names todos/archive/603-completed-...md, but quoted lines 52-53 print todos/603-pending-...md:35/:37, a pre-archive path that no longer exists. A re-run prints the archive path. | also: The AC 1 verification quote has the same defect this todo fixes. The command names todos/archive/603-completed-...md, but quoted lines 52-53 print todos/603-pending-...md:35/37, which no longer exists. A re-run prints the archived path. | 603's own AC 1 evidence repeats the defect 603 fixes. The command names todos/archive/603-completed-...md, but the quoted lines 52-53 print todos/603-pending-...md:35/37, a path that no longer exists. Re-running the command prints archive/603-completed...:35/37/47/50/52/53. | 603's own Verified AC 1 quote repeats the defect 603 fixes: the command names todos/archive/603-completed-...md, but quoted lines 52-53 print todos/603-pending-...md:35/:37, a path that no longer exists after archive.
2. **low** `todos/archive/608-completed-p4-thread-summary-too-short-1054.md:63` 608's AC 1 quote has the same pre-archive path mismatch. The command names todos/archive/608-completed-...md, but quoted lines 63-65 print todos/608-pending-...md:45/47/49. A re-run on this branch prints the archive path. | also: The AC 1 quote names todos/archive/608-completed-...md in its command, but lines 63-65 print todos/608-pending-...md:45/47/49, the pre-archive path. This is the same command/output mismatch that todo 603 corrects for 583. | Same pre-archive path mismatch in 608's AC 1 evidence. The command names todos/archive/608-completed-...md, but quoted lines 63-65 print todos/608-pending-...md:45/47/49, a path that no longer exists after the rename. | Same command/output mismatch in 608's Verified AC 1 quote: the command greps todos/archive/608-completed-...md, but lines 63-65 print todos/608-pending-...md:45/47/49, the pre-archive path.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: todos/archive/583-completed-p4-chore-466-evidence-followups.md:62 The Work Log headings in 583, 603 and 608 are dated 2026-10-11, but they describe run 2026-10-12-0349, which ran on 2026-10-12. The dates do not match the run id. | also: The new Work Log headings are dated 2026-10-11, but they describe run 2026-10-12-0349 and a re-run on origin/main 9c1a6145, the 2026-10-12 triage commit. The same mismatch appears in the 603 and 608 entries, so the dates misstate when the work happened. (refuted: completing-todos SKILL.md:28-29 sets RUN_ID with `date -u` (UTC) and TODAY with the local `date`. Triage commit 9c1a6145 is dated 2026-10-11 22:10 -0600, so run 2026-10-12-0349 UTC ran on 2026-10-11 local. The 2026-10-11 headings follow the convention.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1073 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g4`.
