---
status: pending
priority: p2
issue_id: "318"
tags: [web, api, plant-identification, bug]
dependencies: []
---

# plantIdService.saveToCollection() calls a dead route — Identify→Garden save is broken in production

## Problem

`saveToCollection()` in `web/src/services/plantIdService.ts` fetches
`/api/v1/users/collections/` to find the user's default collection before
saving an identified plant. That path does not exist — there is no
`/api/v1/users/` mount at all. It resolves to Wagtail's page-serving
catch-all (`wagtail_serve`), not a collections endpoint, so the request
effectively 404s (as an HTML page, not a JSON error) and every "Save to My
Collection" click on the Identify page fails. This severs the entire
Identify → Garden save flow in production.

## Findings

- `web/src/services/plantIdService.ts:109` —
  `` `${API_BASE_URL}/api/${API_VERSION}/users/collections/` ``, called
  from `saveToCollection()` (line 103).
- `backend/apps/users/urls.py:35` — the real view, `user_collections`
  (GET/POST), is registered at `me/collections/`, not `collections/` off a
  `users/` root.
- `backend/plant_community_backend/urls.py:124` and `:146` — `apps.users.urls`
  is mounted at `auth/`, so the real, working path is
  `/api/v1/auth/me/collections/`. There is no `path("users/", ...)` mount
  anywhere in the URL tree.
- Confirmed empirically via Django's URL resolver (`django.urls.resolve`):
  `resolve('/api/v1/users/collections/')` → `wagtail_serve`;
  `resolve('/api/v1/auth/me/collections/')` → `user_collections`.
- Confirmed independently twice during Canopy PR 4 (2026-08-16/17,
  `docs/superpowers/plans/2026-08-16-canopy-areas.md`): once by Task 8's
  implementer while writing `web/e2e/canopy-areas-authenticated.spec.js`
  (had to use the real route to seed a `UserPlant` fixture — see that
  file's doc comment), and again independently by the final whole-branch
  reviewer. Left unfixed both times as out of scope for those tasks (e2e
  spec / style-only branch, no application logic changes authorized).
- Pre-existing bug, not introduced by Canopy PR 4 (#558) — the branch only
  restyled `IdentifyPage.tsx`/`MyPlantsPage.tsx`, it didn't touch
  `plantIdService.ts`.

## Proposed Solutions

### Option 1: Fix the URL (Recommended)

- **Implementation:** Change line 109 to
  `` `${API_BASE_URL}/api/${API_VERSION}/auth/me/collections/` ``. One-line
  fix; the response shape `user_collections` returns (list of collections
  with `id`/`name`) already matches what `saveToCollection()` expects from
  `collections: Collection[]`.
- **Pros:** Minimal, matches the working route already exercised by
  `canopy-areas-authenticated.spec.js` and by manual collection-creation
  flows elsewhere in the app.
- **Cons:** None identified.
- **Effort:** ~15 minutes including a regression test.
- **Risk:** Low.

## Recommended Action

1. Fix `web/src/services/plantIdService.ts:109` to call
   `/api/v1/auth/me/collections/`.
2. Add or extend a unit/integration test for `saveToCollection()` that
   mocks the fetch and asserts it hits the corrected path (check
   `web/src/services/plantIdService.test.ts` if it exists; create one if
   not — this function currently has no direct test coverage, which is
   how the dead route went unnoticed).
3. Manually verify end-to-end: identify a plant, click "Save to My
   Collection," confirm it lands in `/my-plants` — this is also covered by
   `web/e2e/canopy-areas-authenticated.spec.js`'s Garden fixture seeding,
   but that test seeds via direct API call, not through the Identify UI's
   actual save button, so it would NOT have caught this bug. Consider
   whether a dedicated e2e test that clicks the real "Save" button (not a
   seeded fixture) belongs in this fix.

## Technical Details

- File: `web/src/services/plantIdService.ts:103-134` (`saveToCollection`)
- Dead route: `GET /api/v1/users/collections/` → `wagtail_serve` (Wagtail
  catch-all page-serving view)
- Correct route: `GET /api/v1/auth/me/collections/` → `user_collections`
  (`backend/apps/users/urls.py:35`, `backend/apps/users/views.py`)
- Mount chain: `backend/plant_community_backend/urls.py:124`/`:146` →
  `path("auth/", include("apps.users.urls"))` → `apps/users/urls.py`

## Acceptance Criteria

- [ ] `saveToCollection()` calls `/api/v1/auth/me/collections/`
- [ ] A test (unit or e2e-via-UI) exercises the real save button and fails
      before the fix, passes after
- [ ] Manual smoke test: identify → Save to My Collection → plant appears
      on `/my-plants`

## Work Log

### 2026-08-17 - Filed

- Filed by Claude following Canopy PR 4 (#558, merged 2026-08-17). Found
  and confirmed twice during that work (Task 8 implementer,
  final-review agent) but left unfixed as out of scope for a style-only
  branch. Recommended as a follow-up in the PR body; filing the actual
  todo was deferred past the merge and is done now.

## Notes

- p2 because it silently breaks a core user flow (not a crash, not
  data loss, but "Save to My Collection" simply does nothing useful) —
  bump to p1 if analytics or user reports confirm active usage of that
  button in production.
- Related: Canopy PR 4 / #558 (`docs/superpowers/plans/2026-08-16-canopy-areas.md`,
  `docs/superpowers/specs/2026-08-16-canopy-areas-design.md`).
