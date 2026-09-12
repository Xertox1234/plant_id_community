import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb, visibleForTesting;

/// Firebase configuration loaded from local environment values.
///
/// This file is intentionally committed so a fresh checkout can compile.
/// It does not contain project-specific Firebase keys. Provide values through
/// `--dart-define` / CI environment configuration for builds. The `.env.example`
/// file lists the required keys.
///
/// The api key is resolved **per platform** (`FIREBASE_ANDROID_API_KEY`,
/// `FIREBASE_IOS_API_KEY`, `FIREBASE_WEB_API_KEY`), each falling back to the
/// shared `FIREBASE_API_KEY`. Google permits exactly one application restriction
/// per API key, so a key shared by Android and iOS cannot be restricted at all
/// without breaking one of them — see `todos/382`.
class DefaultFirebaseOptions {
  static const _dartDefines = <String, String>{
    'API_BASE_URL': String.fromEnvironment('API_BASE_URL'),
    'FIREBASE_API_KEY': String.fromEnvironment('FIREBASE_API_KEY'),
    // Per-platform api keys. A platform key that is not set falls back to the
    // shared FIREBASE_API_KEY above, so an existing build keeps working.
    'FIREBASE_ANDROID_API_KEY': String.fromEnvironment(
      'FIREBASE_ANDROID_API_KEY',
    ),
    'FIREBASE_IOS_API_KEY': String.fromEnvironment('FIREBASE_IOS_API_KEY'),
    'FIREBASE_WEB_API_KEY': String.fromEnvironment('FIREBASE_WEB_API_KEY'),
    'FIREBASE_APP_ID': String.fromEnvironment('FIREBASE_APP_ID'),
    'FIREBASE_MESSAGING_SENDER_ID': String.fromEnvironment(
      'FIREBASE_MESSAGING_SENDER_ID',
    ),
    'FIREBASE_PROJECT_ID': String.fromEnvironment('FIREBASE_PROJECT_ID'),
    'FIREBASE_STORAGE_BUCKET': String.fromEnvironment(
      'FIREBASE_STORAGE_BUCKET',
    ),
    'FIREBASE_AUTH_DOMAIN': String.fromEnvironment('FIREBASE_AUTH_DOMAIN'),
    'FIREBASE_MEASUREMENT_ID': String.fromEnvironment(
      'FIREBASE_MEASUREMENT_ID',
    ),
    'FIREBASE_WEB_APP_ID': String.fromEnvironment('FIREBASE_WEB_APP_ID'),
    'FIREBASE_IOS_BUNDLE_ID': String.fromEnvironment('FIREBASE_IOS_BUNDLE_ID'),
    'FIREBASE_IOS_APP_ID': String.fromEnvironment('FIREBASE_IOS_APP_ID'),
    'FIREBASE_ANDROID_PACKAGE_NAME': String.fromEnvironment(
      'FIREBASE_ANDROID_PACKAGE_NAME',
    ),
    'FIREBASE_ANDROID_APP_ID': String.fromEnvironment(
      'FIREBASE_ANDROID_APP_ID',
    ),
  };

  static const _resolver = FirebaseOptionsResolver(_dartDefines);

  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }

    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return ios;
      case TargetPlatform.windows:
      case TargetPlatform.linux:
        return desktop;
      case TargetPlatform.fuchsia:
        throw UnsupportedError(
          'DefaultFirebaseOptions are not configured for Fuchsia. '
          'Configure Firebase for this platform before running the app.',
        );
    }
  }

  static FirebaseOptions get android => _resolver.android;

  static FirebaseOptions get ios => _resolver.ios;

  static FirebaseOptions get web => _resolver.web;

  static FirebaseOptions get desktop => _resolver.desktop;
}

/// Builds [FirebaseOptions] from a map of build-time values.
///
/// Extracted from [DefaultFirebaseOptions] purely as a test seam: the production
/// values come from `String.fromEnvironment`, which is a compile-time constant,
/// so a test compiled with one `--dart-define` set can never exercise another.
/// Injecting the map lets one `flutter test` run assert — by value — both that
/// each platform picks up its own key and that an unset platform key still falls
/// back to the shared one.
///
/// This seam cannot prove the `_dartDefines` map itself lists a variable; a
/// forgotten entry there is invisible to an injected map. `test/firebase_options_test.dart`
/// covers that with real `--dart-define` values, and `mobile-ci.yml` runs it.
@visibleForTesting
class FirebaseOptionsResolver {
  const FirebaseOptionsResolver(this._values);

  final Map<String, String> _values;

  FirebaseOptions get android => FirebaseOptions(
    apiKey: _required(
      'FIREBASE_ANDROID_API_KEY',
      fallbackKey: 'FIREBASE_API_KEY',
    ),
    appId: _required('FIREBASE_ANDROID_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
    messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: _required('FIREBASE_PROJECT_ID'),
    storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
  );

  FirebaseOptions get ios => FirebaseOptions(
    apiKey: _required('FIREBASE_IOS_API_KEY', fallbackKey: 'FIREBASE_API_KEY'),
    appId: _required('FIREBASE_IOS_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
    messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: _required('FIREBASE_PROJECT_ID'),
    storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
    iosBundleId: _optional('FIREBASE_IOS_BUNDLE_ID'),
  );

  FirebaseOptions get web => FirebaseOptions(
    apiKey: _required('FIREBASE_WEB_API_KEY', fallbackKey: 'FIREBASE_API_KEY'),
    appId: _required('FIREBASE_WEB_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
    messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: _required('FIREBASE_PROJECT_ID'),
    authDomain: _optional('FIREBASE_AUTH_DOMAIN'),
    storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
    measurementId: _optional('FIREBASE_MEASUREMENT_ID'),
  );

  // Desktop is not shipped; it keeps the shared key deliberately (todos/382).
  FirebaseOptions get desktop => FirebaseOptions(
    apiKey: _required('FIREBASE_API_KEY'),
    appId: _required('FIREBASE_APP_ID'),
    messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: _required('FIREBASE_PROJECT_ID'),
    storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
  );

  String _required(String key, {String? fallbackKey}) {
    final value =
        _optional(key) ?? (fallbackKey == null ? null : _optional(fallbackKey));
    if (value == null) {
      final fallbackMessage = fallbackKey == null ? '' : ' or $fallbackKey';
      throw StateError(
        'Missing Firebase configuration value: $key$fallbackMessage. '
        'Use .env.example as a reference and pass the value with --dart-define.',
      );
    }
    return value;
  }

  String? _optional(String key) {
    final value = _values[key];
    if (value != null && value.isNotEmpty) {
      return value;
    }

    return null;
  }
}
