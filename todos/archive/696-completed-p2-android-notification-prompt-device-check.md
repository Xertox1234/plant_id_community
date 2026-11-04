---
status: completed
priority: p2
issue_id: "696"
tags: [mobile, flutter, android, notifications, fcm, owner]
dependencies: ["685"]
---

# Owner device check: Android 13+ shows the notification-permission prompt

## Problem

Todo 685 found that Android 13+ never showed the notification-permission prompt after
sign-in. PR #1262 bumped `firebase_messaging` to ^16.7.1, which reports
`AuthorizationStatus.notDetermined` on Android 13+ before the user has answered, so the
existing sign-in flow now asks for `POST_NOTIFICATIONS`. Tests and analysis pass; whether a
real Android 13+ phone shows the prompt can only be checked on a device. Owner decision
2026-11-03 ("Close 685 as done by #1262") moved this check here.

Only the owner can run and record this check.

## Steps

1. Uninstall the app from the Samsung SM-A376B (Android 16), or clear its data, so
   `POST_NOTIFICATIONS` is back to not-set.
2. Install a build that contains PR #1262 and sign in.
3. Note whether the system notification-permission prompt appears, and allow it.
4. Send a push (for example a forum reply) and check it shows in the tray.

## Acceptance Criteria

- [x] On a fresh Android 13+ install, signing in shows the notification-permission prompt (device check, owner).

## Work Log

- 2026-11-03: Created from todo 685 criterion 1 (re-pointed by owner decision "Close 685 as done by #1262").
- 2026-11-04: Done on the owner's Samsung SM-A376B (Android 16, wireless adb). Build: `flutter build apk --release --dart-define-from-file=.env.production` from main `fcd4607a` (Flutter 3.47.9, `firebase_messaging` 16.7.1 locked). Uninstalled the old app, installed this APK: `dumpsys package` showed `POST_NOTIFICATIONS` requested with no grant state. After the owner signed in, logcat showed `GrantPermissionsActivity` start at 16:03:17 and `dumpsys` then read `POST_NOTIFICATIONS: granted=true, flags=[ USER_SET|...]`, so the prompt appeared and the owner allowed it. Step 4's tray check was not shown: the owner replied to their own post, and the backend does not notify a user about their own reply (owner: "it really shouldn't if it's my own post"). The tray path had already worked on this phone once permission was granted (todo 685: FCM registered and delivered; only the tray was suppressed).
