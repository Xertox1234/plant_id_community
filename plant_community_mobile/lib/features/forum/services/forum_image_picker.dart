import 'package:image_picker/image_picker.dart';

import '../../../services/api_service.dart';

/// Picks an image file path from the device gallery for the forum composer.
///
/// Wrapped behind this tiny interface — rather than calling [ImagePicker]
/// directly from the composer screen — so widget tests can inject a fake
/// without touching platform channels (the app's existing convention for
/// external services: see `ForumApi` wrapping `ApiService`, `AuthService`
/// wrapping Firebase).
abstract class ForumImagePicker {
  /// Returns the picked file's path, or `null` if the user cancelled.
  ///
  /// Throws [ApiException] when the pick is over [DeviceForumImagePicker.maxUploadBytes],
  /// so the composer surfaces it exactly like a server-side rejection — before
  /// the bytes go over the wire.
  Future<String?> pickImagePath();
}

class DeviceForumImagePicker implements ForumImagePicker {
  const DeviceForumImagePicker({ImagePicker? picker}) : _picker = picker;

  final ImagePicker? _picker;

  /// Mirrors the backend cap (`wagtail_forum/conf.py` IMAGE_MAX_SIZE_BYTES).
  /// A full-resolution phone photo is routinely larger, and without this
  /// check the whole file went over the wire only to be rejected (audit
  /// 2026-09-04 M7). NOT `maxWidth`/`imageQuality` on the pick: on Android
  /// those re-encode every gallery pick — an opaque PNG comes back as JPEG
  /// bytes under a `.png` name and an animated GIF is flattened to its first
  /// frame (image_picker_android ImageResizer), while iOS preserves both.
  /// GIF is in the forum's upload allowlist, so the pick stays byte-exact
  /// and only the size is guarded client-side (code review, PR #629).
  static const int maxUploadBytes = 10 * 1024 * 1024;

  @override
  Future<String?> pickImagePath() async {
    final file = await (_picker ?? ImagePicker()).pickImage(
      source: ImageSource.gallery,
    );
    if (file == null) return null;
    final size = await file.length();
    if (size > maxUploadBytes) {
      throw ApiException(
        'That photo is over 10 MB. Pick a smaller one.',
        statusCode: 413,
      );
    }
    return file.path;
  }
}
