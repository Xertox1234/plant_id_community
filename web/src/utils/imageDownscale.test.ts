import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  canMeasureImages,
  downscaleForUpload,
  ImageTooLargeError,
  MAX_IMAGE_SIDE,
} from './imageDownscale';

const file = (type: string, name: string, bytes: BlobPart[] = ['original']) =>
  new File(bytes, name, { type, lastModified: 42 });

describe('downscaleForUpload (audit F207)', () => {
  const drawImage = vi.fn();
  let natural = { width: 0, height: 0 };
  let drawn: { width: number; height: number } | null = null;
  let encodeAs: (type: string) => string | null = (type) => type;

  beforeEach(() => {
    drawn = null;
    encodeAs = (type) => type;
    drawImage.mockReset();
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
    Object.defineProperty(HTMLImageElement.prototype, 'decode', {
      configurable: true,
      value: () => Promise.resolve(),
    });
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockImplementation(
      () => natural.width
    );
    vi.spyOn(HTMLImageElement.prototype, 'naturalHeight', 'get').mockImplementation(
      () => natural.height
    );
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(
      () => ({ drawImage }) as unknown as CanvasRenderingContext2D
    );
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      callback,
      type
    ) {
      drawn = { width: this.width, height: this.height };
      const encoded = encodeAs(type ?? 'image/png');
      callback(encoded ? new Blob(['small'], { type: encoded }) : null);
    });
  });

  afterEach(() => {
    delete (HTMLImageElement.prototype as { decode?: unknown }).decode;
    vi.restoreAllMocks();
  });

  it('shrinks a 24 MP phone photo under the server limit and keeps its shape and format', async () => {
    natural = { width: 5712, height: 4284 };
    const result = await downscaleForUpload(file('image/jpeg', 'IMG_1.jpg'));
    expect(result.type).toBe('image/jpeg');
    expect(result.name).toBe('IMG_1.jpg');
    expect(result.lastModified).toBe(42);
    expect(drawn!.width).toBe(4096);
    expect(drawn!.width).toBeLessThanOrEqual(MAX_IMAGE_SIDE);
    expect(drawn!.width / drawn!.height).toBeCloseTo(5712 / 4284, 2);
    expect(drawImage).toHaveBeenCalledWith(
      expect.any(HTMLImageElement),
      0,
      0,
      drawn!.width,
      drawn!.height
    );
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x');
  });

  it('keeps a portrait photo portrait', async () => {
    natural = { width: 4284, height: 5712 };
    await downscaleForUpload(file('image/webp', 'p.webp'));
    expect(drawn!.height).toBe(4096);
    expect(drawn!.width).toBeLessThan(drawn!.height);
  });

  it('keeps a PNG a PNG', async () => {
    natural = { width: 6000, height: 100 };
    const result = await downscaleForUpload(file('image/png', 'p.png'));
    expect(result.type).toBe('image/png');
  });

  it.each([
    [4032, 3024],
    [5000, 5000],
  ])('returns a %ix%i photo untouched', async (width, height) => {
    natural = { width, height };
    const original = file('image/jpeg', 'ok.jpg');
    expect(await downscaleForUpload(original)).toBe(original);
    expect(drawn).toBeNull();
  });

  it('never flattens an animation: an oversized GIF or animated WebP is refused', async () => {
    natural = { width: 6000, height: 6000 };
    await expect(downscaleForUpload(file('image/gif', 'a.gif'))).rejects.toThrow(
      ImageTooLargeError
    );
    const header = new Uint8Array(30);
    header.set(new TextEncoder().encode('RIFF'), 0);
    header.set(new TextEncoder().encode('WEBPVP8X'), 8);
    header[20] = 0x02; // the ANIM flag
    await expect(downscaleForUpload(file('image/webp', 'a.webp', [header]))).rejects.toThrow(
      /6000 × 6000.*5000/
    );
    expect(drawn).toBeNull();
  });

  it('refuses rather than uploading another format than the browser could write', async () => {
    natural = { width: 6000, height: 4000 };
    encodeAs = () => 'image/png'; // Safari cannot encode WebP
    await expect(downscaleForUpload(file('image/webp', 'p.webp'))).rejects.toThrow(
      ImageTooLargeError
    );
    encodeAs = () => null;
    await expect(downscaleForUpload(file('image/jpeg', 'p.jpg'))).rejects.toThrow(
      ImageTooLargeError
    );
  });

  it('leaves the file to the server when the browser cannot decode it', async () => {
    Object.defineProperty(HTMLImageElement.prototype, 'decode', {
      configurable: true,
      value: () => Promise.reject(new Error('bad image')),
    });
    const original = file('image/jpeg', 'broken.jpg');
    expect(await downscaleForUpload(original)).toBe(original);
    delete (HTMLImageElement.prototype as { decode?: unknown }).decode;
    expect(canMeasureImages()).toBe(false);
    expect(await downscaleForUpload(original)).toBe(original);
  });
});
