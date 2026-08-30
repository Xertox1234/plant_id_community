---
status: completed
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

- [x] Subscribe/unsubscribe from the thread screen; the toggle reflects
      `isSubscribed` on load — test
- [x] Notifications screen lists notifications and pages correctly through an
      ABSOLUTE cursor URL — test asserting the second page is fetched verbatim
- [x] Unread badge clears on mark-read — test
- [x] Push-tap routing (cold start `getInitialMessage` + warm resume
      `onMessageOpenedApp`, one test per entry point) → split to
      **todo 311** on 2026-08-17 (advisor consult: the real todo-286 iOS
      APNs blocker makes this a materially different verification story than
      the other two slices above, which have no such blocker). Resolved via
      todo 311 — PR #573 merged, `5a6a6d2`; see todo 311's archived file for
      its own AC evidence.
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

### 2026-08-17 - Subscriptions + notifications list implemented (advisor-scoped)

- Advisor consult confirmed the todo's own Recommended Action ordering was a
  real dependency chain, not just style: push-tap routing depends on the
  list's navigation target AND is the one AC blocked by the gated todo 286
  (iOS APNs). Split it to **todo 311**, re-pointed (not checked off) above,
  and shipped the other two slices here.
- **Backend read (no backend changes)**: `TopicSubscriptionView` (idempotent
  POST/DELETE), `NotificationListView`/`NotificationUnreadCountView`/
  `NotificationMarkReadView` (`api/notifications.py`,
  `api/subscriptions.py`), `NotificationSerializer` fields
  (`id, verb, actor, topic, post_id, created_at, read_at`). Confirmed the
  actual `Notification.verb` wire values via
  `models/notifications.py::NotificationVerb` are `reply` | `mention` |
  `solution` — NOT the `reply_added`/`answer_accepted` keys in
  `notification_copy.py` (that table is keyed by a separate Celery
  task-event-name namespace, not the model's `verb` field). The mobile copy
  renderer switches on the real model values.
- **New**: `forum_notification.dart` (`ForumNotification`,
  `ForumNotificationTopicRef` — a flat topic ref, distinct from
  `ForumTopicBoardRef`, mirroring `NotificationSerializer.get_topic`'s flat
  shape). `forum_notifications_screen.dart` (list, load-more, mark-all-read,
  tap-to-open — mirrors the web bell's copy rendering, a deliberate third
  copy home per that file's own header comment, since the client can't
  import a Python table).
- **Changed**: `ForumApi`/`HttpForumApi` gained
  `subscribeToTopic`/`unsubscribeFromTopic`/`fetchNotifications`/
  `fetchUnreadNotificationCount`/`markNotificationsRead`. `topicDetail`
  converted from a plain function provider to a class-based `TopicDetail`
  notifier (same generated `topicDetailProvider` name, so both existing call
  sites needed no changes) so it could gain `toggleSubscription()` — writes
  back the server's returned `subscribed` state, never a local optimistic
  flip (mirrors `TopicPosts.toggleReaction`'s write-back-from-response
  discipline), and rethrows on failure (unlike the fire-and-forget reaction
  toggle) so the thread screen can show an error SnackBar. New
  `NotificationsFeed` (cursor pagination via the same `PagedList`/verbatim-URL
  idiom as `BoardTopics`/`TopicPosts`) and `unreadNotificationCount`
  providers. `forum_thread_screen.dart` gained a bell icon-button AppBar
  action; `forum_screen.dart` gained a `Badge`-wrapped bell button
  navigating to the new `/forum/notifications` route.
- Mutation-tested the one safety-critical point: temporarily made
  `toggleSubscription` optimistically flip local state before the API call
  (no rollback on failure) — the "failed toggle leaves state unchanged" test
  went red with `Expected: false, Actual: <true>`, confirming the test
  actually exercises the write-back discipline. Reverted; re-verified green.
- Verification:

  ```
  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 0.9s)

  $ flutter test
  00:10 +252 ~3: All tests passed!
  ```

  252 passing (3 pre-existing skips, unrelated to this change; two
  pre-existing tests — `forum_screen_test.dart` and
  `forum_read_path_test.dart`'s "forum home lists boards" — needed an
  `authServiceProvider` override added, since `ForumScreen` now reads auth
  state for the bell button; fixed as part of this change, not a new gap).
- Known issue accepted at completion: the notifications-screen tap
  navigation and the bell-button navigation are exercised via
  `test/routing/app_router_test.dart` full-router integration tests (2 new),
  matching this codebase's existing sanctioned pattern for `context.pushNamed`
  call sites — there is no dio-mocking harness for `HttpForumApi` itself, so
  `fetchNotifications`'s absolute-cursor-URL handling is proven only via the
  Fake + provider layer (same boundary as `fetchPosts`/`fetchTopics`
  already ship with), not a live-HTTP-layer test.

### 2026-08-17 - Code review (1 finding, fixed)

- Dispatched `code-review-orchestrator` on the diff. One MEDIUM finding,
  verified against source (including a comparison against the web sibling
  `NotificationBell.tsx`):
  - **MEDIUM** — `_openNotification` `await`ed `markRead(id: ...)` *before*
    navigating, with no try/catch. Since the row's `onTap` is a
    fire-and-forget `VoidCallback`, a transient mark-read failure threw
    before `context.pushNamed('forumTopic', ...)` ever ran, silently
    breaking the row's primary action (open the topic) with zero user
    feedback — while every other mutating action added in this diff
    (`_toggleSubscription`, `_LoadMoreButton`) already wraps its call in
    try/catch. The web bell treats mark-read as explicitly best-effort
    (fires unawaited, swallows the error, navigates regardless). **Fixed**:
    `_openNotification` now wraps `markRead` in try/catch and navigates
    unconditionally afterward (best-effort, matching the web sibling); "Mark
    all read" now wraps in try/catch + SnackBar, matching
    `_LoadMoreButton`'s existing pattern in the same file. Added
    `FakeForumApi.failMarkReadWith` (mirrors the existing
    `failSubscriptionWith` idiom) and a new full-router regression test,
    "a failed mark-read does not block opening the topic (todo 293)".
    Mutation-tested: reverted to the blocking `await` with no try/catch,
    confirmed the new test goes red (`Found 0 widgets with type
    "ForumThreadScreen"` — navigation blocked, the exact original symptom),
    reverted to the fix, re-verified green.
- 8 non-issues confirmed by the reviewer (backend-contract field-by-field
  cross-check, the `topicDetail` function→Notifier conversion's call-site
  compatibility, cache-header/stale-badge safety, etc.) — no further action.
- Verification after repair:

  ```
  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 1.3s)

  $ flutter test
  00:09 +253 ~3: All tests passed!
  ```

### 2026-08-30 - Reconciled and closed out

- Local `main` in this checkout had drifted 25 commits behind `origin/main`
  across several intervening sessions — the 2026-08-17 work above merged
  cleanly (PR #556, `ad2ad98`) and stayed merged, but the todo file itself
  was never reconciled/archived against the synced state.
- Re-verified AC1–3 directly against the current working tree (not just the
  original commit) via three parallel Explore agents:
  - **AC1** (subscribe toggle): `forum_thread_screen.dart:40,46-55` +
    `forum_providers.dart::TopicDetail.toggleSubscription()` (lines 98-108)
    — writes back the server's `subscribed` flag, rethrows on failure.
    Covered by `forum_read_path_test.dart:134` (unsubscribed→subscribed,
    widget layer) and `forum_providers_test.dart:236-298` (both directions
    + failure-rethrow, provider layer).
  - **AC2** (absolute-cursor pagination): `forum_api.dart:261-271`'s
    `fetchNotifications({cursorUrl})` passes the cursor straight to `get()`,
    never re-prefixed. Two independent tests
    (`forum_notifications_screen_test.dart:59-82`,
    `forum_providers_test.dart:331-354`) assert this against a
    `https://api/forum/notifications/?cursor=p2` absolute fixture URL, with
    `FakeForumApi` recording the raw arg so a re-prefixing regression would
    genuinely fail the assertion.
  - **AC3** (unread badge clears): `NotificationsFeed.markRead()`
    (`forum_providers.dart:360-391`) invalidates
    `unreadNotificationCountProvider` after splicing rows read. The
    count-provider behavior itself is tested
    (`forum_providers_test.dart:356-419`, both single-id and mark-all
    paths); no widget test directly pumps the bell `Badge` to assert its
    rendered label, a one-line low-risk gap left as-is.
  - Confirmed no later commit (`5a6a6d2` todo 311, `02403ef` todo 317) has
    touched the subscribe-toggle or mark-read-on-tap logic — both are
    additive elsewhere in the same files.
- **AC4 checked off**, not left re-pointed: todo 311 (its destination) has
  itself reached `completed` (PR #573, `5a6a6d2`, verified present and
  intact in the current working tree — see its own archived file for
  evidence). Per `CLAUDE.md`'s Review Doc Tracking convention, a re-pointed
  item stays unchecked only while its destination is still open; once the
  destination ships, the source reference is checked off citing it.
- Fresh verification on this reconciliation branch (`origin/main` +
  nothing else — no application code changes):

  ```
  $ flutter test
  00:58 +420 ~3: All tests passed!

  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 1.9s)
  ```

## Notes

p3. Promoted from todo 279 on 2026-07-31. Subscriptions + notifications list
shipped 2026-08-17 (PR #556); push-tap routing split to todo 311
(advisor-scoped, real todo-286 blocker), shipped 2026-08-29 (PR #573 merged
2026-08-29T02:38:23Z — implemented well after the split, not on the split
date itself). Both confirmed merged and archived 2026-08-30. Related: todo
286 (iOS APNs entitlement — blocks push actually arriving on a distributed
iOS build).
