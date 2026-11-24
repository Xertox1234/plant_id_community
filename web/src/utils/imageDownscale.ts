/**
 * Shrink an over-size photo in the browser before it is uploaded (audit F207).
 *
 * The forum refuses an image wider or taller than 5000 px
 * (wagtail_forum conf IMAGE_MAX_WIDTH / IMAGE_MAX_HEIGHT), which ordinary
 * 24 and 48 MP phone photos are. The same format comes back, and the shape the
 * reader sees: both the measured size and the drawing follow the photo's EXIF
 * orientation, because they go through an <img>.
 */

/** Mirrors the server's per-side limit. */
export const MAX_IMAGE_SIDE = 5000;
/** 4096 x 4096 is also the largest canvas older iOS Safari will draw. */
const TARGET_SIDE = 4096;
const JPEG_WEBP_QUALITY = 0.9;

/** The photo is over the limit and could not be shrunk; `message` is for the author. */
export class ImageTooLargeError extends Error {
  constructor(width: number, height: number) {
    super(
      `This image is ${width} × ${height} pixels and could not be made smaller here. ` +
        `The limit is ${MAX_IMAGE_SIDE} pixels on each side, so resize it and try again.`
    );
    this.name = 'ImageTooLargeError';
  }
}

/** Whether this browser can read an image's size before upload. */
export function canMeasureImages(): boolean {
  return typeof HTMLImageElement.prototype.decode === 'function';
}

/** An animated WebP sets the ANIM bit in its VP8X header; a canvas would keep one frame. */
async function isAnimatedWebp(file: File): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 21).arrayBuffer());
  return (
    head.length >= 21 &&
    String.fromCharCode(...head.slice(8, 16)) === 'WEBPVP8X' &&
    (head[20] & 0x02) !== 0
  );
}

/**
 * `file` itself when it is within the limit (or cannot be decoded here: the
 * server then decides), otherwise a smaller copy. Throws ImageTooLargeError
 * when it is over the limit and cannot be shrunk without changing what it is.
 */
export async function downscaleForUpload(file: File): Promise<File> {
  if (!canMeasureImages()) return file;
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    try {
      await image.decode();
    } catch {
      return file;
    }
    const { naturalWidth: width, naturalHeight: height } = image;
    if (width <= MAX_IMAGE_SIDE && height <= MAX_IMAGE_SIDE) return file;
    if (file.type === 'image/gif' || (file.type === 'image/webp' && (await isAnimatedWebp(file)))) {
      throw new ImageTooLargeError(width, height);
    }
    const scale = TARGET_SIDE / Math.max(width, height);
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new ImageTooLargeError(width, height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, file.type, JPEG_WEBP_QUALITY)
    );
    // A browser that cannot write the type silently answers with a PNG.
    if (!blob || blob.type !== file.type) throw new ImageTooLargeError(width, height);
    return new File([blob], file.name, { type: file.type, lastModified: file.lastModified });
  } finally {
    URL.revokeObjectURL(url);
  }
}
