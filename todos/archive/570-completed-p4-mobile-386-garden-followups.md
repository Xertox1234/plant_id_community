---
status: completed
priority: p4
issue_id: "570"
tags: [mobile, backend, garden-calendar, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "#8: keep the 10-page cap and show a 'list truncated' notice when it is reached. #14: add a real two-transaction TransactionTestCase that pins the select_for_update lock, despite the testing.md constraint (2026-10-11)"
---

# Follow-ups from PR #998 (todo 386, mobile Care Schedule garden)

## Problem

PR #998 (todo 386, the mobile Care Schedule garden) left the engine after round 1 (a Land-side
criteria-text false positive) and was finished by hand with the owner's approval: a race-fix round and a
final round. The two blocking findings of those rounds were fixed on the PR (atomic complete/skip with
in-flight buttons; a late skip dated from the skip). The round-1 non-blocking findings still open on the PR
head and the hand review's non-blocking ones are below; 5 more round-1 locations were dropped by the
engine's cap of 10. Line numbers are as of the PR head; re-check against main before acting.

## Findings

1. **medium** `plant_community_mobile/lib/features/garden/garden_screen.dart:28` RefreshIndicator wraps ListViews (error state and short/empty _GardenList) with default physics. When content is shorter than the viewport the list does not scroll, so pull-to-refresh never fires, including on the error screen.
2. **medium** `plant_community_mobile/lib/features/garden/providers/garden_provider.dart:10` gardenRetry (4xx fails fast, else default backoff) is new behaviour with no test. Deleting the 4xx branch leaves the suite green; the load-failure test uses a fake and cannot show retry timing.
3. **medium** `plant_community_mobile/test/services/push_message_router_service_test.dart:57` Care-reminder push tests only cover a signed-in tap. A signed-out tap, where the protected-route redirect should send the user to login, is not tested. Cold start also has no case where the garden fetch fails.
4. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:556` The task title is the type label plus the plant name. The plant name can be up to 200 chars and CareTask.title max_length is 200, so scheduling care for a long-named plant 400s with a generic 'That did not work'.
5. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:371` _run catches only ApiException. Any other error (e.g. a TypeError from a response cast) escapes onPressed unhandled: no snackbar and no refresh. Double-tapping Done or Skip also fires two requests, so the second 400s and shows 'That did not work' after the action succeeded.
6. **low** `plant_community_mobile/lib/services/push_message_router_service.dart:836` A warm-resume care push always does router.push('/garden'), so a push tapped while the garden is already open stacks a duplicate GardenScreen.
7. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:392` The task title is built as `<type label> <plant.commonName>`. common_name allows 200 chars and CareTask.title is max_length=200, so a plant name over about 184 chars makes every task create fail with a 400, which the user sees only as 'That did not work'.
8. **low** `plant_community_mobile/lib/features/garden/services/garden_api_service.dart:66` _all silently stops after 10 pages (200 rows). An account with more pending tasks than that sees a cut-off due list and wrong per-plant counts, and nothing tells the user.
9. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:135` _busy clears as soon as the request returns, before gardenProvider finishes refetching, so a finished task's Done/Skip are briefly enabled again; a second tap 400s and shows 'That did not work' for a task that did complete. Keep_busy true after a success.
10. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:425` The due time is local midnight + Duration(hours: 9), so on DST-change days it lands at 08:00 or 10:00; and 'First due' today can already be past 9 am. Use DateTime(y, m, d, 9) and clamp to the future.
11. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:36` onRefresh is `() async => ref.invalidate(gardenProvider)`, so the spinner stops before the reload finishes. Use `ref.refresh(gardenProvider.future)`.
12. **low** `plant_community_mobile/lib/features/garden/services/garden_api_service.dart:83` fetchPendingTasks does not filter out tasks of inactive plants (fetchPlants filters is_active=true, the reminder sweep filters plant__is_active), so an archived plant's tasks still show under DUE CARE.
13. **low (hypothesis, not verified)** `plant_community_mobile/lib/services/push_message_router_service.dart:219` authRestoreSettled treats firebaseUser == null as settled. If the platform has not restored the Firebase user yet at a cold start from a care push, the wait returns at once and a signed-in user lands on /login.
14. **low** `backend/apps/garden_calendar/tests/test_models.py:439` The race tests are sequential (stale instances / mocked get_object). Dropping select_for_update() but keeping the pending check would still pass them; only a two-transaction test (TransactionTestCase is constrained by docs/rules/testing.md) would pin the lock.
15. **low** `backend/apps/garden_calendar/models.py:1260` _create_next_occurrence builds the next task from the instance the view fetched before the lock, so a PATCH to recurrence_interval_days committed in between is ignored. Pre-existing.
16. **low** `backend/apps/garden_calendar/api/views.py:1563` Cleanup: the views run the refusal check before calling the model and again after AlreadyResolved; one path through the except would do.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Mobile garden (`plant_community_mobile/lib/features/garden/`): #1 both ListViews set `AlwaysScrollableScrollPhysics` (tests pull a short list and the error state; the tests showed pull-to-refresh already worked because a primary vertical ListView defaults to that physics, so this makes it explicit rather than inferred); #11 `onRefresh` awaits `ref.refresh(gardenProvider.future)`; #5 `_run` catches any error (snackbar, list still reloads); #9 `_run` completes only after the reload, so Done/Skip stay disabled until the list drops the finished task; #4/#7 `careTaskTitle` caps the title at 200; #10 `firstDueAt` builds 9 am from the date fields and clamps a past time to now. Each has a test that fails with the fix reverted.
- #8 (owner decision 2026-10-11): the 10-page cap stays; `GardenList.truncated` reports a `next` left unread and the screen shows a 'List truncated' notice (`garden_api_service_test.dart`, widget tests). #12: `plant__is_active` is now a care-task filter (`backend/apps/garden_calendar/api/views.py`) and the app sends it. #2: `garden_provider_test.dart` pins `gardenRetry`. #3: tests for a signed-out warm tap (lands on login) and a cold start whose garden fetch fails (error + Retry). #6: a warm tap while `/garden` is on top no longer pushes a second one.
- Backend: #14 (owner decision 2026-10-11, overriding docs/rules/testing.md) `CareTaskResolveLockTest` is a real two-transaction `TransactionTestCase`; it fails with `select_for_update` removed from `CareTask._resolve`. #15 `_resolve` reloads the whole row under the lock (`refresh_from_db(from_queryset=...select_for_update())`), so a committed recurrence PATCH is used (`test_the_next_occurrence_uses_the_recurrence_as_committed`). #16 the views drop the duplicate pre-check; `AlreadyResolved` is the one refusal path.
- #13 declined, checked against the plugin source: firebase_auth 6.5.4 seeds `currentUser` from the `APP_CURRENT_USER` plugin constant that `Firebase.initializeApp()` collects (iOS `FLTFirebaseAuthPlugin.m:326`, Android `FlutterFirebaseAuthPlugin.java:742`, read in `FirebaseAuthPlatform.instanceFor`), before `runApp`, so a persisted user is non-null when `AuthService.build` runs on a cold start. Web, where restore is async, is not a target.
- The `GardenApi` fetches now return `GardenList`, so the test fake (`test/features/garden/support/garden_test_support.dart`) and the existing `HttpGardenApi` tests changed with it; the recording `ApiService` moved into that support file.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest apps/garden_calendar/tests/test_models.py apps/garden_calendar/tests/test_viewsets.py --create-db -q -p no:cacheprovider && cd plant_community_mobile && flutter test --no-pub -r expanded test/features/garden test/services/push_message_router_service_test.dart'` — evidence `.sweep-evidence/g8/570-ac0.txt` (not committed), last lines:

  ```text
  00:01 +51: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases a moderation_decided-shaped payload (no post_id key) routes to the topic without a postId query param
  00:01 +52: plant_community_mobile/test/services/push_message_router_service_test.dart: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  00:01 +53: plant_community_mobile/test/services/push_message_router_service_test.dart: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  00:01 +54: All tests passed!
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
