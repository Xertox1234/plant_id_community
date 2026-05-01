import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform, kIsWeb;

/// Firebase configuration loaded from local environment values.
///
/// This file is intentionally committed so a fresh checkout can compile.
/// It does not contain project-specific Firebase keys. Provide values through
/// `--dart-define` / CI environment configuration for builds. The `.env.example`
/// file lists the required keys.
class DefaultFirebaseOptions {
  static const _dartDefines = <String, String>{
    'API_BASE_URL': String.fromEnvironment('API_BASE_URL'),
    'FIREBASE_API_KEY': String.fromEnvironment('FIREBASE_API_KEY'),
    'FIREBASE_APP_ID': String.fromEnvironment('FIREBASE_APP_ID'),
    'FIREBASE_MESSAGING_SENDER_ID': String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
    'FIREBASE_PROJECT_ID': String.fromEnvironment('FIREBASE_PROJECT_ID'),
    'FIREBASE_STORAGE_BUCKET': String.fromEnvironment('FIREBASE_STORAGE_BUCKET'),
    'FIREBASE_AUTH_DOMAIN': String.fromEnvironment('FIREBASE_AUTH_DOMAIN'),
    'FIREBASE_MEASUREMENT_ID': String.fromEnvironment('FIREBASE_MEASUREMENT_ID'),
    'FIREBASE_WEB_APP_ID': String.fromEnvironment('FIREBASE_WEB_APP_ID'),
    'FIREBASE_IOS_BUNDLE_ID': String.fromEnvironment('FIREBASE_IOS_BUNDLE_ID'),
    'FIREBASE_IOS_APP_ID': String.fromEnvironment('FIREBASE_IOS_APP_ID'),
    'FIREBASE_ANDROID_PACKAGE_NAME': String.fromEnvironment('FIREBASE_ANDROID_PACKAGE_NAME'),
    'FIREBASE_ANDROID_APP_ID': String.fromEnvironment('FIREBASE_ANDROID_APP_ID'),
  };

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

  static FirebaseOptions get android => FirebaseOptions(
        apiKey: _required('FIREBASE_API_KEY'),
        appId: _required('FIREBASE_ANDROID_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
        messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
        projectId: _required('FIREBASE_PROJECT_ID'),
        storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
      );

  static FirebaseOptions get ios => FirebaseOptions(
        apiKey: _required('FIREBASE_API_KEY'),
        appId: _required('FIREBASE_IOS_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
        messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
        projectId: _required('FIREBASE_PROJECT_ID'),
        storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
        iosBundleId: _optional('FIREBASE_IOS_BUNDLE_ID'),
      );

  static FirebaseOptions get web => FirebaseOptions(
        apiKey: _required('FIREBASE_API_KEY'),
        appId: _required('FIREBASE_WEB_APP_ID', fallbackKey: 'FIREBASE_APP_ID'),
        messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
        projectId: _required('FIREBASE_PROJECT_ID'),
        authDomain: _optional('FIREBASE_AUTH_DOMAIN'),
        storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
        measurementId: _optional('FIREBASE_MEASUREMENT_ID'),
      );

  static FirebaseOptions get desktop => FirebaseOptions(
        apiKey: _required('FIREBASE_API_KEY'),
        appId: _required('FIREBASE_APP_ID'),
        messagingSenderId: _required('FIREBASE_MESSAGING_SENDER_ID'),
        projectId: _required('FIREBASE_PROJECT_ID'),
        storageBucket: _optional('FIREBASE_STORAGE_BUCKET'),
      );

  static String _required(String key, {String? fallbackKey}) {
    final value = _optional(key) ?? (fallbackKey == null ? null : _optional(fallbackKey));
    if (value == null) {
      final fallbackMessage = fallbackKey == null ? '' : ' or $fallbackKey';
      throw StateError(
        'Missing Firebase configuration value: $key$fallbackMessage. '
        'Use .env.example as a reference and pass the value with --dart-define.',
      );
    }
    return value;
  }

  static String? _optional(String key) {
    final dartDefineValue = _dartDefines[key];
    if (dartDefineValue != null && dartDefineValue.isNotEmpty) {
      return dartDefineValue;
    }

    return null;
  }
}
