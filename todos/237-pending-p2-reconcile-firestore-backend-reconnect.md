---
status: pending
priority: p2
issue_id: "237"
tags: [mobile, firestore, sync, api]
dependencies: ["224"]
---

# Reconcile Firestore plant collection with the Django backend on reconnect

## Problem

An identified plant is written to **two independent stores** with no link between
them: the Django backend (during the identify API call) and Firestore (offline-first,
via `savePlant`). Nothing reconciles them when connectivity returns, so the two can
drift — a plant can exist in Firestore but not in the backend's record (or vice
versa), and the collection UI, which reads Firestore only, can disagree with the
backend.

## Findings

- `plant_community_mobile/lib/features/camera/camera_screen.dart`: `_identifyPlant`
  calls the backend `identifyPlant` (via `api_service`) **and** then
  `_persistPlantOffline(plant)` → `savePlant` to Firestore (fire-and-forget). Two
  writes, no shared id or reconciliation.
- `plant_community_mobile/lib/features/collection/collection_screen.dart` reads
  from Firestore only (`plantsStreamProvider`); the backend's identification
  records are never merged in.
- No connectivity-restored / sync-on-reconnect path exists in the mobile app.
- `firebase/firestore.rules` already reserves a `sync_queue` collection
  ("only backend can write", updated/deleted by cloud functions only — lines
  67–73), which suggests an intended server-side sync mechanism that is not yet
  wired to the plant collection.
- Discovered while wiring todo 224 (offline persistence); recorded as a follow-up
  in `todos/archive/224-completed-p2-wire-offline-persistence-firestore.md` and in
  project memory.

## Proposed Solutions

### Option 1: Firestore as source of truth, backend mirrors (Recommended)

- **Implementation:** the app writes only to Firestore; a Cloud Function (or the
  existing `sync_queue`) mirrors new/changed plant docs into the Django backend.
  On reconnect, the SDK flushes queued writes and the function fans them out.
- **Pros:** single client write path; offline-first stays simple; reconciliation
  is server-side and idempotent.
- **Cons:** requires a Cloud Function + backend ingest endpoint; backend is
  eventually-consistent with Firestore.
- **Effort:** hours–day.
- **Risk:** medium — needs idempotency keys to avoid duplicate backend records.

### Option 2: Backend as source of truth, Firestore as cache

- **Implementation:** on reconnect, pull the backend's identifications and
  upsert them into Firestore; treat the local Firestore copy as a cache.
- **Pros:** backend stays authoritative (matches web app / garden calendar).
- **Cons:** more client-side reconcile logic; offline writes still need a queue to
  reach the backend.
- **Effort:** hours–day.
- **Risk:** medium.

## Recommended Action

1. Decide the source of truth (lean Option 1 — Firestore-first with a backend
   mirror) and document it.
2. Add a reconnect trigger (e.g. a `connectivity_plus` listener, or react to
   `hasPendingWrites` clearing) that runs a reconciliation pass.
3. Reconcile by stable plant id so the operation is **idempotent** — no duplicate
   records on either side after repeated runs.
4. Add an integration test (fake or emulator) asserting a plant saved while offline
   appears in the backend after reconnect + reconcile, with no duplicates.

## Technical Details

- Two write sites today:
  `plant_community_mobile/lib/features/camera/camera_screen.dart`
  (`_identifyPlant` → backend `identifyPlant`; `_persistPlantOffline` →
  `firestoreServiceProvider.savePlant`).
- Read site: `plant_community_mobile/lib/services/firestore_service.dart`
  (`getPlantsStream` → `plantsStreamProvider`).
- Backend API client: `plant_community_mobile/lib/services/api_service.dart`.
- Reserved sync surface: `firebase/firestore.rules` `sync_queue` (lines 67–73).
- Relevant patterns: `plant_community_mobile/docs/patterns/firebase-auth.md`,
  `firebase/docs/patterns/cloud-functions.md` (idempotency, cold starts).

## Acceptance Criteria

- [ ] A documented decision on the source of truth (Firestore-mirror vs
      backend-authoritative) lands in the relevant pattern doc or this todo.
- [ ] A reconciliation pass runs when connectivity is restored.
- [ ] An integration test asserts a plant saved offline is present in the backend
      after reconnect + reconcile.
- [ ] The reconcile is idempotent: running it twice produces no duplicate records
      on either store — asserted by the test.

## Work Log

### 2026-06-22 - Filed

- Created from a todo-224 implementation follow-up (Firestore↔backend drift). Not
  yet started.

## Notes

- Priority p2 (above the sibling test-coverage follow-up 236): this is a real
  data-consistency gap that can surface user-visible drift between the mobile
  collection and the backend, not just a missing test. Downgrade to p3 if the
  backend collection is confirmed not user-facing.
- Related: todo 236 (emulator round-trip test) and archived todo 224.
