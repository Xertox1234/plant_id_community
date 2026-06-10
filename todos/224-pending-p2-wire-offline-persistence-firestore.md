---
status: pending
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

- [ ] At least one production screen reads from `plantsStreamProvider`.
- [ ] Plant data persists to Firestore on save and is readable offline.
- [ ] Sync-on-reconnect behavior is defined and covered by a real (non-mock-only) test.
- [ ] `flutter analyze` clean; `flutter test` green.

## Work Log

### 2026-06-09 - Created

- Reclassified from audit finding M18. Audit restored the wrongly-deleted layer
  after the owner confirmed offline persistence is a roadmap priority; this todo
  tracks wiring it into the UI and improving it.

## Notes

p2: not a bug, but the layer is dead weight until wired — and it's a stated
roadmap priority. This is the "improve upon" half of "keep and improve."
