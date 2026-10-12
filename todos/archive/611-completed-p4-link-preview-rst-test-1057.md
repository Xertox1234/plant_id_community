---
status: completed
priority: p4
issue_id: "611"
tags: [backend, forum, testing, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1057 (todos 591 and 598, forum link-preview tests)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1057 (todos 591 and 598, forum link-preview tests). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1057 (todo sweep run 2026-10-11-2219, group g9, todos 591, 598); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `backend/apps/forum_host/tests/test_link_preview.py:1025` test_598's RST test syncs only on time.sleep(0.2) so the server reaches recv() before the reset. If the RST beats accept() (ECONNABORTED is retried in_accept) or surfaces as EOF, the asserts still pass, so the test can pass without exercising the new pre-request except OSError branch. | also: The new RST test only proves anything if the server has accepted and is in recv() before the reset. It relies on a 0.2s sleep for that. On a loaded runner the RST can land before accept(), e.g. dropped or ECONNABORTED on BSD/macOS. The test then passes without exercising the new except OSError branch. | backend/apps/forum_host/tests/test_link_preview.py:1036 New test 598 can pass without exercising the fix: if the RST beats accept() (ECONNABORTED is retried) the thread stays in_accept until stop(), so hung_up False and a dead thread hold even with the old code. The 0.2 s sleep makes this unlikely.
2. **low** `backend/apps/forum_host/tests/test_link_preview.py:1036` New test 598 can pass without exercising the fix: if the RST beats accept() (ECONNABORTED is retried) the thread stays in _accept until stop(), so hung_up False and a dead thread hold even with the old code. The 0.2 s sleep makes this unlikely.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1057 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g9`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Findings 1 and 2 (the same race): `DripServer` in `backend/apps/forum_host/tests/conftest.py` now sets an
  `accepted` event once a client is accepted, and records how a client that sent nothing left
  (`left_before_request`: `"eof"` or `"reset"`).
- `test_598_a_client_that_resets_before_sending_is_not_a_hang_up` waits on `accepted` instead of a 0.2 s
  sleep, checks the thread ended before `stop()` (a RST that beat `accept()` left it polling until `stop()`),
  and asserts `left_before_request == "reset"`, so it can no longer pass without reaching the pre-request
  `except OSError`. `test_576_item2_…` asserts `"eof"` the same way.
- Mutation check: deleting the pre-request `except OSError` branch makes test 598 fail
  (`assert None == 'reset'`); restored.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/forum_host/tests/test_link_preview.py -p no:cacheprovider --create-db -q` — evidence `.sweep-evidence/g10/611-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 58 passed, 3 warnings in 23.30s ========================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Work Log date and eof mutation evidence corrected by the todo sweep (run 2026-10-12-1724, todo 635)

- The Implemented heading (2026-10-12) is correct: PR #1080 was opened at 2026-10-12 10:19 MDT. The
  Verified and Completed entries say 2026-10-11 because Land's `--date` was fixed when the run started
  (21:49 MDT on 2026-10-11) and went stale after midnight. Those two dates are wrong, not the heading.
  (Review round 2 of PR #1097 caught an earlier edit that had moved the heading to 2026-10-11.)
- The ENVIRONMENT DRIFT in the Verified quote (pyjwt, urllib3) is the local venv lagging
  `backend/requirements.txt` (todo 378), not this test; CI installs the pins. It still prints on a re-run.
- Mutation check for the `"eof"` assertion in `test_576_item2_...`: deleting only
  `self.left_before_request = "eof"` in `DripServer._receive_request` (keeping its `return None`) makes the
  test fail at `assert server.left_before_request == "eof"` (`AssertionError: assert None == 'eof'`), after
  its `received == b""` and thread-ended asserts passed; restored, and the file passes again.
