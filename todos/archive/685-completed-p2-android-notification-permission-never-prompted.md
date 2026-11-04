---
status: completed
priority: p2
issue_id: "685"
tags: [mobile, flutter, android, notifications, fcm]
dependencies: []
triage: ready
triaged: 2026-11-03
owner_decision: "Bump now, device later: the worker does the firebase_messaging bump and tests now; the Samsung SM-A376B device check moves to a new follow-up todo for the owner (2026-11-03)"
---

# Android 13+ never shows the notification-permission prompt

## Problem

Found on a physical Samsung SM-A376B (Android 16) on 2026-11-02 (todo 387 Work Log). After signing in, the user is never asked to allow notifications. FCM still registers the device and the push reaches it, but Android suppresses every tray notification:

```
NotificationService: Suppressing notification from package com.plantcommunity.plant_community_mobile by user request.
```

`dumpsys package` showed `POST_NOTIFICATIONS: granted=false` without `USER_SET`: the user never refused. A fresh debug install logged `[PUSH] Notification permission: AuthorizationStatus.denied` before any prompt.

## Root cause (verified against the plugin source)

`PushRegistrationService.syncAfterLogin` asks only when the status is `notDetermined` (`_refreshPermission(askIfUndetermined: true)` in `lib/services/push_registration_service.dart`). On Android, `firebase_messaging` 16.4.1 (the locked version) maps `getNotificationSettings()` to `areNotificationsEnabled ? 1 : 0`, which is authorized or denied and never `notDetermined` (`FlutterFirebaseMessagingPlugin.java`, `getPermissions()`). So the ask can never fire on Android, and the settings tile offers "Settings" (the denied case) and not "Allow".

`firebase_messaging` 16.7.1 adds `resolveNotificationAuthorizationStatus()`, which returns `AUTH_NOT_DETERMINED` until the permission has been requested once. It also adds `AUTH_DENIED_PERMANENTLY`, so check whether the Dart `AuthorizationStatus` enum gains a value that the exhaustive switch in `_permissionOf` must handle.

## Recommended Action

1. Bump `firebase_messaging` (and its platform interface) to a version that reports `notDetermined` on Android. Map any new enum value in `_permissionOf`.
2. Add a test that a `notDetermined` status from `getNotificationSettings()` triggers `requestPermission()` on sign-in, and that `denied` does not.
3. Verify on a physical Android 13+ device: a fresh install, sign-in shows the system prompt, Allow, then a background push appears in the tray.

## Acceptance Criteria

- [ ] On a fresh Android 13+ install, signing in shows the notification-permission prompt (device check, owner). → todo 696 (re-pointed 2026-11-03)
- [x] A test covers the ask-on-`notDetermined` path and the no-ask-on-`denied` path.
- [x] `flutter analyze` is clean and `flutter test` passes.

## Notes

No Android build is distributed yet, so no user is affected today. This must be fixed before an Android release. The workaround is Profile → Settings → Notifications → Settings → allow.

## Work Log

### 2026-11-02 - Filed from the Android device check (todo 387)

- Reproduced twice on the owner's Samsung SM-A376B (release and debug builds); root cause read in the locked plugin source.

### 2026-11-03 - Checked by the todo sweep (run 2026-11-03-2214)

- No code change: PR #1262 already bumped `firebase_messaging` to ^16.7.1 (locked 16.7.1) and mapped `AuthorizationStatus.deniedPermanently` to `PushPermission.denied` in `plant_community_mobile/lib/services/push_registration_service.dart`.
- The ask-on-`notDetermined` and no-ask-on-`denied` paths are covered by the `permission (todo 621)` group in `plant_community_mobile/test/services/push_registration_service_test.dart` (6 tests pass, including a `deniedPermanently` case).
- `flutter analyze` reports no issues and the full `flutter test` suite passes (1581 tests, 11 skipped).
- The Samsung Android 13+ device check is owner-only; per the owner decision it moves to a new follow-up todo (696).

### 2026-11-03 - Verified by the todo sweep (run 2026-11-03-2214)

- AC 2: `cd plant_community_mobile && flutter test test/services/push_registration_service_test.dart --plain-name 'permission (todo 621)'` — evidence `.sweep-evidence/g10/685-ac1.txt` (not committed), last lines:

  ```text
  [PUSH] Notification permission: AuthorizationStatus.deniedPermanently
  [PUSH] FCM token registered (13 chars)
  00:00 +5: permission (todo 621) requestPermission (the settings tile) reports the answer
  00:00 +6: All tests passed!
  exit=0
  ```

- AC 3: `cd plant_community_mobile && flutter analyze && flutter test` — evidence `.sweep-evidence/g10/685-ac2.txt` (not committed), last lines:

  ```text
  02:51 +1579 ~11: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  02:51 +1580 ~11: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  02:51 +1581 ~11: All tests passed!
  exit=0
  ```

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
