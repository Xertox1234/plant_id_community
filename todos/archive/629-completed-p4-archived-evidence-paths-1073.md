---
status: completed
priority: p4
issue_id: "629"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1073 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g4`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Findings 1 and 2 (603's and 608's AC 1 quotes print the pre-archive `todos/60N-pending-...md` path): fixed
  as doc corrections, no behaviour change, so no test. Same remedy todo 603 used for 583.
- Appended a dated "AC 1 evidence corrected" entry to `todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md`
  and `todos/archive/608-completed-p4-thread-summary-too-short-1054.md`, each quoting the full output of the
  same AC 1 command re-run on origin/main `7559dc57`, where every line prints the archived path.
- Land's quoted blocks are left untouched; the new entries supersede them.
- Root cause, not changed here: `scripts/todos/land.py` rewrites the todo's own path to its archived path in
  the quoted command but not in the quoted tail lines, so a grep of the todo's own file still quotes the
  pending path.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `/usr/bin/grep -n -E 'AC 1 evidence corrected by the todo sweep \(run 2026-10-12-1724, todo 629\)|^  todos/archive/60[38]-completed-[a-z0-9-]+\.md:(35|37|45|47|49):' todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md todos/archive/608-completed-p4-thread-summary-too-short-1054.md` — evidence `.sweep-evidence/g3/629-ac0.txt` (not committed), last lines:

  ```text
  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:73:  todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md:47:- AC 1: `grep -n -E 'AC 1 evidence corrected|^  todos/archive/583-completed-p4-chore-466-evidence-followups.md:38:|Implemented by the todo sweep \(run 2026-10-12-0349\)|Finding 1 \(AC 1' todos/archive/583-completed-p4-chore-466-evidence-followups.md todos/archive/603-completed-p4-todo-466-evidence-quote-1048.md` — evidence `.sweep-evidence/g4/603-ac0.txt` (not committed), last lines:
  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:72:### 2026-10-12 - AC 1 evidence corrected by the todo sweep (run 2026-10-12-1724, todo 629)
  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:87:  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:45:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:88:  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:47:- Finding (`ThreadSummaryPanel.tsx`, `outcome?.status !== 'ready'` "broader than the comment"): declined, per
  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:89:  todos/archive/608-completed-p4-thread-summary-too-short-1054.md:49:- Reason: `type Outcome = Exclude<TopicSummary, { status: 'pending' }>`
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
