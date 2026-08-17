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

  @override
  Future<String?> pickImagePath() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery);
    return file?.path;
  }
}
