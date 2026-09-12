import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/firebase_options.dart';

// Distinct sentinels, so every assertion below can only pass for one reason.
// Held in constants rather than inline literals: a `'..._API_KEY': '<literal>'`
// line trips the detect-secrets keyword heuristic, and a test file does not
// belong in .secrets.baseline.
const _shared = 'sentinel-shared';
const _androidOnly = 'sentinel-android';
const _iosOnly = 'sentinel-ios';
const _webOnly = 'sentinel-web';

/// Values every getter needs regardless of which api key it resolves.
const _base = <String, String>{
  'FIREBASE_APP_ID': 'app-id',
  'FIREBASE_MESSAGING_SENDER_ID': 'sender-id',
  'FIREBASE_PROJECT_ID': 'project-id',
};

Map<String, String> _values(Map<String, String> overrides) => {
  ..._base,
  ...overrides,
};

// The real compile-time defines, read here so the second group can assert what
// the production `_dartDefines` map actually wires up. `flutter test` with no
// --dart-define leaves these empty and that group is skipped; `mobile-ci.yml`
// runs a second `flutter test` that supplies them.
const _legacyDefine = String.fromEnvironment('FIREBASE_API_KEY');
const _androidDefine = String.fromEnvironment('FIREBASE_ANDROID_API_KEY');
const _iosDefine = String.fromEnvironment('FIREBASE_IOS_API_KEY');
const _webDefine = String.fromEnvironment('FIREBASE_WEB_API_KEY');
const _definesUsable =
    _legacyDefine != '' &&
    String.fromEnvironment('FIREBASE_APP_ID') != '' &&
    String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID') != '' &&
    String.fromEnvironment('FIREBASE_PROJECT_ID') != '';

void main() {
  group('FirebaseOptionsResolver api key resolution', () {
    test('each platform resolves its own key when all are set', () {
      final resolver = FirebaseOptionsResolver(
        _values({
          'FIREBASE_API_KEY': _shared,
          'FIREBASE_ANDROID_API_KEY': _androidOnly,
          'FIREBASE_IOS_API_KEY': _iosOnly,
          'FIREBASE_WEB_API_KEY': _webOnly,
        }),
      );

      expect(resolver.android.apiKey, _androidOnly);
      expect(resolver.ios.apiKey, _iosOnly);
      expect(resolver.web.apiKey, _webOnly);
      // Desktop is not shipped and deliberately keeps the shared key.
      expect(resolver.desktop.apiKey, _shared);

      // The whole point of todo 382: Android and iOS must be able to differ, so
      // each key can carry its own Google application restriction.
      expect(resolver.android.apiKey, isNot(resolver.ios.apiKey));
    });

    test('every platform falls back to the shared key when none are set', () {
      final resolver = FirebaseOptionsResolver(
        _values({'FIREBASE_API_KEY': _shared}),
      );

      expect(resolver.android.apiKey, _shared);
      expect(resolver.ios.apiKey, _shared);
      expect(resolver.web.apiKey, _shared);
      expect(resolver.desktop.apiKey, _shared);
    });

    test('a platform key set for one platform does not leak to another', () {
      final resolver = FirebaseOptionsResolver(
        _values({
          'FIREBASE_API_KEY': _shared,
          'FIREBASE_ANDROID_API_KEY': _androidOnly,
        }),
      );

      expect(resolver.android.apiKey, _androidOnly);
      expect(resolver.ios.apiKey, _shared);
      expect(resolver.web.apiKey, _shared);
    });

    test('an empty platform key is treated as unset, not as an empty key', () {
      final resolver = FirebaseOptionsResolver(
        _values({
          'FIREBASE_API_KEY': _shared,
          'FIREBASE_ANDROID_API_KEY': '',
        }),
      );

      expect(resolver.android.apiKey, _shared);
    });

    test('a missing key throws and names both the platform var and the '
        'fallback', () {
      final resolver = FirebaseOptionsResolver(_base);

      expect(
        () => resolver.android.apiKey,
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            allOf(
              contains('FIREBASE_ANDROID_API_KEY'),
              contains('FIREBASE_API_KEY'),
            ),
          ),
        ),
      );
    });
  });

  // Guards the one failure the injected-map tests above cannot see: a
  // per-platform variable wired into a getter but missing from the
  // `_dartDefines` map is never read, so every platform silently falls back to
  // the shared key — exactly the bug todo 382 exists to fix, with a green suite.
  group(
    'DefaultFirebaseOptions reads the real --dart-define values',
    () {
      test('each platform resolves the define it was given', () {
        expect(
          DefaultFirebaseOptions.android.apiKey,
          _androidDefine.isNotEmpty ? _androidDefine : _legacyDefine,
          reason:
              'android must read FIREBASE_ANDROID_API_KEY; if this returns the '
              'shared key while the android define is set, the variable is '
              'missing from the _dartDefines map in firebase_options.dart',
        );
        expect(
          DefaultFirebaseOptions.ios.apiKey,
          _iosDefine.isNotEmpty ? _iosDefine : _legacyDefine,
          reason: 'ios must read FIREBASE_IOS_API_KEY',
        );
        expect(
          DefaultFirebaseOptions.web.apiKey,
          _webDefine.isNotEmpty ? _webDefine : _legacyDefine,
          reason: 'web must read FIREBASE_WEB_API_KEY',
        );
        expect(
          DefaultFirebaseOptions.desktop.apiKey,
          _legacyDefine,
          reason: 'desktop deliberately keeps the shared key',
        );
      });

      test('android and ios differ when both platform defines are set', () {
        if (_androidDefine.isEmpty || _iosDefine.isEmpty) {
          return;
        }
        expect(
          DefaultFirebaseOptions.android.apiKey,
          isNot(DefaultFirebaseOptions.ios.apiKey),
        );
      });
    },
    skip: _definesUsable
        ? null
        : 'needs real --dart-define values; see the second "flutter test" step '
              'in .github/workflows/mobile-ci.yml',
  );
}
