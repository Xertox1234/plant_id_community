---
status: pending
priority: p2
issue_id: "685"
tags: [mobile, flutter, android, notifications, fcm]
dependencies: []
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

- [ ] On a fresh Android 13+ install, signing in shows the notification-permission prompt (device check, owner).
- [ ] A test covers the ask-on-`notDetermined` path and the no-ask-on-`denied` path.
- [ ] `flutter analyze` is clean and `flutter test` passes.

## Notes

No Android build is distributed yet, so no user is affected today. This must be fixed before an Android release. The workaround is Profile → Settings → Notifications → Settings → allow.

## Work Log

### 2026-11-02 - Filed from the Android device check (todo 387)

- Reproduced twice on the owner's Samsung SM-A376B (release and debug builds); root cause read in the locked plugin source.
