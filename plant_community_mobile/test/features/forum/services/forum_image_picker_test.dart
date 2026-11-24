import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';
import 'package:plant_community_mobile/features/forum/services/forum_image_picker.dart';
import 'package:plant_community_mobile/features/forum/services/forum_photo_downscale.dart';
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

  group('downscale to the server pixel limit (audit 2026-11-24 F207)', () {
    // Small images against a small limit: the real one needs 5000 px files.
    const limit = 100;

    Future<String?> pick(String name, List<int> bytes) async {
      final f = File('${tmp.path}/$name');
      await f.writeAsBytes(bytes);
      return DeviceForumImagePicker(
        picker: _StubImagePicker(XFile(f.path)),
        maxEdgePx: limit,
      ).pickImagePath();
    }

    /// Left half red, right half blue.
    img.Image halves(int width, int height) {
      final image = img.Image(width: width, height: height);
      for (final p in image) {
        p.x < width ~/ 2 ? p.setRgb(255, 0, 0) : p.setRgb(0, 0, 255);
      }
      return image;
    }

    test('the limit mirrors the backend IMAGE_MAX_WIDTH/HEIGHT', () {
      expect(DeviceForumImagePicker.serverMaxEdgePx, 5000);
    });

    test('an oversized JPEG comes back within the limit, same shape', () async {
      final path = await pick('wide.jpeg', img.encodeJpg(halves(400, 200)));
      expect(path, endsWith('/wide.jpg'));
      final out = img.decodeJpg(await File(path!).readAsBytes())!;
      expect([out.width, out.height], [100, 50]);
      expect(out.getPixel(10, 25).r, greaterThan(200));
      expect(out.getPixel(90, 25).b, greaterThan(200));
      expect(
        await File('${tmp.path}/wide.jpeg').exists(),
        isTrue,
        reason: 'the picked file is not ours to change',
      );
    });

    test('each copy has its own path, and only a copy is discarded', () async {
      final bytes = img.encodeJpg(halves(400, 200));
      final first = (await pick('same.jpg', bytes))!;
      final second = (await pick('same.jpg', bytes))!;
      expect(second, isNot(first));

      await discardForumPhotoCopy(first);
      expect(await File(first).exists(), isFalse);
      expect(await File(second).exists(), isTrue);
      await discardForumPhotoCopy('${tmp.path}/same.jpg');
      expect(await File('${tmp.path}/same.jpg').exists(), isTrue);
      await discardForumPhotoCopy(second);
    });

    test('an EXIF-rotated JPEG ends upright exactly once', () async {
      // Orientation 6: shown turned 90 degrees clockwise, so the stored left
      // half (red) is the shown top half.
      final image = halves(400, 200)..exif.imageIfd.orientation = 6;
      final path = await pick('rotated.jpg', img.encodeJpg(image));
      final out = img.decodeJpg(await File(path!).readAsBytes())!;
      expect(out.exif.imageIfd.orientation ?? 1, 1);
      expect([out.width, out.height], [50, 100]);
      expect(out.getPixel(25, 10).r, greaterThan(200));
      expect(out.getPixel(25, 90).b, greaterThan(200));
    });

    test('an oversized opaque WebP comes back as a JPEG', () async {
      final path = await pick('wide.webp', img.encodeWebP(halves(400, 200)));
      expect(path, endsWith('/wide.jpg'));
      final out = img.decodeJpg(await File(path!).readAsBytes())!;
      expect([out.width, out.height], [100, 50]);
    });

    test('everything else stays byte-exact', () async {
      final clear = img.Image(width: 400, height: 200, numChannels: 4);
      for (final (name, bytes) in [
        ('ok.jpg', img.encodeJpg(halves(limit, 80))),
        ('big.png', img.encodePng(halves(400, 200))),
        ('big.gif', img.encodeGif(halves(400, 200))),
        ('clear.webp', img.encodeWebP(clear)),
        ('broken.jpg', [0xFF, 0xD8, 0xFF, 1, 2, 3]),
      ]) {
        expect(await pick(name, bytes), '${tmp.path}/$name');
        expect(await File('${tmp.path}/$name').readAsBytes(), bytes);
      }
    });

    test('the 10 MB cap applies to what will be uploaded', () async {
      // Trailing bytes push the pick over the cap; the resize drops them.
      final path = await pick('heavy.jpg', [
        ...img.encodeJpg(halves(400, 200)),
        ...Uint8List(DeviceForumImagePicker.maxUploadBytes),
      ]);
      expect(await File(path!).length(), lessThan(100000));
    });
  });

  test('the cap mirrors the backend IMAGE_MAX_SIZE_BYTES', () {
    expect(DeviceForumImagePicker.maxUploadBytes, 10 * 1024 * 1024);
  });
}
