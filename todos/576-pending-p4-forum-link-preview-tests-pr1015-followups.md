---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
