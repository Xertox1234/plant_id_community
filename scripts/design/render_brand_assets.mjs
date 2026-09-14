#!/usr/bin/env node
/**
 * Render every app-icon and launch-image PNG from the ONE canonical brand mark.
 *
 * WHY THIS EXISTS -- the Houseplant MD mark is a vector, defined once at
 * web/public/favicon.svg and ported to Flutter as lib/shared/widgets/brand_mark.dart.
 * Until now the shipped app icon was Flutter's default placeholder, so the icon on
 * the home screen had nothing to do with the mark on the screen it opened to.
 * Hand-exporting 23 PNGs would re-create that drift the first time the mark changed,
 * so nothing here is hand-made: every file is derived from the SVG, and re-running
 * this script is how you update them.
 *
 * WHY CHROMIUM -- this repo already trusts Chromium as a rasteriser. The Canopy
 * token contract is pinned to Chromium's painted pixels by
 * verify_canopy_tokens_in_browser.mjs, for the same reason that applies here:
 * it is the renderer whose output users actually see, and it needs no native
 * image toolchain (rsvg/inkscape/imagemagick are all absent on this machine).
 * Each size is rendered natively from the vector rather than downscaled from
 * 1024, so small icons stay crisp instead of going muddy.
 *
 * TWO SHAPES, DELIBERATELY -- but split by ROLE, not by platform:
 *
 *   icons    full-bleed square (rx -> 0), iOS and Android alike. Both platforms
 *            mask app icons themselves, so shipping the already-rounded tile
 *            rounds it twice: a launcher that masks leaves dark wedges outside
 *            its mask, and one that does not shows the tile floating on a square
 *            of backdrop. The badge survives the mask -- its farthest point sits
 *            123px from the corner arc's centre at 1024px, against Apple's
 *            ~229px radius.
 *   launch   the rounded tile as drawn, centred on the ground. Here the mark IS
 *            a logo presented on a background, so the radius is the point.
 *
 * The guard caught this: rendering Android as the rounded tile put the abyss
 * ground in the corner where check_brand_assets.py expects the pine tile.
 *
 * NO ALPHA CHANNEL. Apple rejects app icons containing one. Chromium always
 * writes RGBA, so every icon is re-encoded here as PNG colour type 2 (truecolour,
 * no alpha) after asserting every pixel is already fully opaque -- a transparent
 * pixel means the artwork did not cover the canvas and is a hard error, not
 * something to silently flatten onto a guessed background.
 *
 * Usage:
 *   node scripts/design/render_brand_assets.mjs           # write all assets
 *   node scripts/design/render_brand_assets.mjs --check   # render, compare, write nothing
 *   SVG=path/to/other.svg node scripts/design/render_brand_assets.mjs
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { deflateSync, inflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');

// Resolve Playwright from web/node_modules, matching
// verify_canopy_tokens_in_browser.mjs. A bare `import 'playwright'` resolves
// relative to THIS file and finds the repo root's older @playwright/test, whose
// Chromium build is not the one installed -- the launch then fails with a
// browser-not-found that reads like a missing install rather than a wrong one.
const require = createRequire(resolve(REPO, 'web/package.json'));
const { chromium } = require('playwright');
const MOBILE = join(REPO, 'plant_community_mobile');
const ICONSET = join(MOBILE, 'ios/Runner/Assets.xcassets/AppIcon.appiconset');
const LAUNCHSET = join(MOBILE, 'ios/Runner/Assets.xcassets/LaunchImage.imageset');
const RES = join(MOBILE, 'android/app/src/main/res');

const SVG_PATH = process.env.SVG || join(REPO, 'web/public/favicon.svg');
const CHECK_ONLY = process.argv.includes('--check');

/** Canopy abyss -- the dark ground the app's first painted frame uses. */
const LAUNCH_GROUND = '#051F20';
/** Launch mark size in points; iOS shows LaunchImage at its natural size. */
const LAUNCH_PT = 120;

/** Android legacy mipmap densities. */
const ANDROID = [
  ['mipmap-mdpi', 48],
  ['mipmap-hdpi', 72],
  ['mipmap-xhdpi', 96],
  ['mipmap-xxhdpi', 144],
  ['mipmap-xxxhdpi', 192],
];

const die = (msg) => {
  console.error(`ERROR: ${msg}`);
  process.exit(1);
};

// ------------------------------------------------------------------ PNG ----
// Minimal PNG decode/encode. Only what Chromium emits (8-bit, non-interlaced)
// and only what Apple accepts (colour type 2) -- not a general codec.

const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/** Decode an 8-bit non-interlaced PNG to {width, height, channels, pixels}. */
function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) die('not a PNG');
  let off = 8;
  let ihdr = null;
  const idat = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('ascii', off + 4, off + 8);
    const data = buf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') {
      ihdr = {
        width: data.readUInt32BE(0),
        height: data.readUInt32BE(4),
        depth: data[8],
        colorType: data[9],
        interlace: data[12],
      };
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    off += 12 + len;
  }
  if (!ihdr) die('PNG has no IHDR');
  if (ihdr.depth !== 8) die(`expected 8-bit PNG, got ${ihdr.depth}-bit`);
  if (ihdr.interlace !== 0) die('interlaced PNG not supported');
  const channels = { 2: 3, 6: 4 }[ihdr.colorType];
  if (!channels) die(`unsupported PNG colour type ${ihdr.colorType}`);

  const raw = inflateSync(Buffer.concat(idat));
  const { width, height } = ihdr;
  const stride = width * channels;
  const out = Buffer.alloc(stride * height);

  // Undo per-scanline filters (PNG spec 9.2).
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const src = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const cur = out.subarray(y * stride, (y + 1) * stride);
    const prior = y > 0 ? out.subarray((y - 1) * stride, y * stride) : null;
    for (let i = 0; i < stride; i++) {
      const a = i >= channels ? cur[i - channels] : 0;
      const b = prior ? prior[i] : 0;
      const c = prior && i >= channels ? prior[i - channels] : 0;
      let v = src[i];
      if (filter === 1) v += a;
      else if (filter === 2) v += b;
      else if (filter === 3) v += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      } else if (filter !== 0) die(`bad PNG filter ${filter} on row ${y}`);
      cur[i] = v & 0xff;
    }
  }
  return { width, height, channels, pixels: out };
}

/** Re-encode as colour type 2 (RGB, no alpha), refusing any non-opaque pixel. */
function encodeRgbPng({ width, height, channels, pixels }, label) {
  const stride = width * 3;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0; // filter: none
    for (let x = 0; x < width; x++) {
      const s = (y * width + x) * channels;
      if (channels === 4 && pixels[s + 3] !== 255) {
        die(
          `${label}: pixel (${x},${y}) has alpha ${pixels[s + 3]}, not 255. The ` +
            `artwork does not cover the canvas; refusing to guess a background.`
        );
      }
      const d = y * (stride + 1) + 1 + x * 3;
      raw[d] = pixels[s];
      raw[d + 1] = pixels[s + 1];
      raw[d + 2] = pixels[s + 2];
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type: truecolour, no alpha
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// --------------------------------------------------------------- render ----

/**
 * The iOS variant drops the tile's corner radius so the system mask is the only
 * rounding. Asserted rather than assumed: a mark whose tile stops using rx would
 * silently render identically for both platforms.
 */
function fullBleed(svg) {
  if (!/<rect[^>]*\brx="18"/.test(svg)) {
    die(
      'the canonical SVG no longer has a tile <rect ... rx="18">. The iOS ' +
        'full-bleed variant is produced by zeroing that radius; re-check the ' +
        'mark before trusting this script.'
    );
  }
  return svg.replace(/(<rect[^>]*\b)rx="18"/, '$1rx="0"');
}

function page(svg, size, { ground = null, inset = null } = {}) {
  const art = inset
    ? `<div style="width:${inset}px;height:${inset}px">${svg}</div>`
    : svg;
  return `<!doctype html><html><body style="margin:0;background:${ground ?? 'transparent'}">
<div style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center">
${art.replace(/<svg([^>]*)width="64"([^>]*)height="64"/, `<svg$1width="100%"$2height="100%"`)}
</div></body></html>`;
}

async function shoot(browser, html, size) {
  const p = await browser.newPage({
    viewport: { width: size, height: size },
    deviceScaleFactor: 1,
  });
  await p.setContent(html, { waitUntil: 'load' });
  const buf = await p.screenshot({ type: 'png', omitBackground: false });
  await p.close();
  return buf;
}

/** iOS sizes come from the asset catalogue itself, so the two cannot drift. */
function iosTargets() {
  const cj = JSON.parse(readFileSync(join(ICONSET, 'Contents.json'), 'utf8'));
  const seen = new Map();
  for (const img of cj.images) {
    if (!img.filename) continue;
    const px = Math.round(parseFloat(img.size) * parseFloat(img.scale));
    const prev = seen.get(img.filename);
    if (prev && prev !== px) {
      die(`${img.filename} is claimed at both ${prev}px and ${px}px in Contents.json`);
    }
    seen.set(img.filename, px);
  }
  if (seen.size === 0) die('Contents.json lists no icon filenames');
  return [...seen.entries()];
}

function emit(path, buf, written, stale) {
  if (CHECK_ONLY) {
    const same = existsSync(path) && Buffer.compare(readFileSync(path), buf) === 0;
    if (!same) stale.push(path.replace(REPO + '/', ''));
    return;
  }
  writeFileSync(path, buf);
  written.push(path.replace(REPO + '/', ''));
}

async function main() {
  if (!existsSync(SVG_PATH)) die(`canonical mark not found at ${SVG_PATH}`);
  const svg = readFileSync(SVG_PATH, 'utf8');
  if (!svg.includes('<svg')) die(`${SVG_PATH} is not an SVG`);

  const squared = fullBleed(svg);
  const browser = await chromium.launch();
  const written = [];
  const stale = [];

  try {
    // iOS app icons -- full-bleed, opaque.
    for (const [filename, px] of iosTargets()) {
      const png = await shoot(browser, page(squared, px), px);
      emit(join(ICONSET, filename), encodeRgbPng(decodePng(png), filename), written, stale);
    }

    // Android legacy mipmaps -- full-bleed, same as iOS: launchers mask too.
    for (const [dir, px] of ANDROID) {
      const png = await shoot(browser, page(squared, px), px);
      const label = `${dir}/ic_launcher.png`;
      emit(join(RES, dir, 'ic_launcher.png'), encodeRgbPng(decodePng(png), label), written, stale);
    }

    // Launch image -- the mark centred on the ground the app opens to.
    for (const [suffix, scale] of [['', 1], ['@2x', 2], ['@3x', 3]]) {
      const px = LAUNCH_PT * scale;
      const html = page(svg, px, { ground: LAUNCH_GROUND, inset: px });
      const png = await shoot(browser, html, px);
      const label = `LaunchImage${suffix}.png`;
      emit(join(LAUNCHSET, label), encodeRgbPng(decodePng(png), label), written, stale);
    }
  } finally {
    await browser.close();
  }

  if (CHECK_ONLY) {
    if (stale.length) {
      console.error(
        `ERROR: ${stale.length} brand asset(s) differ from a fresh render of ` +
          `${SVG_PATH.replace(REPO + '/', '')}:\n` +
          stale.map((s) => `    ${s}`).join('\n') +
          `\nRe-run: node scripts/design/render_brand_assets.mjs`
      );
      process.exit(1);
    }
    console.log('OK: every brand asset matches a fresh render of the canonical mark.');
    return;
  }
  console.log(`Rendered ${written.length} assets from ${SVG_PATH.replace(REPO + '/', '')}:`);
  for (const w of written) console.log(`    ${w}`);
}

await main();
