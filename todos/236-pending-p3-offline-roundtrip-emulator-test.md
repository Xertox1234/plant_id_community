---
status: pending
priority: p3
issue_id: "236"
tags: [mobile, testing, firestore, offline]
dependencies: ["224"]
---

# Emulator-backed offline→online round-trip test for Firestore sync

## Problem

The offline→online *transition* — the Firestore SDK queuing a write while offline
and flushing it to the server on reconnect — has no automated test. The current
integration suite runs the real `FirestoreService` against an in-memory
`FakeFirebaseFirestore`, which has no network layer, so it can verify "a saved
plant is continuously readable from the local store" but cannot exercise a literal
write-queue flush across a reconnect. That round-trip is exactly the behavior the
offline feature promises, and it is currently unverified.

## Findings

- `plant_community_mobile/test/integration/offline_sync_test.dart` documents the
  gap in its own header comment: the fake is always an in-memory store with no
  network, so the queue-flush round-trip "is not reproducible in-process … A
  literal network round-trip would require the Firebase emulator."
- The `data persisted before reconnect is still present afterward` test there is a
  stand-in (before/after read from the same persisted store), not a real
  offline→online transition.
- `PlantsSnapshot` already exposes the metadata a real test would assert on
  (`isFromCache`, `hasPendingWrites`) — see
  `plant_community_mobile/lib/services/firestore_service.dart`.
- Discovered while wiring todo 224 (offline persistence); recorded as a follow-up
  in `todos/archive/224-completed-p2-wire-offline-persistence-firestore.md` and in
  project memory.

## Recommended Action

1. Add a Firebase **Firestore emulator** config (an `emulators` block in
   `firebase.json`, or reuse an existing emulator setup) and a script to start it.
2. Write a Flutter `integration_test` (not a widget/unit test) that:
   - points `FirebaseFirestore.instance` at the emulator,
   - calls `disableNetwork()`, then `savePlant(uid, plant)`,
   - asserts the snapshot is readable with `hasPendingWrites == true` /
     `isFromCache == true`,
   - calls `enableNetwork()`, waits for `hasPendingWrites` to flip to `false`,
   - asserts the document is present server-side (independent emulator read).
3. Gate it so the default `flutter test` run stays green without the emulator
   (skip/guard when `FIRESTORE_EMULATOR_HOST` is unset). Optionally wire an
   emulator job into CI as a separate, non-blocking gate.

## Technical Details

- Toggle connectivity with `FirebaseFirestore.instance.disableNetwork()` /
  `enableNetwork()`.
- Assert on `DocumentSnapshot`/`QuerySnapshot` `.metadata.hasPendingWrites` and
  `.isFromCache`, surfaced through `PlantsSnapshot` in
  `plant_community_mobile/lib/services/firestore_service.dart`
  (`getPlantsStream` → `plantsStreamProvider`).
- Existing fake-based tests stay as the fast default suite:
  `plant_community_mobile/test/integration/offline_sync_test.dart`,
  `plant_community_mobile/test/services/firestore_service_test.dart`.
- Relevant patterns: `plant_community_mobile/docs/patterns/firebase-auth.md`.

## Acceptance Criteria

- [ ] An emulator-backed integration test saves a plant while the network is
      disabled and asserts it is readable from cache with `hasPendingWrites == true`.
- [ ] The same test re-enables the network, waits for `hasPendingWrites` to become
      `false`, and asserts the document reached the emulator server via an
      independent read.
- [ ] The test is emulator-gated (skipped when the emulator env var is absent), so
      `flutter test` with no emulator still passes — verified by quoting a clean
      `flutter test` run in the Work Log.

## Work Log

### 2026-06-22 - Filed

- Created from a todo-224 implementation follow-up (real offline→online round-trip
  coverage). Not yet started.

## Notes

- Priority p3: the UI-facing contract (data continuously readable from the local
  store) is already covered by the fake-based suite; this closes the remaining gap
  on the literal SDK reconnect flush, which is valuable but not a current
  regression.
- Related: todo 237 (reconcile Firestore plants with the backend on reconnect) —
  both stem from the same offline-persistence wiring.
