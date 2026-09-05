import 'package:image_picker/image_picker.dart';

/// Picks an image file path from the device gallery for the forum composer.
///
/// Wrapped behind this tiny interface — rather than calling [ImagePicker]
/// directly from the composer screen — so widget tests can inject a fake
/// without touching platform channels (the app's existing convention for
/// external services: see `ForumApi` wrapping `ApiService`, `AuthService`
/// wrapping Firebase).
abstract class ForumImagePicker {
  /// Returns the picked file's path, or `null` if the user cancelled.
  Future<String?> pickImagePath();
}

class DeviceForumImagePicker implements ForumImagePicker {
  const DeviceForumImagePicker();

  /// Downscale on the device, same bounds as the plant-ID camera flow
  /// (`camera_screen.dart`): a full-resolution phone photo is routinely
  /// larger than the backend's 10 MB cap (`wagtail_forum/conf.py`
  /// IMAGE_MAX_SIZE_BYTES), so without this the whole file went over the
  /// wire only to be rejected (audit 2026-09-04 M7). The forum serves a
  /// bounded rendition anyway, so nothing above this is ever displayed.
  static const int maxDimension = 1080;
  static const int jpegQuality = 85;

  @override
  Future<String?> pickImagePath() async {
    final file = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      maxWidth: maxDimension.toDouble(),
      maxHeight: maxDimension.toDouble(),
      imageQuality: jpegQuality,
    );
    return file?.path;
  }
}
