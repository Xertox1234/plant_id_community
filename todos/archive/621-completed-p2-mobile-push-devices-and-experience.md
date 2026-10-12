---
status: completed
priority: p2
issue_id: "621"
tags: [backend, mobile, flutter, firebase, notifications, ux]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: foreground pushes show a restrained in-app banner plus data refresh (no OS banner, moderation sync silent); per-device PushDevice model lives in apps/core, shared by forum and care, migrating ForumProfile.fcm_token with deploy-skew support (2026-10-12)"
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

- [x] Tests prove two devices for one account both remain registered and receive eligible forum/care sends; logout on either removes only that device. Cross-account reuse, token rotation and concurrent registration preserve ownership.
- [x] A dead token clears only the matching registration; transient failure on one device does not silence another or retry successful devices. The legacy-token migration preserves existing working registrations and supports deploy skew safely.
- [x] Permission denied, token unavailable and backend-registration failure have accurate user-visible status and bounded recovery; login remains non-blocking and tests cover logout/account-switch races.
- [x] Foreground messages have a tested presentation/refresh path, listener cleanup and deduplication; self/routine moderation events remain silent. Named Android channel behavior is tested or explicitly scoped out with a dated rationale.
- [x] Cold/warm care taps reach the intended authorized task/plant or aggregate due list; tests cover signed-out sessions, restoration, malformed/stale targets and the no-duplicate-garden invariant.
- [ ] Backend registration/fan-out tests and Flutter registration/router/widget tests pass; Flutter analyze passes for changed code. Record any manual iOS/Android presentation observations with date/build, or explicitly re-point an uncompleted device check to a dedicated todo before archive. → todo 648 (re-pointed 2026-10-12)

## Work Log

### 2026-10-12 - Promoted recorded push limitations into implementation work

- Created at the user's request after comparing the audit with existing todos. Multi-device and foreground observations are promoted from 387; its signing criteria remain unchanged.
- No devices, credentials, registrations or application code were changed. Todo 547 continues to own the real due-care push verification.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1736)

- Backend: new `apps.core.PushDevice` (one row per installation, token unique, optional installation id) with `apps/core/push_devices.py` as its only writer, `POST /api/v1/push-devices/` and `/push-devices/unregister/`, and migration `core.0006_pushdevice` copying every legacy `ForumProfile.fcm_token`. Deploy skew: the legacy column stays, sends target the union of devices and the legacy token, and the host `MeProfileView` mirrors an old build's `fcm_token` PATCH (a blank clears only the device that profile last registered).
- Fan-out: forum (`send_forum_push`, `send_forum_push_batch`) and care (`_push_to_owners`) send to every device. A dead token clears only that registration; a transient failure retries only that device (`send_forum_push(token=...)`, new `send_care_reminder_to_device`) unless every device failed transiently, which keeps the old retry/release path. The 606 credentials stop is now counted per recipient at the recipient boundary.
- Mobile: `push_registration_service.dart` registers per device with a secure-storage installation id, falls back to the legacy PATCH on a 404, unregisters by this device's token at sign-out (awaiting an in-flight registration inside the 3 s bound), asks permission only when never asked, exposes a `PushStatus`, retries on a bounded schedule (no retry on 400/429) and reconciles on app resume. Settings shows it in `notification_status_tile.dart`, with Allow, OS Settings and Retry actions.
- Foreground (owner decision 2026-10-12): `push_foreground_presenter.dart` shows a floating in-app banner with View plus a data refresh, never an OS banner (iOS presentation options set off), deduplicates by message id, keeps `moderation_decided` and data-only messages silent, drops messages while signed out and clears on account change. Android notification channels are scoped out on 2026-10-12: the Android release is blocked on signing (todo 387) and a foreground message uses no channel.
- Care taps: `careFocusOf` turns the payload into a `GardenFocus` (one task, or the due list when `count` > 1); the garden highlights a pending task of the signed-in user, says "That care task is no longer due." otherwise, ignores a malformed target, keeps the todo 570 no-duplicate-garden rule, and drops the target on any sign-in or sign-out. No device was used; the manual iOS/Android observation is left to the owner.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1736)

- AC 1: `sh -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini --create-db -q -p no:cacheprovider apps/core/tests/test_push_devices.py::RegistrationOwnershipTest apps/core/tests/test_push_devices.py::PushDeviceApiTest apps/core/tests/test_push_devices.py::ForumFanOutTest::test_both_devices_receive_a_forum_push apps/core/tests/test_push_devices.py::CareFanOutTest::test_both_devices_receive_the_reminder'` — evidence `.sweep-evidence/g1/621-ac0.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 20 passed, 3 warnings in 20.84s ========================

  [exit code 0]
  ```

- AC 2: `sh -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini --create-db -q -p no:cacheprovider apps/core/tests/test_push_devices.py::RegistrationOwnershipTest::test_a_dead_token_is_forgotten_for_its_account_only apps/core/tests/test_push_devices.py::ForumFanOutTest apps/core/tests/test_push_devices.py::CareFanOutTest apps/core/tests/test_push_devices.py::LegacyTokenSkewTest apps/core/tests/test_push_devices.py::PushDeviceApiTest::test_the_legacy_profile_patch_is_mirrored_per_device apps/forum_host/tests/test_tasks.py apps/garden_calendar/tests/test_care_reminders.py'` — evidence `.sweep-evidence/g1/621-ac1.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 147 passed, 3 warnings in 21.87s =======================

  [exit code 0]
  ```

- AC 3: `sh -c 'cd plant_community_mobile && flutter test --timeout 120s test/services/push_registration_service_test.dart test/features/settings/notification_status_tile_test.dart test/services/auth_service_test.dart'` — evidence `.sweep-evidence/g1/621-ac2.txt` (not committed), last lines:

  ```text
  00:00 +105: plant_community_mobile/test/features/settings/notification_status_tile_test.dart: token unavailable: waiting, with Retry
  00:00 +106: plant_community_mobile/test/features/settings/notification_status_tile_test.dart: follows the service as its status changes
  00:00 +107: All tests passed!

  [exit code 0]
  ```

- AC 4: `sh -c 'cd plant_community_mobile && flutter test --timeout 120s test/services/push_foreground_presenter_test.dart && grep -n "scoped out" plant_community_mobile/lib/services/push_foreground_presenter.dart'` — evidence `.sweep-evidence/g1/621-ac3.txt` (not committed), last lines:

  ```text
  [PUSH] Foreground presentation not set: [core/no-app] No Firebase App '[DEFAULT]' has been created - call Firebase.initializeApp()
  00:00 +14: All tests passed!
  49:/// Android notification channels are scoped out of this slice (2026-10-12):

  [exit code 0]
  ```

- AC 5: `sh -c 'cd plant_community_mobile && flutter test --timeout 120s test/services/push_care_target_test.dart test/services/push_message_router_service_test.dart'` — evidence `.sweep-evidence/g1/621-ac4.txt` (not committed), last lines:

  ```text
  00:02 +22: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  00:02 +23: All tests passed!

  [exit code 0]
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1736)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Repaired by the todo sweep (run 2026-10-12-1736)

- Round-1 review: the legacy `fcm_token` mirror in `backend/apps/forum_host/api.py` registered each new column token but never removed the one it replaced, so two pre-621 builds on one account left both rows and the first build's sign-out removed the second build's device instead of its own.
- A legacy write that replaces the column now also unregisters the replaced token for this account (the old single-device semantics); re-sending the same token keeps its row, and `/push-devices/` registrations never touch the column.
- Added `PushDeviceApiTest::test_two_legacy_builds_then_the_first_signs_out` in `backend/apps/core/tests/test_push_devices.py`; it fails with the fix disabled and passes with it.

## Notes

P2 for cross-device loss of notification coverage. FCM-only care delivery and the 24-hour lookback are retained; this does not authorize an email/browser fallback or production messages. Use mocked sends during implementation and obtain approval for live device tests.
