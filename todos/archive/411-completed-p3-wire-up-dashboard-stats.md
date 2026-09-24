---
status: completed
priority: p3
issue_id: "411"
tags: [backend, web, users]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire `me/dashboard-stats/` into the profile page

## Problem

`GET /api/v1/auth/me/dashboard-stats/` (about 150 LOC; 3 tests in
`test_dashboard_stats.py`) returns plant-ID and forum aggregates, but no screen
shows them. The owner decided (todo 405) to wire it up.

The web `/profile` page became editable in PR #798 and is the natural home.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Check the payload against what the profile page should show. Some
   aggregates read `PlantIdentificationResult`, which nothing writes (todo
   405). Drop or replace those fields.
2. Render a stats section on `/profile`, with tests.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [x] The profile page shows the stats and has tests.
- [x] No field depends on a table nothing writes.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Done: forum-only payload, stats section on /profile

**What the payload read, and what was dropped.** The view never read
`PlantIdentificationResult` (todo 405's note was imprecise). It read
`PlantIdentificationRequest` and `SavedCareInstructions`. A grep of
`backend/apps` and `backend/packages` (tests, migrations and admin excluded)
finds exactly one writer of each: `UserDemoDataService._create_demo_identifications`
(`apps/users/services.py`). That seeder imports `apps.common.models` and
`IdentificationResult`, neither of which exists, so it raises before any
write (todo 412). Nothing sets `status="identified"`. So every plant value was
a permanent zero, and these were removed from `dashboard_stats`:

- `plant_stats` (all four keys);
- the `plant_identification` entries in `recent_activity` (they also linked
  to `/identify/<uuid>`, which is not a web route);
- `total_activity_score`. Two of its four terms were plant terms, and its
  weights had no owner definition, so it was dropped rather than redefined.

No client consumed any of them (repo grep of `.dart`/`.ts`/`.tsx`). The
payload is now `{forum_stats, recent_activity}`. The two sliced lists gained a
`-pk` tie-break (`docs/rules/database.md`). Now stale but left alone:
`backend/docs/patterns/performance/query-optimization.md` and
`backend/docs/performance/n-plus-one-elimination.md` still quote the plant
aggregation as an example.

**Web.** `fetchDashboardStats()` in `profileService.ts` guards the shape at the
fetch boundary and passes on only the typed forum fields. Activity items must
be `forum_topic`/`forum_post` with a `/forum/` path, so a stray plant item
(from an older server) never reaches the page. The new
`components/profile/ProfileStats.tsx` renders on `/profile`, keyed on
`user?.id`. It has two `StatCard`s (Topics, Posts, each with its 30-day
count) and a recent-activity list (`Link` + `Timestamp`). It also has
loading, error (`role="alert"`) and empty ("Visit the forum") states. It
loads independently of the profile form, so a stats failure never blocks
editing. `ProfilePage.test.tsx` now renders inside a `MemoryRouter` and mocks
`fetchDashboardStats`.

**Tests.** Web: 4 new in `profileService.test.ts` (endpoint and cookies,
plant fields and unknown types dropped, bad shape rejected, server message
surfaced); 4 in the new `ProfileStats.test.tsx` (loading then stats and
links, error, empty, legacy plant payload not rendered; these use the real
service over a mocked `fetch`); and 2 new in `ProfilePage.test.tsx` (section
renders; form still usable when only the stats fail). All were red before
the code existed. Backend: 2 new in `test_dashboard_stats.py`.
`test_payload_carries_no_plant_fields` creates an identified
`PlantIdentificationRequest` and asserts the key set is exactly
`{forum_stats, recent_activity}`. `test_query_count_is_constant` asserts
`assertNumQueries(4)`. **Backend tests were written but not run here** (the
shared test DB was owned by another process). The orchestrator runs them.
The 4 is predicted from the garden_calendar `force_authenticate` precedent,
not measured.

**Mutations (web; each restored from a `cp` backup).** All 12 went red:
dropping the activity filter, the type allowlist, the `/forum/` guard or the
shape check; passing the body through; using the wrong endpoint; not
rendering the error state, the loading state or the empty state; the wrong
link target; the wrong month sublabel; and the page omitting the section.

**Commands.** `npx vitest run` on the 3 touched files: 19/19 passed. The full
`npx vitest run`: 103 files, 1406 tests, all passed. `npm run type-check`,
`npm run lint` and `npm run check:classes` (134 files, 5764 tokens) were all
clean.
