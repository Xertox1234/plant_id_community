---
status: pending
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

- [ ] Record any manual iOS/Android presentation observations with date/build, or explicitly re-point an uncompleted device check to a dedicated todo before archive.

## Work Log

### 2026-10-12 - Split from 621

- The device-observation half of 621's last criterion re-pointed here by owner decision; 621's tests and analyze evidence stay with 621.

## Notes

Owner-only: needs a physical device build. Todo 547 keeps the due-care end-to-end check; 387 keeps Android signing.
