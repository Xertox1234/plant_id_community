import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:plant_community_mobile/features/forum/services/forum_image_picker.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Stands in for the platform picker: hands back a real temp file so the
/// size guard reads genuine bytes.
class _StubImagePicker extends ImagePicker {
  _StubImagePicker(this.file);

  final XFile? file;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    // The pick must stay byte-exact (GIF frames, PNG bytes) — no re-encode
    // parameters may be passed (code review, PR #629).
    expect(maxWidth, isNull);
    expect(maxHeight, isNull);
    expect(imageQuality, isNull);
    return file;
  }
}

void main() {
  late Directory tmp;

  setUp(() async {
    tmp = await Directory.systemTemp.createTemp('forum-picker');
  });

  tearDown(() async {
    await tmp.delete(recursive: true);
  });

  Future<XFile> fileOf(int bytes) async {
    final f = File('${tmp.path}/pick.gif');
    await f.writeAsBytes(Uint8List(bytes));
    return XFile(f.path);
  }

  test('returns the path of a pick within the cap, byte-exact', () async {
    final file = await fileOf(1024);
    final picker = DeviceForumImagePicker(picker: _StubImagePicker(file));

    expect(await picker.pickImagePath(), file.path);
  });

  test('rejects a pick over the 10 MB cap before any upload', () async {
    final file = await fileOf(DeviceForumImagePicker.maxUploadBytes + 1);
    final picker = DeviceForumImagePicker(picker: _StubImagePicker(file));

    await expectLater(
      picker.pickImagePath(),
      throwsA(
        isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 413)
            .having((e) => e.message, 'message', contains('10 MB')),
      ),
    );
  });

  test('a cancelled pick is null', () async {
    final picker = DeviceForumImagePicker(picker: _StubImagePicker(null));
    expect(await picker.pickImagePath(), isNull);
  });

  test('the cap mirrors the backend IMAGE_MAX_SIZE_BYTES', () {
    expect(DeviceForumImagePicker.maxUploadBytes, 10 * 1024 * 1024);
  });
}
