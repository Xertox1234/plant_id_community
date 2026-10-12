---
status: pending
priority: p2
issue_id: "621"
tags: [backend, mobile, flutter, firebase, notifications, ux]
dependencies: []
---

# Support multiple push devices and complete the mobile notification experience

## Problem

An account has one FCM token, so a second device replaces the first and logout can clear another device's registration. Foreground messages lack a presentation path, registration failures are difficult for users to diagnose, and care-reminder taps discard the task identifiers carried by the push.

## Findings

Source: Devin's read-only audit and todo comparison, 2026-10-12. Single-token behavior and missing foreground integration were source-confirmed; this audit did not send live pushes.

- `backend/packages/wagtail_forum/wagtail_forum/models/profiles.py:26-46` stores one `fcm_token` per account. `api/serializers.py:1576-1604` updates that field; `plant_community_mobile/lib/services/push_registration_service.dart:155-180` clears it with an empty-token PATCH rather than identifying this device.
- `todos/387-blocked-p3-android-release-signing-and-sign-in.md:253-269` already records a foreground message received without a visible notification and an emulator replacing the operator's iPhone token. These are work-log observations, not 387's remaining signing/device acceptance criteria. Promote them here rather than assuming 387 will fix them.
- `plant_community_mobile/lib/services/push_message_router_service.dart:71-77` handles initial-message and background-tap entry points; the audit found no foreground `onMessage` listener or presentation configuration in shipped mobile source. Firebase documentation distinguishes foreground receipt from automatic background tray display.
- `push_registration_service.dart:75-123,126-152` logs failures only in debug and relies on login/token rotation to try again. Permission is requested during login, and denied permission does not prevent token registration on Android; token presence alone cannot prove visible delivery.
- `push_message_router_service.dart:125-177` recognizes a care event but ignores its task/plant identifiers and opens the garden. Todo 570 fixed duplicate garden stacking; preserve that behavior.

## Recommended Action

1. Add per-installation/device push registrations with an authenticated ownership model and a safe migration from the legacy field. Bind each token to only its current account; logout/dead-token cleanup must affect only the matching registration, never another device or a newer rotated token.
2. Fan out forum and care pushes to all eligible devices with per-device failure handling. Preserve 606's credentials-stop recovery, account preferences and the existing anti-duplicate semantics.
3. Add bounded registration reconciliation on an appropriate lifecycle event and truthful permission/registration status in mobile settings, including guidance to OS settings after denial. Ask permission contextually without blocking login or repeatedly nagging a denied user.
4. Choose and implement foreground presentation: a restrained banner or relevant data refresh, not duplicate OS and in-app alerts. Keep routine moderation sync events silent and clean up listeners on disposal/account changes. Configure named Android notification categories if Android is supported in the chosen slice.
5. Route care pushes to the referenced authorized task/plant, with an aggregate due-list destination for multi-task messages and safe fallback for missing/completed/deleted targets. Preserve auth restoration and warm/cold navigation behavior.

## Technical Details

Primary files are cited above, plus `backend/apps/core/fcm.py`, `backend/apps/forum_host/tasks.py`, `backend/apps/garden_calendar/tasks.py`, mobile auth integration and garden routes. Reference `plant_community_mobile/docs/patterns/firebase-auth.md` and `riverpod.md`.

Existing owners: 547 retains the physical-device end-to-end due-care check; 387 retains Android signing/physical sign-in; 602 owns browser registrations, which are not FCM devices; 606 owns the forum credentials-stop handoff. Coordinate preference UI with todo 620 rather than implementing two competing policies.

## Acceptance Criteria

- [ ] Tests prove two devices for one account both remain registered and receive eligible forum/care sends; logout on either removes only that device. Cross-account reuse, token rotation and concurrent registration preserve ownership.
- [ ] A dead token clears only the matching registration; transient failure on one device does not silence another or retry successful devices. The legacy-token migration preserves existing working registrations and supports deploy skew safely.
- [ ] Permission denied, token unavailable and backend-registration failure have accurate user-visible status and bounded recovery; login remains non-blocking and tests cover logout/account-switch races.
- [ ] Foreground messages have a tested presentation/refresh path, listener cleanup and deduplication; self/routine moderation events remain silent. Named Android channel behavior is tested or explicitly scoped out with a dated rationale.
- [ ] Cold/warm care taps reach the intended authorized task/plant or aggregate due list; tests cover signed-out sessions, restoration, malformed/stale targets and the no-duplicate-garden invariant.
- [ ] Backend registration/fan-out tests and Flutter registration/router/widget tests pass; Flutter analyze passes for changed code. Record any manual iOS/Android presentation observations with date/build, or explicitly re-point an uncompleted device check to a dedicated todo before archive.

## Work Log

### 2026-10-12 - Promoted recorded push limitations into implementation work

- Created at the user's request after comparing the audit with existing todos. Multi-device and foreground observations are promoted from 387; its signing criteria remain unchanged.
- No devices, credentials, registrations or application code were changed. Todo 547 continues to own the real due-care push verification.

## Notes

P2 for cross-device loss of notification coverage. FCM-only care delivery and the 24-hour lookback are retained; this does not authorize an email/browser fallback or production messages. Use mocked sends during implementation and obtain approval for live device tests.
