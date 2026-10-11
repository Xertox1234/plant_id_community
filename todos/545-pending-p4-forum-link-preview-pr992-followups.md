---
status: pending
priority: p4
issue_id: "545"
tags: [forum, backend, tests, follow-ups, todo-sweep]
dependencies: []
---

# Follow-ups from PR #992 (todo 539, forum link previews)

## Problem

Todo-sweep run 2026-10-10-2307 merged PR #992. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and confirmed each one is still present on main, and a
refuter dismissed none. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #992 (todo sweep run 2026-10-10-2307, group g3, todos 539); follow-ups: verified.

1. **low** `backend/apps/forum_host/tests/test_link_preview_images.py:435` The slow-connect/stalled-handshake tests (image and page twins) only check the handshake timeout `if connected_at < deadline`. If a loaded runner's 0.5 s connect overruns the 1.0 s budget, the tests pass with no regression-catching assertion, and they no longer assert elapsed time. | also: backend/apps/forum_host/tests/test_link_preview_images.py:425 The slow-connect image test checks the handshake timeout only under `if connected_at < deadline`. If the connect takes more than 1.0 s, the test passes while asserting nothing but `is None`. | backend/apps/forum_host/tests/test_link_preview.py:302 The page-fetch slow-connect test has the same silent guard. The reason check was widened to {"deadline","timeout"}, which is justified because the two outcomes race, but the guard can still skip the only real assertion. | backend/apps/forum_host/tests/test_link_preview.py:902 The tests accept reason in {'deadline','timeout'} and skip the timeout assertion when connected_at &gt;= deadline, so a loaded runner can make them pass unchecked.
2. **low** `backend/apps/forum_host/tests/conftest.py:107` The loopback_drip teardown closes the listening socket and joins with join(5). On Linux, close() from another thread does not wake a blocked accept(), so a test that never connects stalls teardown for 5 s. Also, recv() and sendall(prefix) are outside any try, so a client reset raises an unhandled thread exception. | also: backend/apps/forum_host/tests/conftest.py:44 The fixture closes the listener and then joins for up to 5 s. On Linux close() does not wake accept(); the `except OSError` branch only helps on macOS. | backend/apps/forum_host/tests/conftest.py:98 Closing the listener from another thread while drip() is blocked in accept() stalls the 5 s join and leaks a daemon thread when nothing connected. | If a test starts loopback_drip but nothing connects (e.g. the fetch aborts early), closing the listening socket does not reliably wake accept() on macOS or Linux, so teardown can stall for the full join(5).
3. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py:1330` The linear-scan regression test asserts wall time &lt; 1.0 s, a real-clock bound added by the same todo that removed real-clock flake risk (item 7). The quadratic regression takes about 4 s, so the margin is wide, but the test is still timing-based.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
