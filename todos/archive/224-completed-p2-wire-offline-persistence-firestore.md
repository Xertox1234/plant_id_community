---
status: completed
priority: p2
issue_id: "224"
tags: [mobile, flutter, offline, firestore, roadmap]
dependencies: []
source_review: "docs/audits/2026-06-09-maintainability.md"
source_finding: "M18"
---

# Wire up (and improve) the Flutter offline persistence layer

## Problem

The 2026-06-09 maintainability audit found `FirestoreService` (offline/sync
Firestore layer) + `plantsStreamProvider` fully built and test-covered but with
**zero production callers** — `collection_screen.dart` is a static placeholder, so
nothing reads the offline cache. The audit initially deleted it as dead code; the
**owner has confirmed offline persistence is a roadmap priority to keep and
improve**, so it was restored. The real work is to *wire it into the UI and build
on it*, not remove it.

## Findings

- `plant_community_mobile/lib/services/firestore_service.dart` — `FirestoreService`,
  `firestoreServiceProvider`, `plantsStreamProvider`, `savePlant`,
  `getPlantsStream`, `deletePlant`, `clearAllPlants`. Covered by
  `test/services/firestore_service_test.dart` and
  `test/integration/offline_sync_test.dart` — all green.
- No production consumer: `collection_screen.dart` has no providers/streams (static
  placeholder); no screen calls `firestoreServiceProvider` / `plantsStreamProvider`.
- Source: `docs/audits/2026-06-09-maintainability.md` (finding M18), restored on
  branch `chore/maintainability-audit-2026-06-09`.

## Recommended Action

1. Wire `collection_screen.dart` (and any plant-list/detail surfaces) to
   `plantsStreamProvider` so the offline cache is the read source.
2. On successful plant ID / save, persist via `FirestoreService.savePlant` so data
   is available offline; reconcile with `api_service` on reconnect (the
   offline→online sync path exercised by `offline_sync_test.dart`).
3. Define + test the conflict-resolution / sync-on-reconnect behavior beyond the
   current mock-based integration test (real offline→online round-trip).
4. Add UI affordances for offline state (cached badge, sync indicator).
5. Keep the existing tests green; extend them as the wiring lands.

## Technical Details

`plant_community_mobile/lib/services/firestore_service.dart`;
`lib/features/collection/collection_screen.dart`;
`test/integration/offline_sync_test.dart`. Patterns:
`plant_community_mobile/docs/patterns/riverpod.md`, `.../firebase-auth.md`.

## Acceptance Criteria

- [x] At least one production screen reads from `plantsStreamProvider`.
- [x] Plant data persists to Firestore on save and is readable offline.
- [x] Sync-on-reconnect behavior is defined and covered by a real (non-mock-only) test.
- [x] `flutter analyze` clean; `flutter test` green.

## Work Log

### 2026-06-09 - Created

- Reclassified from audit finding M18. Audit restored the wrongly-deleted layer
  after the owner confirmed offline persistence is a roadmap priority; this todo
  tracks wiring it into the UI and improving it.

### 2026-06-22 - Started by completing-todos skill (run 2026-06-22-1735)

- Picked up by automated workflow (via /todo-next).
- Owner decisions: test via **fake_cloud_firestore** (criterion #3); **full scope**
  including the offline/cached + sync badge (changes `plantsStreamProvider` to a
  `PlantsSnapshot` wrapper carrying `isFromCache`/`hasPendingWrites`).

### 2026-06-22 - Implementation + verification

**What changed**

- `services/firestore_service.dart`: injected `FirebaseFirestore` via a plain
  `firebaseFirestoreProvider` (overridable in tests; same convention as
  `apiServiceProvider`); guarded `build()`'s `settings=` (fakes don't implement
  it); `getPlantsStream`/`plantsStreamProvider` now emit a `PlantsSnapshot`
  wrapper carrying `isFromCache`/`hasPendingWrites`.
- `services/auth_service.dart`: added `currentUserIdProvider` (Firebase uid,
  null when signed out — Firestore needs only the Firebase identity, not the JWT).
- `features/camera/camera_screen.dart`: on a successful identification, persists
  the plant via `FirestoreService.savePlant` — **fire-and-forget** (`unawaited`)
  because an online `set()` doesn't complete until server-ack and would block
  navigation while offline; skipped when signed out.
- `features/collection/collection_screen.dart`: rewritten from a static stub to a
  `ConsumerWidget` watching `plantsStreamProvider(uid)`, with signed-out /
  loading / error / empty states, real plant cards, an "add" tile that routes to
  the camera, and a sync/offline badge (Syncing… / Offline) from the metadata.
- Tests: added `fake_cloud_firestore` (dev); `firestore_service_test.dart` now
  exercises the **real** service against a fake (CRUD, ordering, malformed-skip,
  per-user scoping, empty-uid rejection); `offline_sync_test.dart` rewritten to
  run the real service + fake (deleted the hand-rolled `MockFirestoreService`)
  and document that the reconnect round-trip is delegated to the Firestore SDK;
  `collection_screen_test.dart` rewritten for the new widget (5 states/badges).

**Verification evidence**

- `flutter analyze` → `No issues found! (ran in 2.7s)`.
- `flutter test` → `+174 ~3: All tests passed!` (3 skips pre-existing; the 4
  collection-stub tests were updated to the new behavior, not left failing).
- Changed-file suites: `firestore_service_test.dart` + `offline_sync_test.dart`
  → `+27 All tests passed!`; `collection_screen_test.dart` → `+5 All tests
  passed!`. The guarded `settings=` path is exercised (logs
  `Persistence settings not applied: NoSuchMethodError` then proceeds).
- `python scripts/check_flutter_security.py` → `✅ PASS: No security issues found`.
- build_runner regenerated `firestore_service.g.dart` (`Stream<PlantsSnapshot>`).

**Honest scope note (criterion #3):** fake_cloud_firestore is in-memory with no
connectivity concept, so the test proves the persistence contract the UI relies
on (a saved plant is immediately + continuously readable from the local store)
against the *real* service — not a literal network offline→online round-trip,
which Firestore's SDK handles natively and which would require the Firebase
emulator. This was the owner-chosen tradeoff.

### 2026-06-22 - Code review + repairs (run 2026-06-22-1735)

Review dispatched (flutter-dart / flutter-firebase / test-quality criteria).
3 findings, 1 blocking — all repaired (owner chose "Repair all three"):

- **[critical] `firebase/firestore.rules`** — the `users/{uid}/identified_plants`
  subcollection this wiring now actively uses was denied (rules don't cascade
  from the parent doc; the catch-all `if false` caught it), so server sync would
  silently fail in prod while the local cache made it *look* wired. Fixed: added
  `match /identified_plants/{plantId} { allow read, write: if isOwner(userId); }`
  nested in the users block. **⚠️ Requires `firebase deploy --only
  firestore:rules` to take effect in prod — deploy is the owner's to run.**
- **[medium] `firestore_service.dart`** — `getPlantsStream`'s blanket
  `.handleError` swallowed all stream errors, making the collection screen's
  error state unreachable and masking the rules failure above. Fixed: removed it
  so permission/index/quota errors propagate to the StreamProvider's AsyncError
  and the error UI shows (per-doc parse failures are still skipped, not surfaced).
- **[low] `offline_sync_test.dart`** — replaced the reactivity test's fixed
  `Future.delayed(50ms)` with a deterministic `stream.firstWhere(...)`.

Re-verification after repair: `flutter analyze` → No issues found; `flutter test`
→ `+174 ~3: All tests passed!`; security scan → PASS.

### 2026-06-22 - Completed by completing-todos skill (run 2026-06-22-1735)

- Verification: all 4 acceptance criteria passed with quoted evidence above.
- Review: 3 findings (1 critical, 1 medium, 1 low) — all repaired and re-verified.
- Follow-up for the owner: deploy the Firestore rules change
  (`firebase deploy --only firestore:rules`) so cross-device server sync works in
  prod. Possible follow-up todos: real offline→online round-trip via the Firebase
  emulator (criterion #3's literal form), and reconciling Firestore plants with
  the backend `api_service` on reconnect (recommended-action #2/#3).

## Notes

p2: not a bug, but the layer is dead weight until wired — and it's a stated
roadmap priority. This is the "improve upon" half of "keep and improve."
