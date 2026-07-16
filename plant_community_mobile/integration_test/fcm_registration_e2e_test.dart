import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:plant_community_mobile/firebase_options.dart';
import 'package:plant_community_mobile/main.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

/// FCM token registration end-to-end (todo 253 slice 6, AC6).
///
/// The app has no login UI yet (todo 260), so this test drives the REAL
/// production chain by signing in through `FirebaseAuth` directly while the
/// real app widget is mounted: the `AuthService` auth-state listener picks the
/// sign-in up exactly as it would a login screen's, exchanges the Firebase ID
/// token for a Django JWT against the live dev backend (`API_BASE_URL`), and
/// its post-exchange hook runs `PushRegistrationService.syncAfterLogin()` —
/// real notification permission, real FCM `getToken()` (needs a Play-services
/// device/emulator), real `PATCH /forum/me/profile/`.
///
/// The test asserts the in-app half (JWT exchange completes). The PATCHed
/// `fcm_token` is write-only by design and never readable from the API, so
/// the registration itself is verified host-side after the run:
///
/// ```bash
/// cd backend && ./venv/bin/python manage.py shell -c \
///   "from django.contrib.auth import get_user_model; \
///    from wagtail_forum.models import ForumProfile; \
///    u = get_user_model().objects.get(email='<E2E_AUTH_EMAIL>'); \
///    t = ForumProfile.for_user(u).fcm_token; \
///    print('fcm_token set:', bool(t), 'len:', len(t))"
/// ```
///
/// ## How it is gated
///
/// Credentials arrive via `--dart-define` (compile-time), NOT a runtime env
/// var — an integration test executes ON the device, where the host shell's
/// environment is invisible (same gate pattern as
/// `firestore_emulator_roundtrip_test.dart`). Without both defines the test
/// is a clean skip, so plain `flutter test` and define-less device runs stay
/// green. The account is a disposable dev user; the password is never
/// committed anywhere.
///
/// The Auth-emulator mode (`E2E_AUTH_EMULATOR_HOST`) is the SUPPORTED path
/// for password accounts: the backend fails closed on unverified emails (403,
/// by design), and only the emulator's admin API can flip `emailVerified`
/// without an email round-trip. Against real Firebase this test only passes
/// with an account whose email is already verified — a fresh auto-created
/// account will 403 every exchange and time out (slice-6 review).
///
/// ## How to run it
///
/// ```bash
/// # backend dev server must be running (port 8000); emulator must have
/// # Google Play services; pre-grant the notification permission so the
/// # Android 13+ system dialog can't block the run:
/// adb shell pm grant com.plantcommunity.plant_community_mobile \
///   android.permission.POST_NOTIFICATIONS
///
/// flutter test integration_test/fcm_registration_e2e_test.dart -d <device> \
///   --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 \
///   --dart-define=FIREBASE_API_KEY=... (etc — same set as flutter run) \
///   --dart-define=E2E_AUTH_EMAIL=fcm-e2e@example.com \
///   --dart-define=E2E_AUTH_PASSWORD=<throwaway>
/// ```
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  const email = String.fromEnvironment('E2E_AUTH_EMAIL');
  const password = String.fromEnvironment('E2E_AUTH_PASSWORD');
  // Optional: run the Firebase-auth leg against the local Auth emulator
  // (repo-root `firebase emulators:start --only auth --project
  // plant-community-prod`; the backend then needs
  // FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 in its environment so
  // firebase_admin verifies emulator tokens). Keeps the E2E fully
  // credential-free and out of prod Firebase Auth; from the Android
  // emulator the host is 10.0.2.2:9099.
  const authEmulatorHost = String.fromEnvironment('E2E_AUTH_EMULATOR_HOST');

  group('FCM registration end-to-end', () {
    testWidgets(
      'sign-in drives JWT exchange, and the push-registration hook runs',
      (tester) async {
        // Mirrors main.dart's own init; the duplicate-app fallback adopts a
        // native [DEFAULT] app when one exists (Firebase.apps is empty
        // Dart-side until the first call, so the isEmpty guard alone cannot
        // detect it).
        if (Firebase.apps.isEmpty) {
          try {
            await Firebase.initializeApp(
              options: DefaultFirebaseOptions.currentPlatform,
            );
          } on FirebaseException catch (e) {
            if (e.code != 'duplicate-app') rethrow;
            await Firebase.initializeApp();
          }
        }

        if (authEmulatorHost.isNotEmpty) {
          final (host, port) = _splitHostPort(authEmulatorHost);
          await FirebaseAuth.instance.useAuthEmulator(host, port);
        }

        // Start signed out so the sign-in below always transitions the
        // auth-state listener.
        if (FirebaseAuth.instance.currentUser != null) {
          await FirebaseAuth.instance.signOut();
        }

        // Own the container so the test can read the REAL app's providers.
        final container = ProviderContainer();
        addTearDown(container.dispose);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: const MyApp(),
          ),
        );
        await tester.pump(const Duration(seconds: 1));

        // Sign in (or first-run create) the disposable E2E account. The real
        // AuthService listener reacts to this exactly as it would a login
        // screen's call — nothing app-side is mocked or bypassed.
        try {
          await FirebaseAuth.instance.signInWithEmailAndPassword(
            email: email,
            password: password,
          );
        } on FirebaseAuthException catch (e) {
          if (e.code == 'user-not-found' || e.code == 'invalid-credential') {
            await FirebaseAuth.instance.createUserWithEmailAndPassword(
              email: email,
              password: password,
            );
          } else {
            rethrow;
          }
        }

        if (authEmulatorHost.isNotEmpty) {
          // The backend fails closed on unverified emails (403, by design —
          // docs/rules/security.md), and an emulator password account starts
          // unverified. Flip the flag through the emulator's credential-free
          // admin API (`Bearer owner`), then sign in AGAIN so the auth-state
          // listener re-fires with a verified token. Dart's HttpClient is not
          // subject to the platform cleartext policy, so this reaches the
          // emulator directly.
          final uid = FirebaseAuth.instance.currentUser!.uid;
          final httpClient = HttpClient();
          try {
            final request = await httpClient.postUrl(
              Uri.parse(
                'http://$authEmulatorHost'
                '/identitytoolkit.googleapis.com/v1/accounts:update',
              ),
            );
            request.headers.set('Authorization', 'Bearer owner');
            request.headers.contentType = ContentType.json;
            request.write(
              jsonEncode({'localId': uid, 'emailVerified': true}),
            );
            final response = await request.close();
            expect(
              response.statusCode,
              200,
              reason: 'emulator accounts:update must accept the owner token',
            );
            await response.drain<void>();
          } finally {
            httpClient.close();
          }

          await FirebaseAuth.instance.signOut();
          await FirebaseAuth.instance.signInWithEmailAndPassword(
            email: email,
            password: password,
          );
        }

        // JWT exchange (Firebase token → Django JWT) runs async in the
        // listener; poll the real provider until it completes.
        const exchangeBudget = Duration(seconds: 45);
        final deadline = DateTime.now().add(exchangeBudget);
        while (!container.read(authServiceProvider).isAuthenticated) {
          if (DateTime.now().isAfter(deadline)) {
            fail(
              'JWT exchange did not complete within $exchangeBudget — '
              'state: ${container.read(authServiceProvider).error}',
            );
          }
          await tester.pump(const Duration(milliseconds: 500));
        }

        // The FCM registration hook fires after the exchange (fire-and-
        // forget): poll the service's own completion marker — exits the
        // moment registration lands, fails loudly if it never does (a blind
        // fixed wait was both slower and able to exit before the PATCH on a
        // cold emulator; slice-6 review).
        final pushService = container.read(pushRegistrationServiceProvider);
        const registrationBudget = Duration(seconds: 60);
        final syncDeadline = DateTime.now().add(registrationBudget);
        while (pushService.lastSyncedToken == null) {
          if (DateTime.now().isAfter(syncDeadline)) {
            fail(
              'FCM registration did not complete within $registrationBudget',
            );
          }
          await tester.pump(const Duration(milliseconds: 500));
        }

        expect(container.read(authServiceProvider).isAuthenticated, isTrue);
        expect(pushService.lastSyncedToken, isNotEmpty);
      },
      // Credential gate: skipped unless both --dart-define values are
      // supplied (see the file header for the full run command).
      skip: email.isEmpty || password.isEmpty,
      // Real network on both legs (Firebase + local Django): generous overall
      // ceiling so an unreachable backend fails loudly instead of hanging.
      timeout: const Timeout(Duration(minutes: 4)),
    );
  });
}

/// Splits a `host:port` string on the final colon, so bracketed IPv6 hosts
/// (e.g. `[::1]:9099`) keep their address intact — same helper as
/// `firestore_emulator_roundtrip_test.dart`.
(String, int) _splitHostPort(String value) {
  final idx = value.lastIndexOf(':');
  final port = idx < 0 ? null : int.tryParse(value.substring(idx + 1));
  if (idx < 0 || port == null) {
    throw ArgumentError.value(value, 'value', 'expected "host:port"');
  }
  return (value.substring(0, idx), port);
}
