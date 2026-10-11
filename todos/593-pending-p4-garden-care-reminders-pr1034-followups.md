---
status: pending
priority: p4
issue_id: "593"
tags: [todos, follow-ups]
dependencies: []
---

# Follow-ups from PR #1034 (todos 566, 570, 573)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1034 (care-reminder FCM errors, garden list and log prefixes). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1034 (todo sweep run 2026-10-11-1448, group g8, todos 566, 570, 573); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/garden_calendar/tasks.py:282` A credentials error (SenderIdMismatch/ThirdPartyAuth) is treated as server misconfiguration, but its tasks still take the permanent-failure path: owner added to `done`, claim kept. One bad FIREBASE_CREDENTIALS_B64 deploy drops every reminder due until fixed. | also: A project-wide credentials failure logs one ERROR per owner per sweep. The care sweep and send_forum_push_batch keep sending to every remaining recipient even though they fail identically, which floods the ERROR channel and wastes FCM calls.
2. **low** `backend/apps/garden_calendar/tasks.py:195` When autoretry is still possible, the age-out warning is turned off for every released task. A task within the retry delay of the lookback edge leaves the window before the retry claims it and is dropped with no warning. | also: The `autoretries` guess (OperationalError and retries < max_retries) mirrors the decorator's autoretry config by hand. If autoretry_for or max_retries changes, the age-out warning silently goes wrong. | On an OperationalError with retries left, the age-out warning is turned off for the whole batch. But the autoretry countdown (retry_backoff=60 with jitter, up to 240s on the 3rd try) can pass a task's 24h lookback edge. The retry's new `now` then never re-claims that task, and it is dropped with no warning.
3. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:295` careTaskTitle measures and cuts in UTF-16 code units; substring can split a surrogate pair at the cut, leaving a lone surrogate (sent as U+FFFD). The server counts code points, so emoji titles are also cut shorter than needed. | also: careTaskTitle cuts the title with String.substring on UTF-16 code units. A long plant name with an emoji or other non-BMP character at position 198/199 can be split mid surrogate pair, which sends a lone surrogate (it becomes U+FFFD or bad text) in the task title. | (garden_screen.dart:258) careTaskTitle truncates by UTF-16 code units. substring can split a surrogate pair (emoji at the cut), leaving a malformed string. The server counts code points, so this is also stricter than needed.
4. **low** `backend/apps/garden_calendar/models.py:1232` refresh_from_db under the lock clears cached relations (e.g. self.plant), so mark_complete/mark_skip may re-query plant for the next-occurrence build, discarding the view's select_related.
5. **low** `backend/apps/garden_calendar/signals.py:153` signals.py still holds a leftover management Command class; it is dead/misplaced code that manage.py never discovers. | also: A management `Command` class still lives in signals.py (pre-existing); the docstring rewrite documents it rather than moving it, so it is dead and never discoverable by manage.py.
6. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:253` The doc comment on careTaskTitle runs past 80 columns after a mid-edit reflow; dart format will not rewrap comments.
7. **low** `backend/apps/garden_calendar/signals.py:60` logger.exception already appends the traceback and exception; also passing `e` as a %s arg duplicates the message (same at the RSVP, weather and cleanup handlers). | also: logger.exception(..., %s, e) repeats the exception text already included by the traceback; harmless redundancy repeated in four handlers. | logger.exception already appends the traceback and exception; also passing `e` as a %s arg duplicates the message in each of the four converted handlers.
8. **low** `backend/apps/core/fcm.py:52` A token truly belonging to another sender now raises SenderIdMismatchError on every send; it is never cleared and logs ERROR each time, so a stale device token keeps firing alerts. Deliberate trade-off (owner decision, todo 566).
9. **low** `backend/apps/forum_host/tests/test_tasks.py:1021` The test calls cache.delete('wagtail_forum:digest-run:weekly') on the default cache; in dev/sweep runs that is shared Redis, so it can release a digest run lock held by a live local worker.
10. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:258` careTaskTitle truncates by UTF-16 code units. substring can split a surrogate pair (emoji at the cut), leaving a malformed string. The server counts code points, so this is also stricter than needed.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1034 (todos 566, 570, 573).
