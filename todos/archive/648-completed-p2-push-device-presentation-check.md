---
status: completed
priority: p2
issue_id: "648"
tags: [mobile, flutter, firebase, notifications, owner, device]
dependencies: []
---

# Observe foreground and tray push presentation on a real device build

## Problem

Split from todo 621 (run 2026-10-12-1736, owner decision 2026-10-12): 621 ships per-device push registration, the foreground in-app banner and care-tap routing with automated tests; the manual iOS/Android presentation observation needs an owner-run device build.

## Recommended Action

1. Install a build containing 621 on a physical iPhone (and Android once 387's signing lands). Register two devices on one account.
2. Trigger an eligible forum reply and a due care reminder with the app foregrounded, backgrounded and killed; tap each notification.
3. Record date, build number, device/OS and what appeared (in-app banner vs tray, routing target, duplicates).

## Acceptance Criteria

- [x] Record any manual iOS/Android presentation observations with date/build, or explicitly re-point an uncompleted device check to a dedicated todo before archive. (completed 2026-11-02: iOS forum-reply observations in the Work Log; Android stays with 387, care-reminder presentation with 547)

## Work Log

### 2026-10-12 - Split from 621

- The device-observation half of 621's last criterion re-pointed here by owner decision; 621's tests and analyze evidence stay with 621.

### 2026-11-02 - iOS forum-reply presentation observed (owner on device)

Setup: the owner's iPhone on TestFlight build 16 (the latest uploaded build, 2026-10-17, which contains 621; the build number was not read back from the device), signed in as `plantadmin`. Replies were posted to the owner's topic 51 by the `simtest` prod test account (owner OK, 2026-11-01: "do it"). The owner approved held replies in Reports → Pending forum content, and approval is the publish that fires `reply_added`.

| State | Post | Result |
|---|---|---|
| Foreground (on topic 51) | #304 | In-app banner shown; tapping it opened topic 51. Web bell count went to 2. |
| Background | #305 | iOS notification arrived; tapping it opened topic 51. |
| Killed (swiped away) | #306 | iOS notification arrived; tapping it cold-launched the app on topic 51. |

No duplicate notifications were reported in any state.

Findings, all expected behaviour:
- The first attempt (post #303) had no device to reach: the app was signed out, so `PushDevice` held no row for the user and the `forum_push` delivery was `suppressed / no_destination`. The email copy was sent. Signing in registered the device (`ios`, 2026-11-02 10:04 UTC).
- The background push was held about 10 minutes as `pending / coalescing`, because it came within `REPLY_COALESCE_SECONDS` (600 s) of the foreground one on the same topic. The hold released as designed (todo 624). A device test spaces replies more than 10 minutes apart, timed from the previous **send**.
- Build 16 predates mobile live replies (#1165, 2026-10-19), so the reply did not appear on the open thread by itself. A build containing #1165 is needed to see that.
- Replies after `simtest`'s first one were held for moderation as low-trust content.

Not covered here: Android (blocked on signing, todo 387), two devices on one account, and care-reminder presentation (todo 547 keeps the due-care push end to end).

## Notes

Owner-only: needs a physical device build. Todo 547 keeps the due-care end-to-end check; 387 keeps Android signing.
