---
status: pending
priority: p4
issue_id: "573"
tags: [logging, backend, scripts, follow-ups, todo-sweep]
dependencies: []
---

# Follow-ups from PR #1012 (todo 392, backend log prefixes)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1012. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1012 (todo sweep run 2026-10-11-0401, group g1, todos 392); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/check_log_prefixes.py:163` is_exempt also scans the line directly above the call, so a trailing `# log-prefix: exempt` on one single-line logger call (or on any unrelated line above) silently exempts an unprefixed logger call on the next line. | also: The new is_exempt/EXEMPT column logic has no test and no CI caller; it exempts a call whenever the line above contains the mark. | is_exempt has no dedicated test: no self-test covers the line-above, own-line, or no-marker-nearby cases; a marker on a non-adjacent line is not rejected by any test. | is_exempt looks only at text after the first '#' on a line, so a '#' inside a string literal on the call's lines (e.g. "#%s") can hide or fake the mark. Needs contrived input; the 2 real exempt sites report correctly. | The `log-prefix: exempt` marker is honored only by the checker; scripts/add_log_prefixes.py doesn't read it, so re-running it would stamp `[X]` onto the relayed lines and produce doubled `[EMAIL] [EMAIL]`. | is_exempt matches a trailing comment on an unrelated line directly above a call (e.g. `x = 1  # log-prefix: exempt`); the docstring says only a comment above or on the call's own lines counts.
2. **low** `backend/apps/forum_host/tests/test_tasks.py:968` The new relay test keeps a leftover debug `print(f"relayed: ...")` loop, filters task lines with a loose `"starting" not in message` substring denylist, and asserts every relayed line starts with '[EMAIL] digest frequency=weekly', which is brittle. | also: Leftover debug print inside the new test; noise in test output. | The `"starting" not in message` filter is a brittle denylist; any relayed command line containing 'starting' would be skipped silently. | Filtering by 'starting' could make the assertion pass vacuously if task lines are excluded. | The all() startswith('[EMAIL] digest frequency=weekly') check fails if the command ever writes another [EMAIL] line (e.g. a summary). | Test depends on cache lock state: if the digest run lock is already held, the lock-held line is still relayed and the test passes, which could mask a lock leak. | Edit only adds a new test; no existing test was changed or weakened.
3. **low** `backend/apps/forum_host/tests/test_tasks.py:961` caplog.at_level(logger=...) does not attach caplog.handler; with propagate=False on app loggers it could capture nothing. The `assert relayed` guard prevents green-by-emptiness, but the setup is fragile.
4. **low** `backend/apps/blog/tasks.py:78` The blog newsletter relay loop is newly exempted, but no test runs the real send_blog_newsletter through the task to pin exactly one [EMAIL] per relayed line; only the forum relay is covered. | also: The blog newsletter relay was given the same no-prefix exemption, but no test runs the real command through the task to pin a single [EMAIL] per relayed line.
5. **low** `backend/apps/garden_calendar/signals.py:149` After hoisting the BaseCommand import, the `# Weather alert cleanup task - remove expired alerts` comment is orphaned above blank lines rather than the Command class it describes. | also: Moving the BaseCommand import to the top leaves a dangling comment followed by a blank gap; cosmetic only. | The comment is now orphaned with two blank lines before the Command class. | Separately, signal receivers still call NotificationService inline instead of transaction.on_commit (existing behaviour, not part of this diff).
6. **low** `backend/apps/garden_calendar/signals.py:60` Log calls still use f-strings (`logger.error(f"[NOTIFY] ...{e}")`) rather than lazy %s args, and lose the traceback.
7. **low** `backend/apps/forum_host/tests/test_tasks.py:967` The edit to test_tasks.py only adds a new test; no existing test was changed or weakened. The new test drops relayed records by substring ("starting" not in message), so any relayed command line that contains "starting" would be skipped silently. It also leaves a debug print loop in the test. | also: Debug residue: print(f"relayed: ...") loop left in the new test. Also the `"starting" not in` filter is a loose substring match that could hide a relayed line.
8. **low** `backend/apps/forum_host/tests/test_tasks.py:965` Filtering relayed lines by `"starting" not in message` is brittle: a task log line containing that word is silently excluded and the assertion can pass vacuously.
9. **low** `backend/apps/forum_host/tests/test_tasks.py:970` Leftover debug print() in the new test. The test also depends on cache lock state and on the exact command wording (startswith '[EMAIL] digest frequency=weekly'), which makes it brittle. | also: Test keeps a leftover debug print, and a magic 'starting' substring filter. The all() startswith('[EMAIL] digest frequency=weekly') check fails if the command ever writes another [EMAIL] line (e.g. a summary). | The new test has a debug `print(f"relayed: ...")` loop. It adds noise and does no asserting. | The new test has a stray debug print loop, and the 'starting' substring filter is fragile. If the test cache already holds the digest run lock, the command's lock-held line is still relayed and the test still passes, so it can mask a lock leak. | Test has a leftover debug print loop, and its assertion requires every relayed line to start with '[EMAIL] digest frequency=weekly'. That breaks if the command later emits any other [EMAIL] line (for example a summary), so the test is brittle.
10. **low** `backend/apps/garden_calendar/signals.py:148` After hoisting the BaseCommand import, the `# Weather alert cleanup task` comment is orphaned above blank lines, not the class it describes. | also: Moving the BaseCommand import to the top leaves the 'Weather alert cleanup task' comment followed by blank lines and then the Command class. The comment now floats with no code under it. Separately, the signal receivers still call NotificationService inline instead of using transaction.on_commit (existing behaviour, not part of this diff).

3 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
