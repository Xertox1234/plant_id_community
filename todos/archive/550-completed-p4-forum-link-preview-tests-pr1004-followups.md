---
status: completed
priority: p4
issue_id: "550"
tags: [forum, backend, tests, follow-ups, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-10
---

# Follow-ups from PR #1004 (todo 545, forum link-preview tests)

## Problem

Todo-sweep run 2026-10-11-0149 merged PR #1004. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1004 (todo sweep run 2026-10-11-0149, group g2, todos 545); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/forum_host/tests/test_link_preview.py:941` The client-reset test can pass without reaching the new `except OSError` in `_drip`. The client sends a RST before the drip thread accepts. accept() can then fail (ECONNABORTED on Linux), which `_accept` treats as 'listener closed', or macOS drops the connection. The thread exits quietly either way.
2. **medium** `backend/apps/forum_host/tests/test_link_preview.py:921` The new else-branch (connect used the whole budget) runs only on a loaded runner. A 0.5 s sleep against a 1.0 s budget never reaches it on a normal run, so its gettimeout()==connect_timeout and fileno()==-1 assertions go unverified. Same in the images test. | also: The edited existing tests are justified: production calls create_connection positionally, so the new slow_connect(address, timeout, ...) signature binds, and the else-branch matches production. However, the else branch is effectively unreachable on a normal run, so it adds coverage only on loaded runners.
3. **medium** `backend/apps/forum_host/tests/test_link_preview.py:924` Clock-race flake: the test picks its branch from its own connected_at, and production re-reads monotonic() at a different moment. If the deadline falls between the two reads, the else branch's `gettimeout()==connect_timeout` can fail, or so can the first branch's `<= deadline - connected_at`. Same at images:530/536. | also: The new else-branch assertions also pass under the bug they guard. With no deadline cut, nothing calls settimeout, so gettimeout()==connect_timeout. HTTPSConnection.connect's wrap_socket detaches the raw sock, so fileno()==-1 anyway. The same applies to test_link_preview_images.py:537. | low: test_link_preview.py:915. The branch is chosen by the clock at connected_at, but the wrapper decides whether to close with its own later monotonic() read. If the deadline falls between the two reads, the first branch's `gettimeout() <= deadline - connected_at` can fail. Same at test_link_preview_images.py:530. The window is narrow, and the code predates the diff.
4. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py:1336` _backtracking_repeats treats ATOMIC_GROUP like SUBPATTERN (av[-1]). An ATOMIC_GROUP's av is the SubPattern itself, so av[-1] is one (op, av) item and the recursion raises TypeError. ASSERT, ASSERT_NOT and GROUPREF_EXISTS are never walked, so a greedy repeat inside one passes. Latent today. | also: _backtracking_repeats treats an ATOMIC_GROUP's av like a SUBPATTERN tuple, but for ATOMIC_GROUP av is the sub-pattern itself, so av[-1] is its last (op, av) item and the walk crashes. ASSERT/ASSERT_NOT/GROUPREF_EXISTS bodies are never walked either, so a greedy repeat inside a lookaround would pass the guard. | low: test_link_previews.py:1337. `_backtracking_repeats` misreads ATOMIC_GROUP. Its av is the SubPattern itself, so av[-1] is the last (op, av) tuple and the walk raises TypeError. It also never descends into ASSERT, ASSERT_NOT or GROUPREF_EXISTS, so a backtracking repeat inside a lookaround would pass the linearity guard.
5. **low** `backend/apps/forum_host/tests/conftest.py:41` Two claims are inaccurate. The comment says the accepted socket inherits the listener's poll timeout, but CPython's accept() gives it the default timeout. The docstring says stop() ends the server promptly, yet a client that connects and sends nothing leaves recv() blocked until the join times out. | also: low: conftest.py:50. After accept, `connection.settimeout(None)` makes `recv(4096)` block indefinitely if a client connects but never sends. stop() cannot wake it, so teardown still stalls for the join timeout in that case. The stated goal of a prompt stop is met only in the no-connect case.
6. **low** `backend/apps/forum_host/tests/conftest.py:40` `_accept` treats every OSError as 'the listener was closed'. A transient accept error such as ECONNABORTED for one client silently ends the drip server, so the test then sees a refused or hung connection instead of the drip it expected.
7. **low** `backend/apps/forum_host/tests/test_link_preview.py:915` The branch is chosen by the clock at connected_at, but the wrapper decides whether to close with its own later monotonic() read. If the deadline falls between the two reads, the socket is closed with the connect timeout, and the first branch's `gettimeout() <= deadline - connected_at` can fail. The same flake exists at test_link_preview_images.py:530. The window is narrow, and the code predates this diff. | also: Test records connected_at after create_connection returns, but production re-checks the deadline slightly later. If the deadline passes in that gap, the socket is closed with its original timeout and the `<= deadline - connected_at` assertion fails. Narrow flake window. Same in test_link_preview_images.py.
8. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py:1337` `_backtracking_repeats` misreads ATOMIC_GROUP. Its av is the SubPattern itself, so av[-1] is the last (op, av) tuple and the walk raises TypeError. It also never descends into ASSERT, ASSERT_NOT or GROUPREF_EXISTS, so a backtracking repeat inside a lookaround would pass the linearity guard.
9. **low** `backend/apps/forum_host/tests/test_link_preview.py:916` The edited existing tests are justified. Production calls socket.create_connection(addr, timeout, source_address) with positional arguments, so the new slow_connect(address, timeout, ...) signature binds. The new else-branch matches production, which closes the socket without calling settimeout when remaining <= 0. However, the else branch is effectively unreachable on a normal run (0.5 s sleep against a 1.0 s budget), so it adds coverage only on loaded runners. | also: The branch choice uses the test's own connected_at, but the wrapper reads the clock again a little later. If connected_at < deadline while the wrapper's read is past it, the wrapper closes the socket without cutting its timeout, and the first branch's assert fails. The window is microseconds and predates this PR. The new else branch almost never runs in normal CI.
10. **low** `backend/apps/forum_host/tests/conftest.py:50` After accept, `connection.settimeout(None)` makes `recv(4096)` block indefinitely if a client connects but never sends. stop() cannot wake it, so teardown still stalls for the join timeout in that case. The stated goal of prompt stop is only met for the no-connect case.

9 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0401)

- Items 2, 3, 7, 9 (clock race, vacuous else branch): fixed. Both slow-connect tests in
  `backend/apps/forum_host/tests/test_link_preview.py` and `test_link_preview_images.py` are
  parametrized (0.2 s and 1.3 s connect against a 1 s budget), so each case lands in its branch by a
  wide margin instead of by the test's own clock read; the over-budget case now asserts the socket
  never reached `SSLContext.wrap_socket` (and, for pages, `reason == "deadline"`), which fails under
  the bug where the old `gettimeout()==connect_timeout` / `fileno()==-1` pair did not.
- Item 1 (reset test could miss `_drip`'s `except OSError`): fixed. The client reads the prefix
  before the RST, and `DripServer.hung_up` records that the except branch ran; the test asserts it.
- Items 5, 10 (wrong comment, `recv()` blocking stop): fixed in `backend/apps/forum_host/tests/conftest.py`.
  The comment now says CPython gives an accepted socket the default timeout; the first `recv()` polls
  the stop event. New test `test_550_item5_a_client_that_never_sends_does_not_stall_stop`.
- Item 6 (every accept `OSError` ends the server): fixed. ECONNABORTED/EINTR/EAGAIN keep it listening;
  new test `test_550_item6_a_transient_accept_error_does_not_end_the_server`.
- Items 4, 8 (`_backtracking_repeats`): fixed in
  `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py`. ATOMIC_GROUP recurses
  on its sub-pattern, and ASSERT, ASSERT_NOT and both GROUPREF_EXISTS arms are walked; pinned by the
  parametrized `test_550_item4_the_repeat_walk_reaches_every_sub_pattern`. No item was declined.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0401)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest backend/apps/forum_host/tests/test_link_preview.py backend/apps/forum_host/tests/test_link_preview_images.py backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g4/550-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 195 passed, 3 warnings in 31.57s =======================
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0401)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
