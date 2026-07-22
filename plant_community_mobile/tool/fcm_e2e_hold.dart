// Throwaway E2E harness (todo 253 AC6 delivery): registers a FRESH FCM token
// and KEEPS the app installed + running, so a real reply_added push can be
// sent from the backend and observed in the emulator's notification tray.
//
// Unlike `flutter test integration_test/fcm_registration_e2e_test.dart`, which
// UNINSTALLS the app on teardown (instantly invalidating the just-minted token
// as NotRegistered), `flutter run -t tool/fcm_e2e_hold.dart` leaves the app in
// place. Same programmatic sign-in as the integration test (auth emulator).
//
// Run:
//   flutter run -t tool/fcm_e2e_hold.dart -d emulator-5554 \
//     --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 \
//     --dart-define=FIREBASE_API_KEY=... (full set) \
//     --dart-define=E2E_AUTH_EMAIL=... --dart-define=E2E_AUTH_PASSWORD=... \
//     --dart-define=E2E_AUTH_EMULATOR_HOST=10.0.2.2:9099
import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/firebase_options.dart';
import 'package:plant_community_mobile/main.dart';

const _email = String.fromEnvironment('E2E_AUTH_EMAIL');
const _password = String.fromEnvironment('E2E_AUTH_PASSWORD');
const _authEmulatorHost = String.fromEnvironment('E2E_AUTH_EMULATOR_HOST');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

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

  if (_authEmulatorHost.isNotEmpty) {
    final (host, port) = _splitHostPort(_authEmulatorHost);
    await FirebaseAuth.instance.useAuthEmulator(host, port);
  }

  // Mount the REAL app first so AuthService's auth-state listener is live; it
  // exchanges the Firebase token for a Django JWT and runs the push-
  // registration hook exactly as production would.
  runApp(const ProviderScope(child: MyApp()));

  await _signInAndVerify();
  debugPrint('[HOLD] sign-in complete — app is registered and staying alive');
}

Future<void> _signInAndVerify() async {
  if (FirebaseAuth.instance.currentUser != null) {
    await FirebaseAuth.instance.signOut();
  }

  try {
    await FirebaseAuth.instance.signInWithEmailAndPassword(
      email: _email,
      password: _password,
    );
  } on FirebaseAuthException catch (e) {
    if (e.code == 'user-not-found' || e.code == 'invalid-credential') {
      await FirebaseAuth.instance.createUserWithEmailAndPassword(
        email: _email,
        password: _password,
      );
    } else {
      rethrow;
    }
  }

  if (_authEmulatorHost.isNotEmpty) {
    // Backend fails closed on unverified emails (403). Flip emailVerified via
    // the emulator's credential-free admin API, then re-sign-in so the token
    // carries the verified claim.
    final uid = FirebaseAuth.instance.currentUser!.uid;
    final httpClient = HttpClient();
    try {
      final request = await httpClient.postUrl(
        Uri.parse(
          'http://$_authEmulatorHost'
          '/identitytoolkit.googleapis.com/v1/accounts:update',
        ),
      );
      request.headers.set('Authorization', 'Bearer owner');
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode({'localId': uid, 'emailVerified': true}));
      final response = await request.close();
      await response.drain<void>();
    } finally {
      httpClient.close();
    }

    await FirebaseAuth.instance.signOut();
    await FirebaseAuth.instance.signInWithEmailAndPassword(
      email: _email,
      password: _password,
    );
  }
}

(String, int) _splitHostPort(String value) {
  final idx = value.lastIndexOf(':');
  final port = idx < 0 ? null : int.tryParse(value.substring(idx + 1));
  if (idx < 0 || port == null) {
    throw ArgumentError.value(value, 'value', 'expected "host:port"');
  }
  return (value.substring(0, idx), port);
}
