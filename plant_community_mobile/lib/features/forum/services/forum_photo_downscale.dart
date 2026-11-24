import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;

/// Encode qualities to try, best first, until the result fits the byte cap.
const _jpegQualities = [92, 85, 75];

/// [path], or the path of a smaller JPEG copy when it is a JPEG or an opaque
/// still WebP with a side over [maxEdgePx] (audit 2026-11-24 F207).
///
/// Everything else comes back untouched: a PNG or GIF stays byte-exact, and a
/// file that cannot be decoded is left for the server to name. The copy keeps
/// the shape, is upright (the decoder applies the EXIF turn, and the copy
/// carries no EXIF to apply it again), and holds at most [maxBytes] when a
/// quality we would accept allows it.
Future<String> downscaleForumPhoto(
  String path, {
  required int maxEdgePx,
  required int maxBytes,
}) async {
  if (!await _isJpegOrWebP(path)) return path;
  final ByteData? pixels;
  final int width;
  final int height;
  try {
    final buffer = await ui.ImmutableBuffer.fromFilePath(path);
    var oversized = false;
    // The callback sees the size before the pixels are decoded, so the full
    // bitmap of a 48 MP photo is never asked for.
    final codec = await ui.instantiateImageCodecWithSize(
      buffer,
      getTargetSize: (w, h) {
        final longest = math.max(w, h);
        oversized = longest > maxEdgePx;
        if (!oversized) return const ui.TargetImageSize();
        final scale = maxEdgePx / longest;
        return ui.TargetImageSize(
          width: math.max(1, (w * scale).round()),
          height: math.max(1, (h * scale).round()),
        );
      },
    );
    try {
      if (!oversized || codec.frameCount != 1) return path;
      final image = (await codec.getNextFrame()).image;
      width = image.width;
      height = image.height;
      try {
        pixels = await image.toByteData();
      } finally {
        image.dispose();
      }
    } finally {
      codec.dispose();
    }
  } catch (_) {
    return path;
  }
  if (pixels == null) return path;

  final jpeg = await compute(_encodeJpeg, (
    rgba: pixels.buffer.asUint8List(pixels.offsetInBytes, pixels.lengthInBytes),
    width: width,
    height: height,
    maxBytes: maxBytes,
  ));
  if (jpeg == null) return path;

  // A folder of its own: two photos may share a name, and the upload's
  // idempotency key is per path. [discardForumPhotoCopy] removes it.
  final dir = await Directory.systemTemp.createTemp(_copyDirPrefix);
  final out = File(p.join(dir.path, '${p.basenameWithoutExtension(path)}.jpg'));
  await out.writeAsBytes(jpeg, flush: true);
  return out.path;
}

const _copyDirPrefix = 'forum_downscaled_';

/// Deletes [path] if it is a copy [downscaleForumPhoto] made; the member's own
/// file is never touched. Call it once the upload is over.
Future<void> discardForumPhotoCopy(String path) async {
  final dir = File(path).parent;
  if (!p.basename(dir.path).startsWith(_copyDirPrefix)) return;
  try {
    await dir.delete(recursive: true);
  } on FileSystemException {
    // Temporary storage: the system clears what is left.
  }
}

/// By the file's first bytes: a picked name's extension is not reliable.
Future<bool> _isJpegOrWebP(String path) async {
  final head = <int>[];
  await for (final chunk in File(path).openRead(0, 12)) {
    head.addAll(chunk);
  }
  bool at(int offset, String ascii) =>
      head.length >= offset + ascii.length &&
      String.fromCharCodes(head, offset, offset + ascii.length) == ascii;
  final jpeg = at(0, '\xFF\xD8\xFF');
  return jpeg || (at(0, 'RIFF') && at(8, 'WEBP'));
}

/// `null` for a picture with any transparency: JPEG cannot carry it.
Uint8List? _encodeJpeg(
  ({Uint8List rgba, int width, int height, int maxBytes}) job,
) {
  for (var i = 3; i < job.rgba.length; i += 4) {
    if (job.rgba[i] != 255) return null;
  }
  final image = img.Image.fromBytes(
    width: job.width,
    height: job.height,
    bytes: job.rgba.buffer,
    bytesOffset: job.rgba.offsetInBytes,
    numChannels: 4,
  );
  late Uint8List jpeg;
  for (final quality in _jpegQualities) {
    jpeg = img.encodeJpg(image, quality: quality);
    if (jpeg.length <= job.maxBytes) break;
  }
  return jpeg;
}
