---
status: pending
priority: p3
issue_id: "311"
tags: [forum, flutter, mobile, notifications, firebase]
dependencies: ["293"]
source_review: "todo 293 (re-pointed 2026-08-17)"
---

# Mobile forum: push-tap routing (getInitialMessage / onMessageOpenedApp)

## Problem

Todo 293 shipped subscriptions and the in-app notifications list (`ForumApi`
subscribe/unsubscribe, `NotificationsFeed`, `ForumNotificationsScreen`,
tap-to-open from the list). What it deliberately did NOT ship is the
FCM-tap-to-navigate subsystem: tapping a push notification in the OS tray
does not route into the app today. That is the whole remaining slice of the
original todo 293 scope (its Recommended Action step 3), split out per an
advisor consult on 2026-08-17 because it has a real dependency this session
cannot satisfy (see Findings).

## Findings

- Todo 260 (AC4) proved the app **receives** a push. What's unbuilt is the
  whole `onMessage` / `onMessageOpenedApp` / `getInitialMessage` /
  background-handler subsystem — there is no FCM message-handler wiring in
  `plant_community_mobile/lib/` today (confirmed by grep: only
  `lib/services/push_registration_service.dart` exists, and it is
  token-registration only, not message handling).
- Notification payloads carry `post_id` and topic deep-link data (Wave 1, PR
  #473) — the tap target can be the exact post, not just the topic. The
  `/forum/topics/:id` route (todo 260) is the deep-link landing point; this
  todo is tap → that route, not a new route.
- **Real dependency, not just a nice-to-have:** todo 286 (iOS APNs
  entitlement) is on this session's gated-skip list (ops/Apple-portal gate).
  Push delivery on a distributed iOS build cannot be end-to-end verified
  until that lands. Android can receive real pushes without it.
- **What CAN be verified now, and what can't:** `getInitialMessage()`
  (cold start) and `onMessageOpenedApp` (warm resume) are both fakeable —
  inject a fake `FirebaseMessaging` and drive each entry point with a
  synthetic `RemoteMessage`, then assert the router lands on the right
  topic/post. That is a legitimate test, but it is a proxy for the real
  tray-tap path, the same category of gap flagged plainly on todo 297's AC1.
  A real device/tray-tap repro is NOT available in this environment. Do not
  flip AC4 (below) on the faked-messaging test alone without saying so.
- Copy for the tray title/body lives in
  `backend/apps/forum_host/notification_copy.py` (todo 287) — already wired
  server-side; this todo is client-side routing only, no copy changes.

## Recommended Action

1. Add the FCM message-handler subsystem: a top-level background handler
   (must be a top-level or static function per the `firebase_messaging`
   plugin's contract — a closure will not survive isolate restart), plus
   `FirebaseMessaging.onMessage`, `.onMessageOpenedApp`, and
   `.getInitialMessage()` wiring, most likely alongside
   `push_registration_service.dart` or a new sibling service.
2. On a tap (warm or cold), extract topic id (and `post_id` if present) from
   the message's data payload and navigate via the existing named route
   (`context.pushNamed('forumTopic', ...)` — mirror `forum_notifications_screen.dart`'s
   `_openNotification`, which already does the equivalent in-app-tap-to-route
   translation for the notifications list).
3. Test both entry points with a faked `FirebaseMessaging` — one test per
   entry point, per the AC below — and state in the Work Log that this is a
   faked-transport proxy, not a physical-device tray-tap repro.
4. Do not attempt a real distributed-build push-tap verification; that stays
   blocked on todo 286.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/` (routing target)
  and `lib/services/` (FCM lifecycle — see `push_registration_service.dart`
  for the existing epoch-based invalidation pattern this can reuse).
- Codegen gate: editing a `@riverpod` source needs
  `flutter pub run build_runner build --delete-conflicting-outputs`; CI blocks
  on a stale `.g.dart`, local `flutter analyze` does not catch it.
- Read `plant_community_mobile/docs/patterns/firebase-auth.md` (FCM lifecycle
  conventions) and `.../riverpod.md` before writing.

## Acceptance Criteria

- [ ] Tapping a push routes to the topic (and to the post when `post_id` is
      present), from BOTH a cold start (`getInitialMessage`) and a warm
      resume (`onMessageOpenedApp`) — a test per entry point, using a faked
      `FirebaseMessaging` (stated explicitly as a transport-layer proxy, not
      a physical-device repro — the real tray-tap path stays unverified until
      todo 286 unblocks a distributed iOS build; Android can be spot-checked
      manually on a dev build if desired, but that is not a substitute for
      an automated AC)
- [ ] `flutter test` passes; `flutter analyze` clean

## Notes

p3. Split out of todo 293 on 2026-08-17 per advisor guidance — todo 293's own
Recommended Action already ordered this last ("Push-tap routing last, since
it reuses the list's navigation target"), and the real todo-286 iOS blocker
makes it a materially different verification story than the other two
slices. Related: todo 286 (iOS APNs entitlement, gated/skipped this session).
