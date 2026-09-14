#!/usr/bin/env node
/**
 * GROUND-TRUTH check for the Canopy token extractor.
 *
 * `extract_canopy_tokens.mjs` resolves `color-mix(in oklab, …)` in JavaScript
 * because Flutter needs a concrete sRGB value. This script proves that maths
 * matches what a browser actually paints, which is the only definition of
 * "correct" that matters — the web IS the canonical reference.
 *
 * It does NOT re-implement anything: it injects the real `:root`,
 * `[data-mode='dark']` and `[data-mode='light']` declaration blocks lifted
 * verbatim out of `web/src/index.css`, paints one element per semantic token
 * with `background-color: var(--gt-<role>)`, and reads back
 * `getComputedStyle().backgroundColor` — Chromium's own resolution of the real
 * expression. Any disagreement with the committed JSON is a real defect.
 *
 * jsdom cannot stand in for this: it does not implement `color-mix`, so a
 * Vitest parity test would pass while being blind to the only hard part.
 *
 * Run:  node scripts/design/verify_canopy_tokens_in_browser.mjs
 * Needs Chromium from web/node_modules (@playwright/test).
 */

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { extract, CSS_PATH, REPO_ROOT } from './extract_canopy_tokens.mjs';

const require = createRequire(resolve(REPO_ROOT, 'web/package.json'));
const { chromium } = require('playwright');

/** Lift one `selector { … }` block out of the stylesheet, verbatim. */
function blockFor(css, selectorPattern) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const m = new RegExp(`${selectorPattern}\\s*\\{`, 'g').exec(clean);
  if (!m) throw new Error(`selector not found: ${selectorPattern}`);
  let depth = 1;
  let i = m.index + m[0].length;
  const start = i;
  for (; i < clean.length && depth > 0; i++) {
    if (clean[i] === '{') depth++;
    else if (clean[i] === '}') depth--;
  }
  return clean.slice(start, i - 1);
}

const css = readFileSync(CSS_PATH, 'utf8');
const tokens = extract();

const rampBlock = blockFor(css, ':root');
const darkBlock = blockFor(css, ":root,\\s*\\[data-mode='dark'\\]");
const lightBlock = blockFor(css, "\\[data-mode='light'\\]");

const roles = Object.keys(tokens.modes.dark.colors);

const page_html = `<!doctype html><html><head><style>
  :root { ${rampBlock} }
  [data-mode='dark'] { ${darkBlock} }
  [data-mode='light'] { ${lightBlock} }
  i { display:block; width:4px; height:4px; }
</style></head><body>
  <div id="dark" data-mode="dark">${roles
    .map((r) => `<i id="dark-${r}" style="background-color: var(--gt-${r})"></i>`)
    .join('')}</div>
  <div id="light" data-mode="light">${roles
    .map((r) => `<i id="light-${r}" style="background-color: var(--gt-${r})"></i>`)
    .join('')}</div>
</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent(page_html);

const actual = await page.evaluate(
  ([roles]) => {
    // Chromium keeps a `color-mix(in oklab, …)` computed value IN oklab — it
    // neither serialises to sRGB nor converts on a canvas `fillStyle`
    // round-trip. So force actual rasterisation: paint the token over an
    // opaque black backdrop and again over white, and read the pixels.
    //
    // Two composites pin the colour AND the alpha independently
    // (over black: c·a; over white: c·a + 255·(1−a)), and they are literally
    // the pixels a user sees — the only definition of correct that matters.
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const over = (backdrop, color) => {
      ctx.globalCompositeOperation = 'copy';
      ctx.fillStyle = backdrop;
      ctx.fillRect(0, 0, 1, 1);
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 1, 1);
      return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3);
    };
    const out = {};
    for (const mode of ['dark', 'light']) {
      out[mode] = {};
      for (const r of roles) {
        const computed = getComputedStyle(document.getElementById(`${mode}-${r}`)).backgroundColor;
        out[mode][r] = {
          computed,
          onBlack: over('#000000', computed),
          onWhite: over('#ffffff', computed),
        };
      }
    }
    return out;
  },
  [roles]
);

await browser.close();

/** Composite `rgba(r,g,b,a)` over an opaque 8-bit backdrop, source-over in sRGB. */
function composite(rgbaStr, backdrop) {
  const n = rgbaStr.match(/[\d.]+/g).map(Number);
  const a = n.length > 3 ? n[3] : 1;
  return [0, 1, 2].map((i) => Math.round(n[i] * a + backdrop * (1 - a)));
}

let failures = 0;
let mixed = 0;
let maxDelta = 0;
for (const mode of ['dark', 'light']) {
  for (const role of roles) {
    const expected = tokens.modes[mode].colors[role];
    if (expected.css.includes('color-mix')) mixed++;
    const got = actual[mode][role];

    const mineBlack = composite(expected.rgba, 0);
    const mineWhite = composite(expected.rgba, 255);
    const deltas = [
      ...got.onBlack.map((v, i) => Math.abs(v - mineBlack[i])),
      ...got.onWhite.map((v, i) => Math.abs(v - mineWhite[i])),
    ];
    const delta = Math.max(...deltas);
    maxDelta = Math.max(maxDelta, delta);

    // An OPAQUE token must match exactly: composited over black it IS the
    // colour, so any difference at all means the oklab maths is wrong. These
    // are the four values Dart hard-codes, so they get the strict bound.
    // A TRANSLUCENT fill is rounded to 8 bits once by the browser's
    // premultiplied backing store and once by `composite()` here, so it is
    // allowed to land 1/255 away — the same colour, a different rounding.
    const tolerance = expected.rgba.startsWith('rgba') ? 1 : 0;
    if (delta > tolerance) {
      failures++;
      console.error(
        `✗ ${mode}/${role}  (off by ${delta}/255)\n` +
          `    expression  : ${expected.css}\n` +
          `    computed    : ${got.computed}\n` +
          `    extractor   : ${expected.rgba}  (${expected.hex})\n` +
          `    over black  : chromium ${got.onBlack.join(',')}   extractor ${mineBlack.join(',')}\n` +
          `    over white  : chromium ${got.onWhite.join(',')}   extractor ${mineWhite.join(',')}`
      );
    }
  }
}

const total = roles.length * 2;
if (failures) {
  console.error(`\n✗ ${failures}/${total} tokens disagree with Chromium.`);
  process.exit(1);
}
console.log(
  `✓ all ${total} semantic tokens match Chromium's painted pixels ` +
    `(${mixed} resolved from color-mix(in oklab, …); max delta ${maxDelta}/255)`
);
