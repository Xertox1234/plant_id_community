---
status: pending
priority: p4
issue_id: "647"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
---

# Follow-ups from PRs #1104 and #1097 (todos 637, 629, 635, todo-sweep runbook and archive dates)

## Problem

Todo-sweep run 2026-10-12-1724 merged PRs #1104 and #1097 (todos 637, 629, 635, todo-sweep runbook and archive dates). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1104 (todo sweep run 2026-10-12-1724, group g10, todos 637); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/todos/state.py:509` The unblock gate accepts any owner_decision, but confirm, clear_hold, release_incomplete and hand_round also append to it, so a needs-design/blocked-*todo moved by a bare `set … ready` or --reset-stranded and later confirmed or hold-cleared still flips to triage: ready (#2/#4 by another path). | also: The new unblock gate takes any owner_decision as the answer. confirm() also appends 'criterion N confirmed by the owner' to owner_decision, so a needs-design/blocked-* todo moved by a bare `set ready` and then given a confirmed criterion is still unblocked without its question being answered.
2. **medium** `.claude/skills/completing-todos/SKILL.md:413` Step 6 records kimi_recovery=skipped via annotate, but no code reads it: summary/show do not surface it and finish deletes the run file. The wrap-up `kimi: skipped` count is prose-only and can miscount (per-todo annotate, aborted commits, repeat recoveries). | also: The wrap-up now counts groups annotated kimi_recovery=skipped, but no code or test reads that field. state.py annotate accepts any key, so the count is prose-only and a missed or mistyped annotation silently under-reports. | also: The wrap-up says it counts groups annotated kimi_recovery=skipped, but no code reads that field. annotate() writes it onto every todo entry of the group, so a multi-todo group could be counted once per todo. The runbook test only pins the strings. | kimi_recovery=skipped is written only into the run file. No state.py command surfaces it, and wrap-up step 2 (finish) deletes the run file, so the promised kimi: skipped count relies on the model reading it ad hoc first. The 637 #3 test checks only the wording.
3. **medium** `.claude/skills/completing-todos/SKILL.md:419` The wrap-up now counts groups annotated kimi_recovery=skipped, but no code or test reads that field. state.py annotate accepts any key, so the count is prose-only and a missed or mistyped annotation silently under-reports. | also: The wrap-up says it counts groups annotated kimi_recovery=skipped, but no code reads that field. annotate() writes it onto every todo entry of the group, so a multi-todo group could be counted once per todo. The runbook test only pins the strings.
4. **low** `scripts/todos/land.py:590` _log_date takes the max of every `### YYYY-MM-DD` Work Log heading with no calendar or plausibility check, so one mistyped heading (2026-13-40, 2062-10-12) is copied into every later Verified/Completed entry and can differ from --date used elsewhere in archive. | also: _log_date takes max() of the raw heading strings. A typo'd or impossible Work Log date (e.g. 2062-10-12, 2026-13-40) passes the regex and becomes the date of every later Verified/Completed entry. The Completed heading can also now differ from the --date used elsewhere in archive (review-doc check-off). | LOG_HEADING_DATE_RE matches any NNNN-NN-NN, so a malformed Work Log heading date such as 2026-13-40 wins `max()` and Land writes that invalid date into its Verified and Completed headings. Only `date` is checked with `_valid_date`. |_log_date takes the max of every `### YYYY-MM-DD` heading in the Work Log and does not check that it is a real date or close to `date`. One mistyped future heading (e.g. 2027-10-12 or 9999-99-99) makes every later Verified and Completed entry carry that wrong date, which corrupts the record without notice.
5. **low** `scripts/todos/test_state_flow.py:1490` The 637 #1/#3/#5 runbook checks are substring pins on SKILL.md prose. They fail if the wording changes but cannot show that the recovery steps work.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

PR #1097 (todo sweep run 2026-10-12-1724, group g3, todos 629, 635); follow-ups: verified.

1. **low** `todos/archive/635-completed-p4-link-preview-eof-1080.md:40` The Implemented entry for finding 1 repeats the false premise that the 2026-10-12 heading was UTC. Run ids are UTC, but the worker's heading used the local date after midnight MDT.

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: todos/archive/611-completed-p4-link-preview-rst-test-1057.md:35 The 611 heading change is not justified: it replaced a correct date (2026-10-12) with a wrong one (2026-10-11). Run 0349 began 21:49 MDT on 10-11, but #1080 merged 10:33 MDT on 10-12, so 2026-10-12 was the real local date. (fixed on main: origin/main line 35 reads '### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)'. Round 2 restored the heading, and 635's round-2 entry records the reversal.; the refuter agreed: On origin/main, 611 line 35 reads '### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)'. The heading is back to the correct 2026-10-12, so the wrong 10-11 heading is no longer there.)
- low: todos/archive/611-completed-p4-link-preview-rst-test-1057.md:66 The correction entry says run 0349 'ran on 2026-10-11 local', but the run spanned two local days. Nine sibling todos (602, 607, 609, 610, 612-616) keep '2026-10-12 - Implemented', so only 611 differs and the archive is inconsistent. (fixed on main: On main, the correction entry (lines 63-66) now says the 2026-10-12 heading is correct and only Land's Verified and Completed dates are stale. Neither 'ran on 2026-10-11' nor a 10-11 heading remains, so 611 matches its siblings.; the refuter agreed: On origin/main, 611's correction entry (lines 63-66) says the 2026-10-12 heading is correct and only Land's Verified and Completed dates are stale. It no longer says 'ran on 2026-10-11', and the heading matches the siblings' 2026-10-12.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PRs #1104 and #1097 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g10 / g3`.
