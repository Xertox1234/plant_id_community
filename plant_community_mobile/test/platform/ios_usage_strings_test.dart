import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// iOS kills an app that asks for a protected resource without its usage
/// string in Info.plist. The camera key was missing for months while
/// Identify -> Take photo shipped, and no test could see it (todo 444,
/// PR #857). This pins the strings every plugin in pubspec.yaml needs.
void main() {
  test('every iOS permission a plugin needs has a usage string', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final plist = File('ios/Runner/Info.plist').readAsStringSync();

    final required = <String, List<String>>{
      'image_picker': [
        'NSCameraUsageDescription',
        'NSPhotoLibraryUsageDescription',
      ],
    };
    for (final entry in required.entries) {
      if (!RegExp('^\\s+${entry.key}:', multiLine: true).hasMatch(pubspec)) {
        continue;
      }
      for (final key in entry.value) {
        final match = RegExp(
          '<key>$key</key>\\s*<string>([^<]+)</string>',
        ).firstMatch(plist);
        expect(
          match,
          isNotNull,
          reason: '${entry.key} is a dependency but Info.plist has no $key',
        );
        expect(match!.group(1)!.trim(), isNotEmpty);
      }
    }
  });
}
