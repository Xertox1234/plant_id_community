import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Deletes captured or picked shot files the app no longer needs.
typedef ShotFileDeleter = void Function(Iterable<String> paths);

/// `camera` writes each shot into the cache dir and `image_picker` copies each
/// pick into the temp dir; neither deletes them, so the app does once a shot
/// is retaken, replaced, abandoned, or its capture is done with (scan-2 audit
/// L9). Overridable so tests record deletions instead of touching disk.
final shotFileDeleterProvider = Provider<ShotFileDeleter>(
  (ref) => deleteShotFiles,
);

/// Best-effort: a file already gone or locked is skipped, never thrown.
void deleteShotFiles(Iterable<String> paths) {
  for (final path in paths.toSet()) {
    unawaited(
      File(path).delete().then<void>(
        (_) {},
        onError: (Object e) => debugPrint('[SCAN] Could not delete shot: $e'),
      ),
    );
  }
}
