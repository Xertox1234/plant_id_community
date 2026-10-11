---
status: completed
priority: p3
issue_id: "386"
tags: [mobile, flutter, dead-code]
dependencies: []
source_review: "todos/384-mobile-navigation-shell-missing"
triage: blocked-device
triaged: 2026-10-10
owner_decision: "Owner: ship the care-guide + garden code now; AC4 (on-device FCM check of a due CareTask push) split into its own todo, re-pointed in the triage PR (2026-10-10)"
blocked_on: "AC4: on-device FCM check that a due CareTask fires a push. All the code (the care-guide slice and the garden slice) can ship first."
---

# `/garden` is dead code and `/care` is a stub that promises navigation

## Problem

Two mobile surfaces look finished from the route table and are not.

### 1. `garden` — 918 lines of models nothing references

`AppRoutes.garden` renders `PlaceholderScreen(title: 'Garden')`. Behind it,
`lib/features/garden/models/` holds five files — `GardenBed`, `GardenPlant`,
`CareTask`, `WeatherData`, plus a barrel — each documented as mapping to
`backend/apps/garden_calendar/models.py`.

Verified during todo 384: grepping `GardenBed|GardenPlant|CareTask|WeatherData`
across `lib/` **excluding** `lib/features/garden/models/` returns **zero hits**,
and zero across `test/`. No screen, provider, service, widget or test. The five
files reference nothing but each other.

It is deliberately **not** a shell destination — there is nothing to show — and
carries a documented entry in the reachability checker's `ALLOWED_ORPHANS`.
Remove that entry when the feature lands.

### 2. `care` — a chevron that does nothing

`CareScreen` (`lib/features/care/care_screen.dart`) says so itself at `:5-6`:
*"Plant care guides hub (stub)"*. It renders four hardcoded category cards and
the footer "Full care guides coming soon".

`_CategoryCard` (`:107-138`) builds a `ListTile` with
`trailing: Icon(Icons.chevron_right)` at `:135` and **no `onTap`**. So it
renders the standard affordance for "this navigates" and does nothing when
tapped. It is reachable from the Home feature grid, so users will hit it.

## Recommended Action

Independent, either order:

1. **Care** (small): either drop the chevron so the cards stop promising
   navigation, or build the guides behind them. Dropping it is honest and
   costs one line.
2. **Garden** (large): build the garden-calendar feature against
   `apps/garden_calendar`, or delete the five model files and the `/garden`
   route. Do not leave it as-is — a route to a placeholder is exactly the
   declared-but-unreachable shape todo 384 was filed about.

## Acceptance Criteria

- [x] `care`'s cards either navigate or stop showing a chevron
- [x] `garden` is either built and wired into the shell, or removed along with
      its route, its models and its `ALLOWED_ORPHANS` entry
- [x] `python3 scripts/check_flutter_route_reachability.py` still exits 0
- [ ] A CareTask created in the mobile garden fires an FCM push when it falls due, verified end to end on a device (moved from todo 410 AC 1). → todo 547 (re-pointed 2026-10-10; owner: split the device check out)
- [x] Tapping a `care_task_due` push opens the garden (today the push router
      ignores a payload without `topic_id`).
- [x] `GardenPlant.gardenBed` is nullable: the API returns `null` for a
      bedless plant (todo 457 item 8).

## Notes

p3 for garden (invisible to users — unreachable), but the `care` chevron is a
live papercut on a reachable screen and is a one-line fix.

### 2026-09-23 - Backend decision from todo 405: calendar KEEP, garden REMOVED

The owner decided in todo 405 that `apps.garden_calendar` is **kept** ("still
fairly useful"). So this todo's choice is now **build**, not "build or delete":
the mobile `/garden` feature is built against `/api/v1/calendar/api/*`.

- `apps.garden`, the separate outdoor garden planner, was **removed** in todo
  405 slice 1.
- Scope note for Houseplant MD: `garden_calendar` is outdoor-shaped in places
  (GardenBed, Harvest, GrowingZone, WeatherAlert, `OPENWEATHER_API_KEY`). The
  houseplant core is CareTask, CareLog and reminders. Decide which models the
  mobile screens need before wiring a bed or hardiness-zone picker into a
  houseplant app.

## Work Log

### 2026-09-24 - Owner decisions: houseplant-core garden; care guides from the CMS (gate removed)

Decided by the owner:

- **Garden:** build only the houseplant core of `garden_calendar` — CareTask,
  CareLog and reminders (reminders delivery is todo 410). No garden beds,
  harvests, hardiness zones or weather.
- **Care:** BUILD the guides (not "drop the chevron"). Each card opens guide
  content from **Wagtail blog posts** in the CMS (a post, or a tag/category
  listing), so guides are editable without an app release. Content comes from
  todo 445 (AI-drafted care articles the owner spot-checks).
Ready for a sweep (garden and care can be separate slices).

### 2026-09-26 - Owner decision: garden_calendar is the one model (see todo 410)

The mobile garden is built on `garden_calendar` `Plant` / `CareTask` /
`CareLog`, with no beds. Todo 410 adds `Plant.owner`, makes `garden_bed`
nullable, and turns CareTask due dates into FCM reminders. So this todo's
garden slice comes **after** 410. `users.CareReminder` is deleted in 410; do
not build on it. The care-guide cards list Wagtail blog posts tagged
`care-guide` (drafts from todo 445).

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- **Care:** each category card now opens the CMS care guides
  (`/blog?tag=care-guide`, titled "<Category> guides"); the "coming soon"
  footer is gone. The CMS has one `care-guide` tag, not one per category,
  so all four cards open the same list.
- **Garden:** built on the houseplant core of `garden_calendar` — a
  `GardenScreen` ("Care Schedule") listing pending care tasks (Mark done /
  Skip; done also writes a CareLog) and the user's plants (Add plant,
  Schedule care with a repeat). `GardenApi` + `gardenProvider` back it.
  `GardenBed`/`WeatherData` models and `PlaceholderScreen` are deleted.
- **Wiring:** `/garden` moved into the Home shell branch (auth-only), with a
  Home feature-grid card; its `ALLOWED_ORPHANS` entry is removed and the
  reachability checker still exits 0.
- **Push:** a tapped `care_task_due` push (no `topic_id`) now opens the
  garden, on warm resume and cold start.
- **Model:** `GardenPlant` was rewritten to the list payload;
  `gardenBed` is `String?` (todo 457 item 8). AC 4's device check is todo 547.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `cd plant_community_mobile && flutter test test/features/care/care_screen_test.dart` — evidence `.sweep-evidence/g1/386-ac0.txt` (not committed), last lines:

  ```text
  00:00 +1: eyebrow CARE GUIDES present
  00:00 +2: no coming-soon notice: the guides exist
  00:00 +3: every card shows a chevron AND navigates to the care guides
  00:00 +4: no crashes on pump
  00:00 +5: All tests passed!
  ```

- AC 2: `grep -n "GardenScreen\|AppRoutes.garden" plant_community_mobile/lib/core/routing/app_router.dart plant_community_mobile/lib/features/home/home_page.dart && cd plant_community_mobile && flutter test test/features/garden test/routing` — evidence `.sweep-evidence/g1/386-ac1.txt` (not committed), last lines:

  ```text
  00:03 +67: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests my forum photos redirects a signed-out user to login (todo 374)
  00:03 +68: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests the profile tab is reachable signed out and gates itself (todo 384)
  00:03 +69: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests Should allow authenticated user to access protected route
  00:03 +70: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests Should redirect authenticated user away from login screen
  00:03 +71: All tests passed!
  ```

- AC 3: `python3 scripts/check_flutter_route_reachability.py` — evidence `.sweep-evidence/g1/386-ac2.txt` (not committed), last lines:

  ```text
  settings             /settings                yes         profile_screen.dart

  PREFIX (not a destination): forumGroups = '/forum/groups'
      guard prefix for /forum/groups/:id (todo 350); not a destination -- both children (/new, /:id) are registered, and no group-list screen exists (groups are folded into ForumConversationsScreen)
  All 20 routes are reachable.
  ```

- AC 5: `cd plant_community_mobile && flutter test test/services/push_message_router_service_test.dart` — evidence `.sweep-evidence/g1/386-ac4.txt` (not committed), last lines:

  ```text
  00:00 +4: PushMessageRouterService payload edge cases a moderation_decided-shaped payload (no post_id key) routes to the topic without a postId query param
  00:00 +5: PushMessageRouterService payload edge cases an unparseable topic_id does not navigate at all (silent no-op, not a crash)
  00:00 +6: pushBackgroundMessageHandler completes without throwing
  [PUSH] Background message received: {topic_id: 42}
  00:00 +7: All tests passed!
  ```

- AC 6: `grep -n "final String? gardenBed" plant_community_mobile/lib/features/garden/models/garden_plant.dart && cd plant_community_mobile && flutter test test/features/garden/garden_screen_test.dart --plain-name "gardenBed is null"` — evidence `.sweep-evidence/g1/386-ac5.txt` (not committed), last lines:

  ```text
  141 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading plant_community_mobile/test/features/garden/garden_screen_test.dart
  00:00 +0: models a bedless plant parses: gardenBed is null (todo 457 item 8)
  00:00 +1: All tests passed!
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-10 - Repaired by the todo sweep (run 2026-10-11-0053)

- **Cold-start care tap:** a tap that launched the app pushed the protected
  `/garden` before the launch JWT exchange finished, so the redirect sent a
  signed-in user to `/login` (then `/profile`). It now waits for the session
  restore to settle (`waitForAuthRestore`, 15 s cap) before routing; a new
  test starts mid-restore and fails without the wait.
- **Skip ends the schedule:** `CareTask.mark_skip` never scheduled the next
  occurrence, so skipping a weekly watering in the new garden UI ended it.
  It now schedules it exactly as `mark_complete` does, and both views report
  `next_occurrence_created` from what actually happened (it was
  `is_recurring`, wrong for a past-end-date task). Model and API tests cover
  recurring, one-off and past-end skips.
