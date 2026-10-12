---
status: completed
priority: p4
issue_id: "598"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1041 (todo 576)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1041 (link-preview test follow-ups from PR #1015). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1041 (todo sweep run 2026-10-11-1448, group g13, todos 576); follow-ups: verified.

1. **low** `backend/apps/forum_host/tests/conftest.py:66` Docstrings now say hung_up is reserved for a mid-drip hang-up. But a client that sends RST before any request makes the first recv() raise ConnectionResetError, which the OSError handler records as hung_up=True. The documented contract is wider than the code.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1041 (todo 576).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Fixed in the code, not the docs: `DripServer._receive_request` in `backend/apps/forum_host/tests/conftest.py`
  now treats an `OSError` (a reset) on the first `recv()` like a clean EOF, as the client leaving, so the drip
  ends without the prefix and `hung_up` stays False. `hung_up` now means only a mid-drip hang-up, as documented.
- New test `test_598_a_client_that_resets_before_sending_is_not_a_hang_up` in
  `backend/apps/forum_host/tests/test_link_preview.py` connects, waits in the server's `recv()`, closes with
  `SO_LINGER 0` (an RST) and asserts the thread ended quietly with `hung_up` False. It failed before the fix.
- The class docstring now names both early-leaving cases (EOF and reset before any request).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/apps/forum_host/tests/test_link_preview.py -v --create-db -p no:cacheprovider -k "drip or hang or reset or client or accept"` — evidence `.sweep-evidence/g9/598-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================= 8 passed, 50 deselected, 3 warnings in 1.50s =================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
