---
status: completed
priority: p4
issue_id: "635"
tags: [forum, tests, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1080 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g10`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Finding 1 (611's Work Log out of date order): fixed as a doc correction. The worker's Implemented heading
  read 2026-10-12 (UTC); headings use the local date (`.claude/skills/completing-todos/SKILL.md:28-29`), so it
  now reads 2026-10-11 like Land's Verified and Completed entries, and a correction entry says why. The
  ENVIRONMENT DRIFT note is the local venv (todo 378), not the test.
- Finding 2 (no mutation evidence for the `"eof"` assertion): mutation check run. Deleting only
  `self.left_before_request = "eof"` in `DripServer._receive_request` makes `test_576_item2_...` fail with
  `AssertionError: assert None == 'eof'` at the new assertion; restored. Recorded in archived 611's Work Log.
- No code or test changed, so no new test.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 3 -- venv/bin/python -m pytest apps/forum_host/tests/test_link_preview.py -p no:cacheprovider --create-db -q && /usr/bin/grep -n -E '^### 2026-10-11 - Implemented by the todo sweep \(run 2026-10-12-0349\)|^### 2026-10-12 - Work Log date and eof mutation evidence corrected|assert None == .eof.' ../todos/archive/611-completed-p4-link-preview-rst-test-1057.md` — evidence `.sweep-evidence/g3/635-ac0.txt` (not committed), last lines:

  ```text
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 58 passed, 3 warnings in 26.80s ========================
  35:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  63:### 2026-10-12 - Work Log date and eof mutation evidence corrected by the todo sweep (run 2026-10-12-1724, todo 635)
  73:  test fail at `assert server.left_before_request == "eof"` (`AssertionError: assert None == 'eof'`), after
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Review round 2 of PR #1097: finding 1 corrected the other way

The edit above moved 611's Implemented heading to 2026-10-11. Review round 2 showed that was wrong: PR #1080
was opened at 2026-10-12 10:19 MDT, so the 2026-10-12 heading was right. The stale dates are Land's Verified
and Completed entries (2026-10-11), because `--date` was fixed at the run's start (21:49 MDT on 2026-10-11).
The heading is restored, and 611's correction entry now says this. Archived Work Log headings are not rewritten.

### 2026-10-12 - Correction by the todo sweep (run 2026-10-12-2056, todo 647)

The Implemented entry above also says 611's 2026-10-12 heading was a UTC date. That premise is false too: run
ids are UTC, but the worker wrote its heading with the local date, and 2026-10-12 was already the local date
(after midnight MDT) when it did. The entry is kept as written; this one corrects it.
