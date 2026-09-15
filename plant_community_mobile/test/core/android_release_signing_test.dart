import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Android release builds must be signed with a release key, and the Firebase
/// config must be able to identify them.
///
/// Both halves shipped broken for the life of the project and nothing said so:
///
///  * `build.gradle.kts` carried Flutter's template default,
///    `signingConfig = signingConfigs.getByName("debug")` inside `release`, so
///    every release build was signed with `~/.android/debug.keystore` — a key
///    shared by every Flutter developer on the machine.
///  * `google-services.json` held one `oauth_client`, a `client_type: 3` (web)
///    entry with no `certificate_hash`. Google Sign-In on Android binds package
///    name to signing certificate through a `client_type: 1` (Android) client,
///    so without one the flow cannot work — in debug or release.
///
/// Neither failure is visible from the UI. The `google_sign_in` README warns
/// that Credential Manager reports configuration errors as `canceled`, and
/// `AuthService.signInWithGoogle` deliberately swallows `canceled` so a user who
/// changes their mind doesn't get a red banner. A misconfigured build therefore
/// looks exactly like a user backing out.
///
/// These assertions read the shipped build file and the shipped config, so a
/// regression fails here rather than on a device.
void main() {
  group('Android release signing', () {
    test('the release build type is not signed with the debug key', () {
      final gradle = _read(
        'android/app/build.gradle.kts',
        'the Android app build script that declares the release signing config',
      );

      final release = _releaseBlock(_withoutComments(gradle));

      expect(
        release,
        isNot(contains('signingConfigs.getByName("debug")')),
        reason:
            'The release build type signs with the debug keystore. That key is '
            'shared by every Flutter install on the machine, is not the key any '
            'store certificate is registered against, and produces artifacts '
            'that cannot be distributed. Point the release block at the release '
            'signing config loaded from android/key.properties.',
      );
    });

    test('release signing is driven by key.properties', () {
      final gradle = _read(
        'android/app/build.gradle.kts',
        'the Android app build script that declares the release signing config',
      );

      expect(
        gradle,
        contains('key.properties'),
        reason:
            'Nothing in the build script reads android/key.properties, so there '
            'is no release keystore to sign with. The keystore itself lives '
            'outside the repository (this repo is public); key.properties is '
            'the gitignored pointer to it.',
      );
    });
  });

  group('Firebase Android client', () {
    test('google-services.json declares an Android OAuth client', () {
      final config = jsonDecode(
            _read(
              'android/app/google-services.json',
              'the Firebase Android configuration',
            ),
          )
          as Map<String, dynamic>;

      final clients = (config['client'] as List<dynamic>).cast<Map<String, dynamic>>();

      expect(
        clients,
        isNotEmpty,
        reason: 'google-services.json declares no client at all.',
      );

      final oauthClients = clients
          .expand(
            (client) =>
                (client['oauth_client'] as List<dynamic>? ?? const <dynamic>[])
                    .cast<Map<String, dynamic>>(),
          )
          .toList();

      final androidClients =
          oauthClients.where((client) => client['client_type'] == 1).toList();

      expect(
        androidClients,
        isNotEmpty,
        reason:
            'google-services.json contains no client_type: 1 (Android) OAuth '
            'client, so Google Sign-In cannot work on Android. An Android '
            'client is provisioned by registering the signing certificate\'s '
            'SHA-1 on the Firebase Android app; re-download the config after '
            'doing so.',
      );

      for (final client in androidClients) {
        final androidInfo = client['android_info'] as Map<String, dynamic>?;
        expect(
          androidInfo?['certificate_hash'],
          isA<String>().having((hash) => hash.length, 'SHA-1 hex length', 40),
          reason:
              'An Android OAuth client carries no usable certificate_hash. The '
              'hash is what binds the package name to a signing certificate — '
              'without it the entry identifies nothing.',
        );
      }
    });

    test('the web OAuth client survives, because Android needs it too', () {
      final config = jsonDecode(
            _read(
              'android/app/google-services.json',
              'the Firebase Android configuration',
            ),
          )
          as Map<String, dynamic>;

      final webClients = (config['client'] as List<dynamic>)
          .cast<Map<String, dynamic>>()
          .expand(
            (client) =>
                (client['oauth_client'] as List<dynamic>? ?? const <dynamic>[])
                    .cast<Map<String, dynamic>>(),
          )
          .where((client) => client['client_type'] == 3);

      expect(
        webClients,
        isNotEmpty,
        reason:
            'google-services.json has no client_type: 3 (web) OAuth client. '
            'The google-services Gradle plugin turns that entry into the '
            'default_web_client_id string resource, which is the only thing '
            'google_sign_in reads on Android when no serverClientId is passed '
            'in Dart (GoogleSignInPlugin.java looks it up by name). Without it '
            'authenticate() throws "serverClientId must be provided on '
            'Android" before any certificate is ever checked.',
      );
    });
  });
}

/// Strips Kotlin comments so prose about the old default cannot fail the test.
///
/// The release block documents what it replaced, and naming
/// `signingConfigs.getByName("debug")` in that comment is the clearest way to
/// say it — but a substring search cannot tell an explanation from an
/// assignment. Comments go first, so the assertion sees only code.
///
/// Line-comment stripping would also cut a `//` inside a string literal. There
/// is no such literal in this build script, and a Gradle file that grows one
/// should not silently change what this test reads — so this stays naive on
/// purpose rather than growing a parser.
String _withoutComments(String gradle) => gradle
    .replaceAll(RegExp(r'/\*.*?\*/', dotAll: true), '')
    .replaceAll(RegExp('//[^\n]*'), '');

/// Extracts the body of the `release { ... }` build type by brace matching.
///
/// A plain substring search over the whole file would let a debug reference
/// anywhere — in `debug { }`, in a comment at the bottom — decide this test.
/// The question is specifically what the *release* build type signs with.
String _releaseBlock(String gradle) {
  final start = RegExp(r'\brelease\s*\{').firstMatch(gradle);
  if (start == null) {
    throw StateError(
      'android/app/build.gradle.kts declares no release build type. Either the '
      'build script moved or the block was deleted; this test cannot report on '
      'release signing without it.',
    );
  }

  var depth = 0;
  for (var i = start.end - 1; i < gradle.length; i++) {
    if (gradle[i] == '{') depth++;
    if (gradle[i] == '}') {
      depth--;
      if (depth == 0) return gradle.substring(start.end, i);
    }
  }

  throw StateError(
    'The release block in android/app/build.gradle.kts is unbalanced — no '
    'closing brace was found. Refusing to guess where it ends.',
  );
}

/// Reads a build file, failing loudly if it is absent.
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
      'Android signing setup from anywhere else.',
    );
  }
  return file.readAsStringSync();
}
