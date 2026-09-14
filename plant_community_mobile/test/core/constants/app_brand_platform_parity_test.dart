import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/constants/app_brand.dart';

/// The home-screen name on each platform must equal [AppBrand.name].
///
/// `AppBrand` unified the three competing Dart-side names, but the name a user
/// actually reads first — the icon caption on the home screen — is not a Dart
/// string at all. It lives in the native manifests, which the Dart rename could
/// not reach. iOS build 10 therefore shipped the whole Canopy design under
/// `CFBundleDisplayName = "Plant Community Mobile"`, and Android still said
/// `plant_community_mobile`.
///
/// Nothing caught that, because nothing compared the two sides. This does.
/// It reads the shipped manifests rather than any intermediate, so a rename in
/// one place and not the other fails here instead of on a tester's phone.
void main() {
  group('native display name matches AppBrand.name', () {
    test('iOS CFBundleDisplayName', () {
      final plist = _read(
        'ios/Runner/Info.plist',
        'the iOS bundle metadata that names the app on the home screen',
      );

      // CFBundleDisplayName's value is the next <string> after the key.
      final match = RegExp(
        r'<key>CFBundleDisplayName</key>\s*<string>([^<]*)</string>',
      ).firstMatch(plist);

      expect(
        match,
        isNotNull,
        reason:
            'ios/Runner/Info.plist declares no CFBundleDisplayName. Without it '
            'iOS falls back to CFBundleName, so the home-screen caption stops '
            'being reviewable here — re-add the key rather than deleting this '
            'assertion.',
      );

      expect(
        match!.group(1),
        AppBrand.name,
        reason:
            'The iOS home-screen name has drifted from AppBrand.name. Update '
            'ios/Runner/Info.plist\'s CFBundleDisplayName to "${AppBrand.name}" '
            '(a Dart-only rename cannot reach it).',
      );
    });

    test('Android application label', () {
      final manifest = _read(
        'android/app/src/main/AndroidManifest.xml',
        'the Android manifest that names the app in the launcher',
      );

      final match = RegExp(
        r'''android:label\s*=\s*["']([^"']*)["']''',
      ).firstMatch(manifest);

      expect(
        match,
        isNotNull,
        reason:
            'AndroidManifest.xml declares no android:label on <application>.',
      );

      expect(
        match!.group(1),
        AppBrand.name,
        reason:
            'The Android launcher name has drifted from AppBrand.name. Update '
            '<application android:label> to "${AppBrand.name}".',
      );
    });
  });
}

/// Reads a manifest, failing loudly if it is absent.
///
/// A missing file must not read as a passing test: these paths are fixed by
/// Flutter's project layout, so absence means the harness is pointed somewhere
/// unexpected, not that there is nothing to check.
String _read(String path, String what) {
  final file = File(path);
  if (!file.existsSync()) {
    throw StateError(
      'Expected $what at ${file.absolute.path}, but it does not exist. '
      'Flutter tests run from the package root; this test cannot verify the '
      'display name from anywhere else.',
    );
  }
  return file.readAsStringSync();
}
