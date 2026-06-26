---
status: completed
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

1. Add a Firebase **Firestore emulator** config — neither `firebase.json` (root
   or `plant_community_mobile/`) has an `emulators` block today, so this is
   net-new: add one plus a script to start the emulator.
2. Write a Flutter `integration_test` (not a widget/unit test) that:
   - points the client at the emulator via
     `FirebaseFirestore.instance.useFirestoreEmulator(host, port)`,
   - calls `disableNetwork()`, then `savePlant(uid, plant)`,
   - asserts the snapshot is readable with `hasPendingWrites == true` /
     `isFromCache == true`,
   - calls `enableNetwork()`, waits for `hasPendingWrites` to flip to `false`,
   - asserts the document is present server-side (independent emulator read).
3. Gate it so the default `flutter test` run stays green without the emulator —
   use an env var (e.g. `FIRESTORE_EMULATOR_HOST`) purely as a *skip guard*; the
   client connects via `useFirestoreEmulator`, not by reading that var. Optionally
   wire an emulator job into CI as a separate, non-blocking gate.

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

- [x] An emulator-backed integration test saves a plant while the network is
      disabled and asserts it is readable from cache with `hasPendingWrites == true`.
- [x] The same test re-enables the network, waits for `hasPendingWrites` to become
      `false`, and asserts the document reached the emulator server via an
      independent read.
- [x] The test is emulator-gated (skipped when the emulator env var is absent), so
      `flutter test` with no emulator still passes — verified by quoting a clean
      `flutter test` run in the Work Log.

## Work Log

### 2026-06-22 - Filed

- Created from a todo-224 implementation follow-up (real offline→online round-trip
  coverage). Not yet started.

### 2026-06-26 - Started by completing-todos skill (run 2026-06-26-0259)

- Picked up by automated workflow.

### 2026-06-26 - Implemented + verified (run 2026-06-26-0259)

**What landed**

- `firebase.json` (root): new `emulators` block — `auth` 9099, `firestore` 8080,
  `ui.enabled: false`, `singleProjectMode: true`.
- `plant_community_mobile/pubspec.yaml`: `integration_test` (sdk: flutter) dev dep.
- `plant_community_mobile/integration_test/firestore_emulator_roundtrip_test.dart`:
  the round-trip test. Reuses the native `[DEFAULT]` Firebase app
  (`Firebase.initializeApp()` with no options), signs in anonymously against the
  Auth emulator (rules require `request.auth.uid == userId`), holds a no-op
  Riverpod listener to keep the autoDispose `firestoreServiceProvider` mounted
  across the network gaps, then: `disableNetwork()` → `savePlant` (captured, not
  awaited) → assert `hasPendingWrites/isFromCache` from the cache → `enableNetwork()`
  → await the write → assert `hasPendingWrites == false` → `Source.server` read.
  Emulator-gated via `const String.fromEnvironment('FIRESTORE_EMULATOR_HOST')`
  (`--dart-define`, since on-device tests can't read host env vars).
- `plant_community_mobile/scripts/run_firestore_emulator_test.sh`: starts the
  auth+firestore emulators via `firebase emulators:exec` and runs the test on a
  device with the emulator-host defines.

**Incidental fix (necessary, kept):** the iOS build was already broken on `main` —
`pubspec.lock` had `firebase_core 4.11.0` while `ios/Podfile.lock` was stale at
`4.7.0` / Firebase 12.12.0 (someone ran `flutter pub upgrade` without
`pod install`). Regenerated `ios/Podfile.lock` (now Firebase 12.15.0) so the
simulator build — and thus this test — can run from a clean checkout.

**Design notes for reviewers**

- Emulator `--project` is the real `plant-community-prod` (matches the projectId
  the native `[DEFAULT]` app auto-loads from the bundled `GoogleService-Info.plist`),
  not a `demo-` project. All Firestore/Auth traffic is redirected to the local
  emulators via `useFirestoreEmulator`/`useAuthEmulator`, so prod is never reached.
- `await savePlant()` while offline would deadlock (Firestore resolves a write's
  Future only on server ack), so the write future is captured and awaited after
  reconnect.

**Verification (AC #1 + AC #2)** — `./plant_community_mobile/scripts/run_firestore_emulator_test.sh`
on a booted iPhone 16e simulator:

```
00:00 +0: Firestore offline→online round-trip (emulator) a write queued offline flushes to the emulator server on reconnect
[FIRESTORE] Saving plant Monstera Deliciosa for user 60oQTiij2pXyAtSxaGnoXQDW3d2i
[FIRESTORE] Received 1 plants (from cache)        # offline: hasPendingWrites/isFromCache asserted
[FIRESTORE] Plant saved successfully (will sync when online)   # write flushed after enableNetwork()
00:02 +1: All tests passed!
✔  Script exited successfully (code 0)
```

**Verification (AC #3)** — default `flutter test` (only scans `test/`; the new
`integration_test/` file is not picked up and is additionally skip-gated):

```
00:13 +174 ~3: All tests passed!
```

- `flutter analyze integration_test/firestore_emulator_roundtrip_test.dart` →
  `No issues found!`

### 2026-06-26 - Code review (run 2026-06-26-0259)

`code-review-orchestrator` — 0 critical/high (non-blocking). Findings triaged:

- **MEDIUM (fixed):** the script's header docstring still claimed emulators run
  "via the `demo-` project prefix" after the projectId was switched to
  `plant-community-prod` — stale/misleading. Rewrote it to describe the real
  isolation (local `emulators:exec` + `useFirestoreEmulator`/`useAuthEmulator`
  redirect, so prod is never contacted).
- **INFO (fixed):** clarified the `_splitHostPort` doc comment (splits on the
  final colon → bracketed IPv6 hosts stay intact).
- **LOW (not changed, by design):** unquoted `$DEVICE_ARG` — it is interpolated
  into a command *string* that `emulators:exec` re-parses with a shell, and device
  IDs are hyphenated hex (no spaces), so the string-building form is correct.
  `_splitHostPort` `RangeError` on a colon-less input — the private helper only
  ever receives the script-provided `host:port` gate value; added validation would
  be speculative (simplicity-first).

Re-verified after the comment fixes: `flutter analyze` → `No issues found!`,
`bash -n` on the script → OK.

### 2026-06-26 - Completed by completing-todos skill (run 2026-06-26-0259)

- Verification: all 3 acceptance criteria passed — emulator round-trip green on an
  iPhone 16e simulator (AC #1/#2), default `flutter test` green with the test
  gated out (AC #3).
- Review: 4 findings, 0 blocking — 1 MEDIUM + 1 INFO fixed, 2 LOW left as-is with
  documented rationale.

## Notes

- Priority p3: the UI-facing contract (data continuously readable from the local
  store) is already covered by the fake-based suite; this closes the remaining gap
  on the literal SDK reconnect flush, which is valuable but not a current
  regression.
- This todo stands on its own and is **not** affected by todo 237's resolution.
  236 verifies the Firestore SDK's *own* offline write-queue flush to the Firestore
  emulator (client cache → Firestore server) — real behavior wired by todo 224.
- Stale cross-reference corrected (2026-06-24): an earlier note here claimed "237's
  reconcile test needs the same emulator harness this todo builds." Todo 237 was
  **resolved as a no-op** — investigation found the identify endpoint is stateless
  and the mobile collection is Firestore-only, so there is no backend↔Firestore
  reconcile and no "237 reconcile test" to share this harness with. The Firestore
  round-trip 236 tests is unrelated to the (non-existent) backend sync. See
  `todos/archive/237-completed-p2-reconcile-firestore-backend-reconnect.md`.
