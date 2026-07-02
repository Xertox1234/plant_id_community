---
status: completed
priority: p3
issue_id: "243"
tags: [backend, web, api, dead-code, plant-collection]
dependencies: []
---

# Backend `UserPlant` collection is write-only — add a read surface or remove the dead write

## Problem

The web app lets users "Save to My Collection" after an identification, which writes
a `UserPlant` row to the Django backend. **No client ever reads that collection back.**
There is no web "My Plants" list page or route, no GET of the `…/plant-identification/plants/`
endpoint, and the mobile app never touches the backend collection (it uses Firestore).
So users save plants into a backend store they can never see — a confusing dead-end,
and `UserPlant`/`UserPlantCollection` are effectively write-only.

## Findings (from todo 237 investigation, 2026-06-24)

- Write path: `web/src/services/plantIdService.ts::saveToCollection`
  (`POST …/plant-identification/plants/`), triggered from
  `web/src/pages/IdentifyPage.tsx` and
  `web/src/components/PlantIdentification/IdentificationResults.tsx`
  ("Save to My Collection" button).
- No read path: no web route/page lists `UserPlant`s; no GET of `…/plants/` exists in
  `web/src/`. The backend `plants` viewset / `add_to_collection` action exist
  (`backend/apps/plant_identification/views.py`) but the real identify flow never
  creates the `PlantIdentificationResult` rows `add_to_collection` depends on (those
  appear only in demo-data seeding, `backend/apps/users/services.py:611`).
- Context: the mobile plant collection is Firestore-only and read by `CollectionScreen`
  (todo 224); the two collections are intentionally separate (decision recorded in
  archived todo 237).

## Proposed Solutions

### Option 1: Remove the dead write (Recommended if no near-term collection UI)

- Drop the web "Save to My Collection" button + `saveToCollection`, and (if otherwise
  unused) retire the backend `plants` create path. Eliminates the confusing dead-end.
- **Pros:** least code; no orphan writes. **Cons:** loses a latent feature if a web
  collection view is planned.

### Option 2: Add the missing read surface

- Build a web "My Plants" page that GETs the user's `UserPlant`s and renders them.
  Turns the existing write into a real feature.
- **Pros:** makes the save meaningful. **Cons:** new UI + endpoint wiring; only worth
  it if web collections are a product goal.

## Recommended Action

1. Decide with the owner whether a **web plant collection view** is on the roadmap.
2. If yes → Option 2 (add the read surface). If no → Option 1 (remove the dead write).
3. Either way, keep mobile (Firestore) and web/backend collections separate per the
   todo-237 decision unless cross-platform unification becomes a goal.

## Acceptance Criteria

- [x] A decision is made (read surface vs. remove) and reflected in code.
- [x] After the change, the web app has no user action that writes to a store it
      cannot read back (no write-only collection dead-end).
- [x] Relevant tests updated (web service test for the removed/added path).

## Notes

- Filed from the todo-237 ("reconcile Firestore↔backend") investigation, which found
  the reconcile premise invalid and surfaced this separate, real issue. See archived
  todo 237 for the full source-of-truth decision.

## Work Log

### 2026-07-02 - Started by completing-todos skill (run 2026-07-02-1727)

- Picked up by automated workflow.
- Owner decision (via /todo-next prompt): **Option 2 — build the web "My Plants" read
  surface** (a web plant-collection view IS wanted). Keeping mobile (Firestore) and
  web/backend collections separate per the todo-237 decision.

### 2026-07-02 - Implementation + verification (run 2026-07-02-1727)

**Changes (branch `feat/243-web-my-plants`):**

- Web read surface: `plantIdService.getMyPlants(page)` GETs
  `/api/v1/plant-identification/plants/?page=N` (DRF-paginated); new
  `MyPlantsPage` at `/my-plants` under `ProtectedLayout` (loading/error/empty/
  grid/pagination states, DiagnosisListPage idioms); nav links added in
  `UserMenu` (desktop dropdown) and `Header` (mobile auth section).
- Types: `UserPlant` gained read-only fields (`collection_name`,
  `display_name`, `image_thumbnail`); new `PaginatedUserPlants`.
- Backend: `UserPlantViewSet.get_queryset` now `select_related("user",
  "species", "collection", "from_identification_request")` — the serializer
  reads all four per row (N+1 on the list the page now uses).
- Tests: 6 new `getMyPlants` service tests, 7 new `MyPlantsPage` page tests,
  3 new backend tests (`tests/test_user_plant_api.py`: auth required,
  user-scoping, relative O(1) query-count).

**Verification evidence:**

- AC1 (decision reflected in code): Option 2 implemented — read surface above.
- AC2 (no write-only dead-end): the "Save to My Collection" write now has a
  read surface at `/my-plants` reading the same backend store.
- AC3 (tests updated): web suite
  `Test Files  43 passed (43) / Tests  585 passed (585)`; backend
  `102 passed, 1 warning in 26.87s` (full `apps/plant_identification`);
  new-file runs: `33 passed` (2 web files), `3 passed` (backend file).
- Query-count test proven non-hollow: with `select_related` stashed,
  `FAILED ...::test_list_query_count_constant_in_plant_count`; passes with it.
- `npm run type-check`: clean. `npm run lint`: 0 errors (1 pre-existing
  warning in generated `coverage/block-navigation.js`, unrelated).

### 2026-07-02 - Completed by completing-todos skill (run 2026-07-02-1727)

- Verification: all 3 acceptance criteria passed (evidence above).
- Review: code-review-orchestrator — 3 findings total, 0 blocking.
  MEDIUM (backend test didn't pin the response contract fields the web page
  renders) fixed in-run: `test_list_returns_only_own_plants` now asserts
  `display_name` / `image_thumbnail` / `collection_name` /
  `care_instructions_json` / `notes` / `created_at` presence
  (`3 passed` re-run).

#### Known issues

- LOW: `PAGE_SIZE = 20` hardcoded in `MyPlantsPage.tsx` mirrors the backend
  DRF page size; same pre-existing idiom as `DiagnosisListPage.tsx`
  ("Backend uses 20 per page"). If the backend page size ever changes, both
  pages need the constant updated — left as-is for house consistency.
