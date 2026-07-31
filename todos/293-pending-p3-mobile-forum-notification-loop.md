---
status: pending
priority: p3
issue_id: "293"
tags: [forum, flutter, mobile, notifications]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile forum: the notification loop — subscriptions, list, push-tap routing

## Problem

The mobile client can receive a push (proven by todo 260 AC4) but the loop
around it is missing at both ends: a user cannot subscribe to a topic, cannot
see a notifications list, and tapping a push does not route anywhere. The three
are one feature — subscribing is what generates the notifications that the list
shows and the tap opens — so they are grouped rather than shipped separately.

## Findings

- Deferred items 3, 4 and 5 of todo 279 (from todo 260's Recommended Action),
  grouped here because they are one user-facing loop.
- Backend is ready on all three: `POST`/`DELETE
  /forum/topics/{id}/subscription/`; `TopicDetail.isSubscribed` already
  serialized; `GET /forum/notifications/` (cursor), `unread-count/`,
  `mark-read/`.
- The `/forum/topics/:id` param route added in todo 260 is the deep-link
  target foundation — the routing work is tap → that route, not new routes.
- **Only the tap→screen routing remains** on the push side. "Receives a push"
  is already proven; the unbuilt part is the whole `onMessage` /
  `onMessageOpenedApp` / `getInitialMessage` / background-handler subsystem.
- Notification payloads carry `post_id` and deep-link data (Wave 1, PR #473),
  so the tap target can be the exact post, not just the topic.
- Copy for these notifications now lives in ONE backend table,
  `backend/apps/forum_host/notification_copy.py` (todo 287) — read the tray
  wording from there rather than assuming it from a screenshot.

## Recommended Action

1. Subscriptions first (smallest, and it produces the data the other two
   render): `ForumApi` subscribe/unsubscribe + a toggle on the thread screen
   driven by `TopicDetail.isSubscribed`.
2. Notifications list + unread badge: cursor pagination, `mark-read` on tap.
   **DRF cursor `next`/`previous` are ABSOLUTE URLs** — fetch them verbatim,
   do not re-prefix the API base (`docs/rules/api.md`).
3. Push-tap routing last, since it reuses the list's navigation target.
   `getInitialMessage` (cold start) and `onMessageOpenedApp` (warm) are
   different entry points and both need covering.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/` — `models/`,
  `providers/`, `screens/` (`forum_topics_screen.dart`,
  `forum_thread_screen.dart`, `forum_composer_screen.dart`), `services/`
  (`forum_api.dart`, `forum_composer_controller.dart`, `forum_sync_service.dart`,
  `forum_sync_store.dart`), `widgets/`.
- `ForumApi` (`services/forum_api.dart`) is the seam to extend: add the method
  plus its fake, mirroring the existing endpoints.
- Codegen gate: editing a `@riverpod` source needs
  `flutter pub run build_runner build --delete-conflicting-outputs` and a
  committed `.g.dart`. CI blocks on this; local `flutter analyze` does NOT
  catch it. A clean rebuild is required — incremental can miss the hash.
- Read `plant_community_mobile/docs/patterns/riverpod.md` and
  `.../flutter-patterns.md` before writing.

## Acceptance Criteria

- [ ] Subscribe/unsubscribe from the thread screen; the toggle reflects
      `isSubscribed` on load — test
- [ ] Notifications screen lists notifications and pages correctly through an
      ABSOLUTE cursor URL — test asserting the second page is fetched verbatim
- [ ] Unread badge clears on mark-read — test
- [ ] Tapping a push routes to the topic (and to the post when `post_id` is
      present), from BOTH a cold start and a warm resume — a test per entry
      point
- [ ] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

## Notes

p3. Promoted from todo 279 on 2026-07-31. Related: todo 286 (iOS APNs
entitlement — blocks push actually arriving on a distributed iOS build, so
verify tap routing on Android or a dev build until that lands).
