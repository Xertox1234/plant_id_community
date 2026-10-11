---
status: completed
priority: p4
issue_id: "576"
tags: [forum, backend, tests, follow-ups, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Item 5: re-run the env-drift evidence in a clean environment and record the result; do not decline it (2026-10-11)"
---

# Follow-ups from PR #1015 (todo 550, forum link-preview tests)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1015. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1015 (todo sweep run 2026-10-11-0401, group g4, todos 550); follow-ups: verified; 2 item(s) the curator did not return were kept as stored.

1. **low** `backend/apps/forum_host/tests/test_link_preview.py:1037` The reset test's prefix-read loop has no EOF guard. If the drip server closes before sending the full prefix, recv returns b'' at once on every pass and the test spins forever instead of failing. The 2 s socket timeout does not fire on EOF. | also: The reset test's prefix-read loop has no EOF guard: if the drip server closes before sending the full prefix (e.g. a future DripServer regression), recv returns b"" at once each time and the loop spins forever, hanging the suite instead of failing. The item-6 test right above it does guard this case. | test_link_preview.py:1036 The prefix-read loop `received += client.recv(...)` spins forever if the server closes early, because recv returns b'' and the length never grows. The 2 s timeout is per recv call, so b'' never raises. | test_link_preview.py:1038 The loop has no EOF check. A future regression in _accept/_receive_request that closes before the prefix makes recv return b"" at once, so the test hangs instead of failing.
2. **low** `backend/apps/forum_host/tests/conftest.py:61` _receive_request treats a clean EOF (recv returning b"") as a request, so the drip goes on to send the prefix to a client that already closed. It stops only on a later EPIPE/ECONNRESET, which also sets hung_up, so hung_up means any hang-up, not just a reset.
3. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py:1356` The new walk test covers atomic, lookaround and conditional nodes but has no nested-quantifier case (`(?:a*)*`, `(?:a*)*+`) and no BRANCH case, so the recursion through MAX_REPEAT, POSSESSIVE_REPEAT and BRANCH is unpinned and could be deleted with the suite green.
4. **low** `backend/apps/forum_host/tests/test_link_preview.py:1007` `assert len(calls) >= 2` in the transient-accept test is weak, since the accept poll loop calls accept repeatedly anyway; `received == b"prefix"` carries the test. Also `stopped_in < 1.0` in the item5 test is wall-clock based and could flake on a loaded runner.
5. **low** `todos/archive/550-completed-p4-forum-link-preview-tests-pr1004-followups.md:65` The AC evidence run printed ENVIRONMENT DRIFT (pyjwt and urllib3 mismatched against requirements.txt, so the results describe a tree CI does not run). The evidence file is not committed.
6. **low** `backend/apps/forum_host/tests/test_link_preview.py:1036` The prefix-read loop `received += client.recv(...)` spins forever if the server closes early, because recv returns b'' and the length never grows. The client socket has a 2 s timeout, but only per recv call, so b'' never raises. | also: The prefix-read loop `while len(received) < len(b"prefix"): received += client.recv(...)` spins forever if recv returns b"" (server closed early). The socket timeout only guards blocking reads, so a regression would hang instead of failing.
7. **low** `backend/apps/forum_host/tests/test_link_preview.py:1038` The reset test's prefix-read loop `received += client.recv(...)` has no EOF check. If the drip server ever closes before sending the prefix (a future regression in _accept/_receive_request), recv returns b"" at once and the loop spins forever, so the test hangs instead of failing.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Items 1, 6, 7 (one finding, reported three times): the reset test's prefix-read loop in
  `backend/apps/forum_host/tests/test_link_preview.py` now breaks on `b""`, so a server that closes early
  fails `received == b"prefix"` instead of hanging. Checked by making the drip skip the prefix: it fails in 0.6 s.
- Item 2: `DripServer._receive_request` (`backend/apps/forum_host/tests/conftest.py`) treats a clean EOF as
  the client leaving and sends nothing; `hung_up` now means a hang-up mid-drip. New test
  `test_576_item2_a_client_that_closes_before_sending_gets_nothing` (failed before the fix with `b'prefixX'`).
- Item 3: `test_550_item4_the_repeat_walk_reaches_every_sub_pattern` gains `(?:a*)*`, `(?:a*)*+`, `a*|b*`
  and `(?:a*|b*)*`. Removing the BRANCH, MAX_REPEAT or POSSESSIVE_REPEAT recursion now fails it.
- Item 4: the transient-accept test asserts the abort really was injected instead of `len(calls) >= 2`; the
  item-5 test drops `stopped_in < 1.0`, since `not thread.is_alive()` after `stop(timeout=2)` is the real check.
- Item 5 (owner decision: re-run in a clean environment): built a fresh `backend/venv` from
  `backend/requirements-dev.txt` and re-ran the three link-preview suites. Header `deps: 221 pinned,
  0 mismatched, 0 not installed, 1 unpinned, 0 removed-but-installed`, no ENVIRONMENT DRIFT section,
  `200 passed`. The main checkout's venv still has pyjwt 2.13.0 and urllib3 2.7.0 (pins 2.15.0 and 2.8.0).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/forum_host/tests/test_link_preview.py backend/apps/forum_host/tests/test_link_preview_images.py backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g13/576-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 200 passed, 3 warnings in 53.95s =======================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
