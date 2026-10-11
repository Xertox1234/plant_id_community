---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
