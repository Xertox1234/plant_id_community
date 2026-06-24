---
status: pending
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

- [ ] A decision is made (read surface vs. remove) and reflected in code.
- [ ] After the change, the web app has no user action that writes to a store it
      cannot read back (no write-only collection dead-end).
- [ ] Relevant tests updated (web service test for the removed/added path).

## Notes

- Filed from the todo-237 ("reconcile Firestore↔backend") investigation, which found
  the reconcile premise invalid and surfaced this separate, real issue. See archived
  todo 237 for the full source-of-truth decision.
