---
status: completed
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

- [x] Tapping a push routes to the topic (and to the post when `post_id` is
      present), from BOTH a cold start (`getInitialMessage`) and a warm
      resume (`onMessageOpenedApp`) — a test per entry point, using a faked
      `FirebaseMessaging` (stated explicitly as a transport-layer proxy, not
      a physical-device repro — the real tray-tap path stays unverified until
      todo 286 unblocks a distributed iOS build; Android can be spot-checked
      manually on a dev build if desired, but that is not a substitute for
      an automated AC)
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-08-30 - Implemented, merged, and reconciled

- This file was never updated with implementation evidence despite the work
  already shipping — discovered while closing out todo 293, whose own local
  checkout had drifted 25 commits behind `origin/main`. Reconciling both
  files together in one pass, mirroring the identical situation resolved for
  todos 294 + 314 (PR #582).
- **Merged as PR #573, commit `5a6a6d2`** — "feat(mobile): FCM push-tap
  routing (todo 311)". Confirmed present and intact in the current working
  tree (not just that commit): `git merge-base --is-ancestor 5a6a6d2 HEAD`
  is true, working tree clean.
- **Production wiring**: `lib/services/push_message_router_service.dart` —
  `PushMessageRouterService` subscribes to
  `FirebaseMessaging.onMessageOpenedApp` (warm resume, constructor) and
  calls `_checkInitialMessage()` → `getInitialMessage()` (cold start).
  `_route()` parses `topic_id`/`post_id` from `message.data` and navigates
  via `router.pushNamed('forumTopic', pathParameters: {'id': '$topicId'},
  queryParameters: postId == null ? {} : {'postId': '$postId'})` — the same
  pattern `forum_notifications_screen.dart::_openNotification` already used
  for in-app taps, per the Recommended Action's "mirror" instruction. On
  cold start it also pre-empts a real splash-screen race by calling
  `router.go(AppRoutes.home)` first before routing to the target. Wired into
  `lib/main.dart` (`FirebaseMessaging.onBackgroundMessage(...)` +
  `ref.watch(pushMessageRouterServiceProvider)` in `MyApp.build`). Route
  target confirmed in `lib/core/routing/app_router.dart` — the `forumTopic`
  route parses `queryParameters['postId']` into `highlightPostId`.
- **Tests** (`test/services/push_message_router_service_test.dart`), both
  driving a hand-rolled `_FakeMessaging implements FirebaseMessaging`:
  - Warm resume: `'a warm-resume tap (onMessageOpenedApp) routes to the
    topic and post'` — drives `FirebaseMessagingPlatform.onMessageOpenedApp`,
    asserts `ForumThreadScreen` renders with the right `topicId`/
    `highlightPostId`.
  - Cold start: `'a cold-start tap (getInitialMessage) routes to the topic
    and post, and survives splash screen's own timer-driven redirect to
    home'` — asserts routing survives past splash's ~1.8s timer, the exact
    race the cold-start pre-empt above exists to fix.
  - Plus payload edge-case tests (no `post_id` key → no query param;
    unparseable `topic_id` → silent no-op) and a background-handler smoke
    test.
  - The file's own header comment states explicitly: "These tests drive the
    FCM tap entry points at the transport layer ... NOT a physical-device
    notification-tray tap. A real on-device repro is blocked on todo 286
    ... this is the closest coverage available until that lands." — matches
    this todo's own AC wording verbatim in spirit.
- Fresh verification on the reconciliation branch (`origin/main`, no
  application code changes):

  ```
  $ flutter test
  00:58 +420 ~3: All tests passed!

  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 1.9s)
  ```

## Notes

p3. Split out of todo 293 on 2026-08-17 per advisor guidance — todo 293's own
Recommended Action already ordered this last ("Push-tap routing last, since
it reuses the list's navigation target"), and the real todo-286 iOS blocker
makes it a materially different verification story than the other two
slices. Shipped 2026-08-17 (PR #573, `5a6a6d2`); confirmed merged and
archived 2026-08-30. Related: todo 286 (iOS APNs entitlement, gated/skipped
that session, since resolved via PR #529).
