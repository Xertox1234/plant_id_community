---
status: pending
priority: p4
issue_id: "635"
tags: [forum, tests, follow-ups]
dependencies: []
---

# Follow-ups from PR #1080 (todo 611, link-preview drip test)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1080 (todo 611, link-preview drip test). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1080 (todo sweep run 2026-10-12-0349, group g10, todos 611); follow-ups: verified.

1. **low** `todos/archive/611-completed-p4-link-preview-rst-test-1057.md:47` Work Log entries are out of order by date: 'Implemented' is dated 2026-10-12, but the 'Verified' and 'Completed' entries after it are dated 2026-10-11, the day before run 2026-10-12-0349 that produced them. Only the audit trail is affected, not the code. | also: The Work Log entries 'Verified' and 'Completed' are dated 2026-10-11, but they come after the 2026-10-12 'Implemented' entry and belong to run 2026-10-12-0349. The record's dates contradict each other. Only the docs are affected; the test code is fine. | Work Log headings for 'Verified' and 'Completed' are dated 2026-10-11, a day before the implementation entry (2026-10-12), so the log reads out of order. The test run also used a drifted venv (pyjwt, urllib3), which the log notes. | Work Log entries 'Verified' and 'Completed' are dated 2026-10-11, but they come after the 'Implemented' entry dated 2026-10-12 for the same run (2026-10-12-0349). The dates are out of order. | Work Log 'Verified' and 'Completed' entries are dated 2026-10-11 but come after the 2026-10-12 'Implemented' entry, so the chronology is inverted. The quoted evidence also shows ENVIRONMENT DRIFT (pyjwt/urllib3 mismatch), so it does not match what CI runs.
2. **low** `backend/apps/forum_host/tests/test_link_preview.py:1000` The eof assertion in test_576_item2 relies on the DripServer.left_before_request side-channel, which only the 598 mutation check exercised. The log gives no mutation evidence that the new 'eof' assertion goes red.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1080 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g10`.
