import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

/// Emulator-backed offline→online round-trip for the Firestore sync layer.
///
/// The fake-based suite (`test/integration/offline_sync_test.dart`) verifies the
/// UI contract — a saved plant is continuously readable from the local store —
/// but `FakeFirebaseFirestore` has no network, so it cannot exercise the literal
/// SDK write-queue flush across a reconnect. This test closes that gap against a
/// real `FirebaseFirestore` pointed at the Firebase emulator suite.
///
/// ## How it is gated
///
/// Connection details arrive via `--dart-define` (compile-time), NOT a runtime
/// env var: an integration test executes ON the device/simulator, where the host
/// shell's environment is not visible. When `FIRESTORE_EMULATOR_HOST` is unset
/// the test is skipped, so:
///   * plain `flutter test` (which only scans `test/`) never sees this file, and
///   * a device run without the define is a clean skip, not a failure.
///
/// ## How to run it
///
/// ```bash
/// # from the repo root (firebase.json with the emulators block lives there)
/// ./plant_community_mobile/scripts/run_firestore_emulator_test.sh <device-id>
/// ```
///
/// or manually (no FIREBASE_* config defines needed — the native [DEFAULT] app
/// supplies them; the emulator --project just matches that native projectId):
///
/// ```bash
/// firebase emulators:exec --project plant-community-prod --only auth,firestore \
///   "cd plant_community_mobile && flutter test \
///      integration_test/firestore_emulator_roundtrip_test.dart -d <device-id> \
///      --dart-define=FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
///      --dart-define=FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099"
/// ```
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  const firestoreHostPort = String.fromEnvironment('FIRESTORE_EMULATOR_HOST');
  const authHostPort = String.fromEnvironment('FIREBASE_AUTH_EMULATOR_HOST');

  group('Firestore offline→online round-trip (emulator)', () {
    testWidgets(
      'a write queued offline flushes to the emulator server on reconnect',
      (tester) async {
        // Single budget for every async step, tunable in one place (e.g. bump
        // for a slow CI runner).
        const stepTimeout = Duration(seconds: 15);

        final (fsHost, fsPort) = _splitHostPort(firestoreHostPort);
        // Auth shares the emulator host; default to the conventional 9099 port
        // when only the Firestore define is supplied.
        final (authHost, authPort) = _splitHostPort(
          authHostPort.isNotEmpty ? authHostPort : '$fsHost:9099',
        );

        // --- Wire Firebase up against the local emulators ---
        // iOS/Android auto-configure the native [DEFAULT] app from the bundled
        // GoogleService-Info.plist / google-services.json. initializeApp() with
        // NO options adopts that native config; passing options would throw
        // [core/duplicate-app]. (Firebase.apps is empty Dart-side until this
        // first call, even when the native app already exists.)
        if (Firebase.apps.isEmpty) {
          await Firebase.initializeApp();
        }

        await FirebaseAuth.instance.useAuthEmulator(authHost, authPort);

        // The Firestore rules enforce `request.auth.uid == userId` server-side,
        // so the queued write would be rejected on flush unless we are signed in
        // as the document owner. Sign in first and use the emulator-issued uid.
        final cred = await FirebaseAuth.instance.signInAnonymously();
        final uid = cred.user!.uid;

        // firestoreServiceProvider is autoDispose (@riverpod): obtained via a
        // bare read with no active listener, it is disposed across the test's
        // async gaps (disableNetwork/enableNetwork), after which ref.read()
        // inside the service throws UnmountedRefException. A no-op listener
        // keeps it mounted for the whole test.
        //
        // The listen also mounts the provider — running FirestoreService.build()
        // (which assigns `settings = Settings(persistenceEnabled: true)`, no
        // host) — BEFORE useFirestoreEmulator below. Connecting the emulator
        // first would let build() clobber the emulator host and send traffic to
        // prod.
        final container = ProviderContainer();
        addTearDown(container.dispose);
        final keepAlive = container.listen(
          firestoreServiceProvider.notifier,
          (_, _) {},
        );
        addTearDown(keepAlive.close);
        final firestore = keepAlive.read();

        FirebaseFirestore.instance.useFirestoreEmulator(fsHost, fsPort);

        addTearDown(() async {
          await FirebaseAuth.instance.signOut();
        });

        final plant = Plant(
          id: 'roundtrip-1',
          name: 'Monstera Deliciosa',
          scientificName: 'Monstera deliciosa',
          description: 'Swiss Cheese Plant',
          care: const ['Water weekly', 'Bright indirect light'],
          imageUrl: 'https://example.com/monstera.jpg',
          timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
        );

        // --- Offline: queue a write, assert it is locally readable + pending ---
        await FirebaseFirestore.instance.disableNetwork();

        // Do NOT await: while offline the write commits to the local cache
        // immediately, but its Future resolves only on server ack (after
        // reconnect). Awaiting here would deadlock the test.
        final pendingWrite = firestore.savePlant(uid, plant);

        final cached = await firestore
            .getPlantsStream(uid)
            .firstWhere((s) => s.plants.any((p) => p.id == plant.id))
            .timeout(stepTimeout);
        expect(
          cached.hasPendingWrites,
          isTrue,
          reason: 'offline write should be pending server acknowledgement',
        );
        expect(
          cached.isFromCache,
          isTrue,
          reason: 'reads while offline come from the local cache',
        );

        // --- Online: reconnect; the queued write flushes to the server ---
        await FirebaseFirestore.instance.enableNetwork();
        await pendingWrite.timeout(stepTimeout);

        // Observe the SDK clear the pending-write flag — the local signal that the
        // server acknowledged the queued write (AC: "wait for hasPendingWrites to
        // become false"). NOTE: a stream emission is NOT itself proof of server
        // persistence — Firestore can serve this from cache with the flag already
        // cleared, and won't reliably push a from-server snapshot for an
        // already-synced query — so the authoritative proof is the Source.server
        // read below.
        final synced = await firestore
            .getPlantsStream(uid)
            .firstWhere(
              (s) =>
                  s.plants.any((p) => p.id == plant.id) && !s.hasPendingWrites,
            )
            .timeout(stepTimeout);
        expect(
          synced.hasPendingWrites,
          isFalse,
          reason: 'the SDK should clear pending writes after the server ack',
        );

        // --- Independent server read proves the doc reached the emulator ---
        final serverDoc = await FirebaseFirestore.instance
            .collection('users')
            .doc(uid)
            .collection('identified_plants')
            .doc(plant.id)
            .get(const GetOptions(source: Source.server))
            .timeout(stepTimeout);
        expect(
          serverDoc.exists,
          isTrue,
          reason: 'document must be present on the emulator server',
        );
        expect(
          serverDoc.metadata.isFromCache,
          isFalse,
          reason: 'a Source.server read must not be served from cache',
        );
        // Every field must round-trip, not just one — guards against a
        // Plant.toJson serialization regression silently dropping fields.
        expect(serverDoc.data(), plant.toJson());
      },
      // Emulator gate: skipped unless --dart-define=FIRESTORE_EMULATOR_HOST is
      // supplied (see the file header for the full run command). Keeps plain
      // `flutter test` and define-less device runs green.
      skip: firestoreHostPort.isEmpty,
      // Overall ceiling so an unreachable emulator fails the test instead of
      // hanging forever: the un-awaited-with-timeout calls (initializeApp,
      // useAuthEmulator, signInAnonymously, enable/disableNetwork) have no
      // per-step timeout of their own.
      timeout: const Timeout(Duration(minutes: 2)),
    );
  });
}

/// Splits a `host:port` string on the final colon, so bracketed IPv6 hosts
/// (e.g. `[::1]:8080`) keep their address intact.
(String, int) _splitHostPort(String value) {
  final idx = value.lastIndexOf(':');
  if (idx < 0) {
    throw ArgumentError.value(value, 'value', 'expected "host:port"');
  }
  return (value.substring(0, idx), int.parse(value.substring(idx + 1)));
}
