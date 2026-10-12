---
status: pending
priority: p4
issue_id: "611"
tags: [backend, forum, testing, follow-ups]
dependencies: []
---

# Follow-ups from PR #1057 (todos 591 and 598, forum link-preview tests)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1057 (todos 591 and 598, forum link-preview tests). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1057 (todo sweep run 2026-10-11-2219, group g9, todos 591, 598); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `backend/apps/forum_host/tests/test_link_preview.py:1025` test_598's RST test syncs only on time.sleep(0.2) so the server reaches recv() before the reset. If the RST beats accept() (ECONNABORTED is retried in_accept) or surfaces as EOF, the asserts still pass, so the test can pass without exercising the new pre-request except OSError branch. | also: The new RST test only proves anything if the server has accepted and is in recv() before the reset. It relies on a 0.2s sleep for that. On a loaded runner the RST can land before accept(), e.g. dropped or ECONNABORTED on BSD/macOS. The test then passes without exercising the new except OSError branch. | backend/apps/forum_host/tests/test_link_preview.py:1036 New test 598 can pass without exercising the fix: if the RST beats accept() (ECONNABORTED is retried) the thread stays in_accept until stop(), so hung_up False and a dead thread hold even with the old code. The 0.2 s sleep makes this unlikely.
2. **low** `backend/apps/forum_host/tests/test_link_preview.py:1036` New test 598 can pass without exercising the fix: if the RST beats accept() (ECONNABORTED is retried) the thread stays in _accept until stop(), so hung_up False and a dead thread hold even with the old code. The 0.2 s sleep makes this unlikely.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1057 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g9`.
