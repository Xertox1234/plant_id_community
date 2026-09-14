#!/usr/bin/env node
/**
 * Canopy token extractor — the single source of truth for cross-platform design tokens.
 *
 * Reads the CANONICAL stylesheet (`web/src/index.css`) and emits
 * `design/canopy-tokens.json`: for every semantic `--gt-*` token, both the CSS
 * expression as authored AND the resolved 8-bit sRGB value.
 *
 * WHY THIS EXISTS
 * ---------------
 * ~10 canonical colours are not literals anywhere: the browser computes them
 * from `color-mix(in oklab, …)`. Flutter cannot express an oklab blend
 * (`Color.lerp` is sRGB), so Dart needs the RESOLVED value. Transcribing those
 * by hand is how two platforms silently diverge — so we generate them, commit
 * the result, and pin it from both sides:
 *
 *   - `web/src/__tests__/canopyTokens.test.ts` re-runs this extractor and
 *     asserts it reproduces the committed JSON  → CSS drift fails the build.
 *   - `plant_community_mobile/test/core/theme/canopy_parity_test.dart` asserts
 *     the Dart palette equals the JSON                → Dart drift fails the build.
 *
 * Neither test can pass by coincidence: each compares a different artefact
 * against the same committed contract.
 *
 * GROUND TRUTH
 * ------------
 * The oklab mixing below implements CSS Color Module 4 §12 (premultiplied
 * interpolation in oklab). Its output was verified ONCE against a real browser
 * — Chromium via Playwright, reading `getComputedStyle().backgroundColor` off
 * elements painted with the real stylesheet — by
 * `scripts/design/verify_canopy_tokens_in_browser.mjs`. All 24 mixed values
 * matched to the byte. Re-run that script if you change the maths here;
 * jsdom cannot verify this (it does not implement `color-mix`).
 *
 * Usage:
 *   node scripts/design/extract_canopy_tokens.mjs            # write the JSON
 *   node scripts/design/extract_canopy_tokens.mjs --check    # exit 1 on drift
 *   node scripts/design/extract_canopy_tokens.mjs --stdout   # print, write nothing
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = resolve(HERE, '..', '..');
export const CSS_PATH = resolve(REPO_ROOT, 'web/src/index.css');
export const JSON_PATH = resolve(REPO_ROOT, 'design/canopy-tokens.json');

/* ───────────────────────── colour maths (CSS Color 4) ───────────────────────── */

const srgbToLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const linearToSrgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);

/** sRGB (0..1) → Oklab. Björn Ottosson's matrices, as adopted by CSS Color 4. */
function srgbToOklab([r, g, b]) {
  const lr = srgbToLinear(r);
  const lg = srgbToLinear(g);
  const lb = srgbToLinear(b);
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** Oklab → sRGB (0..1), gamut-clipped per-channel like a browser's final 8-bit paint. */
function oklabToSrgb([L, A, B]) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return [
    linearToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ].map((c) => Math.min(1, Math.max(0, c)));
}

/* ───────────────────────── colour value model ───────────────────────── */

/** A colour is { rgb: [0..1, 0..1, 0..1], alpha: 0..1 }. */
const rgba = (rgb, alpha = 1) => ({ rgb, alpha });

function parseHex(hex) {
  const h = hex.slice(1);
  const full =
    h.length === 3
      ? h
          .split('')
          .map((c) => c + c)
          .join('')
      : h;
  const n = parseInt(full.slice(0, 6), 16);
  const alpha = full.length === 8 ? parseInt(full.slice(6, 8), 16) / 255 : 1;
  return rgba([((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255], alpha);
}

/**
 * CSS Color 4 §12.2 — mix two colours in oklab with PREMULTIPLIED alpha.
 * `p` is the weight of `a` (0..1).
 *
 * The premultiply step is what makes `color-mix(in oklab, X 45%, transparent)`
 * come out as "X at 45% alpha" rather than "X darkened toward black": the
 * transparent side contributes zero premultiplied colour AND zero alpha, so
 * un-premultiplying by the resulting alpha restores X exactly.
 */
function mixOklab(a, b, p) {
  const q = 1 - p;
  const alpha = a.alpha * p + b.alpha * q;
  const la = srgbToOklab(a.rgb);
  const lb = srgbToOklab(b.rgb);
  const premul = la.map((v, i) => v * a.alpha * p + lb[i] * b.alpha * q);
  if (alpha === 0) return rgba([0, 0, 0], 0);
  return rgba(oklabToSrgb(premul.map((v) => v / alpha)), alpha);
}

const to255 = (c) => Math.round(c * 255);
const hex2 = (n) => n.toString(16).padStart(2, '0').toUpperCase();

/** `#RRGGBB`, or `#RRGGBBAA` when the colour carries alpha. */
function formatHex({ rgb, alpha }) {
  const base = `#${rgb.map((c) => hex2(to255(c))).join('')}`;
  return alpha >= 1 ? base : `${base}${hex2(to255(alpha))}`;
}

/** How a browser serialises it — the form the browser-verification script compares against. */
function formatCss({ rgb, alpha }) {
  const [r, g, b] = rgb.map(to255);
  return alpha >= 1
    ? `rgb(${r}, ${g}, ${b})`
    : `rgba(${r}, ${g}, ${b}, ${String(Number(alpha.toFixed(3)))})`;
}

/** Flutter `Color(0xAARRGGBB)` literal — ARGB, alpha first. */
function formatDart({ rgb, alpha }) {
  const [r, g, b] = rgb.map(to255);
  return `0x${hex2(to255(alpha))}${hex2(r)}${hex2(g)}${hex2(b)}`;
}

/* ───────────────────────── expression resolution ───────────────────────── */

/** Split on top-level commas only — `color-mix(a, b)` nested in a list stays intact. */
function splitTopLevel(input, sep = ',') {
  const parts = [];
  let depth = 0;
  let cur = '';
  for (const ch of input) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    if (ch === sep && depth === 0) {
      parts.push(cur.trim());
      cur = '';
    } else cur += ch;
  }
  if (cur.trim()) parts.push(cur.trim());
  return parts;
}

/**
 * Resolve a CSS colour expression to a concrete colour.
 * Handles exactly the forms `index.css` uses: hex, `transparent`, `var(--x)`,
 * `rgba(...)`, and `color-mix(in oklab, A p%, B [q%])`.
 * Throws on anything else rather than guessing — an unknown form must not
 * silently become a wrong colour.
 */
function resolveColor(expr, vars, seen = new Set()) {
  const s = expr.trim();

  if (s === 'transparent') return rgba([0, 0, 0], 0);
  if (/^#[0-9a-f]{3,8}$/i.test(s)) return parseHex(s);

  const varMatch = /^var\(\s*(--[\w-]+)\s*\)$/.exec(s);
  if (varMatch) {
    const name = varMatch[1];
    if (seen.has(name)) throw new Error(`circular var reference: ${name}`);
    if (!(name in vars)) throw new Error(`undefined var: ${name}`);
    return resolveColor(vars[name], vars, new Set([...seen, name]));
  }

  const rgbaMatch = /^rgba?\(([^)]+)\)$/i.exec(s);
  if (rgbaMatch) {
    const n = splitTopLevel(rgbaMatch[1]).map(Number);
    return rgba([n[0] / 255, n[1] / 255, n[2] / 255], n.length > 3 ? n[3] : 1);
  }

  const mixMatch = /^color-mix\(\s*in\s+oklab\s*,\s*([\s\S]+)\)$/i.exec(s);
  if (mixMatch) {
    const [aRaw, bRaw, extra] = splitTopLevel(mixMatch[1]);
    if (extra !== undefined) throw new Error(`color-mix with >2 colours: ${s}`);
    const parse = (raw) => {
      const m = /^([\s\S]+?)\s+([\d.]+)%$/.exec(raw.trim());
      return m
        ? { expr: m[1], pct: Number(m[2]) / 100 }
        : { expr: raw.trim(), pct: null };
    };
    const A = parse(aRaw);
    const B = parse(bRaw);
    // CSS Color 4: an omitted percentage is 100% minus the other one.
    const pa = A.pct ?? (B.pct !== null ? 1 - B.pct : 0.5);
    const pb = B.pct ?? 1 - pa;
    const total = pa + pb;
    return mixOklab(
      resolveColor(A.expr, vars, seen),
      resolveColor(B.expr, vars, seen),
      pa / total
    );
  }

  throw new Error(`unsupported colour expression: ${s}`);
}

/** Substitute every resolvable colour sub-expression inside a gradient. */
function resolveGradient(expr, vars) {
  // Replace the innermost color-mix(...) calls first, then any bare var(--canopy-*).
  let out = expr;
  for (let pass = 0; pass < 10; pass++) {
    const next = out.replace(
      /color-mix\(\s*in\s+oklab\s*,[^()]*(?:\([^()]*\)[^()]*)*\)/gi,
      (m) => formatCss(resolveColor(m, vars))
    );
    if (next === out) break;
    out = next;
  }
  out = out.replace(/var\(\s*(--canopy-[\w-]+)\s*\)/g, (m, name) =>
    formatCss(resolveColor(vars[name], vars))
  );
  return out.replace(/\s+/g, ' ').trim();
}

/* ───────────────────────── CSS parsing ───────────────────────── */

/** Strip comments, then pull `--name: value;` declarations out of one block. */
function declarationsIn(css, selectorPattern) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const re = new RegExp(`${selectorPattern}\\s*\\{`, 'g');
  const m = re.exec(clean);
  if (!m) throw new Error(`selector not found in index.css: ${selectorPattern}`);
  // Walk braces to find the matching close — values contain nested parens, not braces.
  let depth = 1;
  let i = m.index + m[0].length;
  const start = i;
  for (; i < clean.length && depth > 0; i++) {
    if (clean[i] === '{') depth++;
    else if (clean[i] === '}') depth--;
  }
  const body = clean.slice(start, i - 1);

  const out = {};
  const declRe = /(--[\w-]+)\s*:\s*([\s\S]*?);/g;
  let d;
  while ((d = declRe.exec(body)) !== null) out[d[1]] = d[2].trim().replace(/\s+/g, ' ');
  return out;
}

/* ───────────────────────── the contract ───────────────────────── */

/** Semantic colour roles, in the order the design spec lists them (§3.2). */
const COLOR_ROLES = [
  'ground',
  'surface',
  'surface-2',
  'surface-3',
  'ink',
  'ink-2',
  'ink-3',
  'primary',
  'on-primary',
  'secondary',
  'tertiary',
  'clay',
  'on-clay',
  'leaf',
  'berry',
  'sky',
  'ok',
  'warn',
  'error',
  'on-error',
  'line',
  'line-2',
];

const GRADIENT_ROLES = ['grad-card', 'grad-sweep', 'grad-cta', 'grad-ambient'];
const TILE_ROLES = ['tile-sage', 'tile-pollen', 'tile-bloom', 'tile-orchid'];
const SHADOW_ROLES = ['shadow-1', 'shadow-2', 'shadow-3'];

export function extract() {
  const css = readFileSync(CSS_PATH, 'utf8');

  const raw = declarationsIn(css, ':root');
  const darkDecls = declarationsIn(css, ':root,\\s*\\[data-mode=\'dark\'\\]');
  const lightDecls = declarationsIn(css, "\\[data-mode='light'\\]");

  // Light mode only OVERRIDES — anything it does not restate is inherited from dark.
  const darkVars = { ...raw, ...darkDecls };
  const lightVars = { ...darkVars, ...lightDecls };

  const modeBlock = (vars) => {
    const colors = {};
    for (const role of COLOR_ROLES) {
      const key = `--gt-${role}`;
      if (!(key in vars)) throw new Error(`missing semantic token ${key}`);
      const value = resolveColor(vars[key], vars);
      colors[role] = {
        css: vars[key],
        hex: formatHex(value),
        rgba: formatCss(value),
        dart: formatDart(value),
      };
    }
    const gradients = {};
    for (const role of GRADIENT_ROLES) gradients[role] = resolveGradient(vars[`--gt-${role}`], vars);
    const tiles = {};
    for (const role of TILE_ROLES) tiles[role] = resolveGradient(vars[`--gt-${role}`], vars);
    const shadows = {};
    for (const role of SHADOW_ROLES) shadows[role] = vars[`--gt-${role}`].replace(/\s+/g, ' ');
    return { colors, gradients, tiles, shadows };
  };

  // Raw ramp — the ten named Canopy hues, straight literals.
  const ramp = {};
  for (const [k, v] of Object.entries(raw)) {
    if (k.startsWith('--canopy-')) ramp[k.replace('--canopy-', '')] = v.toUpperCase();
  }

  // Density: cozy is the default, declared in the SAME block as the dark
  // semantic tokens (`:root, [data-mode='dark']`) — NOT the bare `:root` raw
  // ramp block. The other two live in their own attribute blocks.
  const density = {
    cozy: {
      padCard: darkVars['--gt-pad-card'],
      padScreen: darkVars['--gt-pad-screen'],
      gap: darkVars['--gt-gap'],
    },
  };
  for (const name of ['comfortable', 'compact']) {
    const d = declarationsIn(css, `\\[data-density='${name}'\\]`);
    density[name] = { padCard: d['--gt-pad-card'], padScreen: d['--gt-pad-screen'], gap: d['--gt-gap'] };
  }

  // Both `@theme { … }` (radius, text scale) and `@theme inline { … }` (the
  // Tailwind colour/font registrations, where --font-* lives).
  const themeBlocks =
    css.replace(/\/\*[\s\S]*?\*\//g, '').match(/@theme(?:\s+inline)?\s*\{[\s\S]*?\n\}/g) ?? [];
  const themeVars = {};
  for (const block of themeBlocks) {
    const declRe = /(--[\w-]+)\s*:\s*([\s\S]*?);/g;
    let d;
    while ((d = declRe.exec(block)) !== null) themeVars[d[1]] = d[2].trim();
  }

  const radius = {};
  for (const k of ['xs', 'sm', 'md', 'lg', 'xl', 'pill']) radius[k] = themeVars[`--radius-${k}`];

  const text = {};
  for (const k of ['micro', 'meta', 'body-sm', 'body', 'body-lg', 'lead', 'hero']) {
    text[k] = { size: themeVars[`--text-${k}`], lineHeight: themeVars[`--text-${k}--line-height`] };
  }

  // Display scale lives in @layer components as .gt-display/.gt-h1/.gt-h2/.gt-h3.
  const display = {};
  const cleanCss = css.replace(/\/\*[\s\S]*?\*\//g, '');
  for (const name of ['display', 'h1', 'h2', 'h3']) {
    const m = new RegExp(`\\.gt-${name}\\s*\\{([\\s\\S]*?)\\}`).exec(cleanCss);
    if (!m) throw new Error(`missing .gt-${name} rule`);
    const body = m[1];
    const pick = (prop) => {
      const p = new RegExp(`(?:^|;|\\s)${prop}\\s*:\\s*([^;]+)`).exec(body);
      return p ? p[1].trim() : null;
    };
    display[name] = {
      fontFamily: 'display',
      fontWeight: Number(pick('font-weight')),
      fontSize: pick('font-size'),
      lineHeight: Number(pick('line-height')),
      letterSpacing: pick('letter-spacing'),
      fontStyle: pick('font-style') ?? 'normal',
    };
  }

  const labelRule = /\.gt-label\s*\{([\s\S]*?)\}/.exec(cleanCss);
  const labelBody = labelRule ? labelRule[1] : '';
  const labelPick = (prop) => {
    const p = new RegExp(`(?:^|;|\\s)${prop}\\s*:\\s*([^;]+)`).exec(labelBody);
    return p ? p[1].trim() : null;
  };

  return {
    $schema: 'https://houseplant-md.dev/schemas/canopy-tokens-1.json',
    $generator: 'scripts/design/extract_canopy_tokens.mjs',
    $source: 'web/src/index.css',
    $doc: [
      'CANONICAL cross-platform design token contract for the Canopy design language.',
      'GENERATED — do not hand-edit. Change web/src/index.css and re-run the generator.',
      'Every `color-mix(in oklab, ...)` is resolved here because Flutter cannot express',
      'an oklab blend; the resolved values were verified byte-for-byte against Chromium',
      'via scripts/design/verify_canopy_tokens_in_browser.mjs.',
    ].join(' '),
    ramp,
    modes: { dark: modeBlock(darkVars), light: modeBlock(lightVars) },
    defaults: { mode: 'dark', density: 'cozy' },
    density,
    radius,
    text,
    display,
    label: {
      fontFamily: 'mono',
      fontSize: labelPick('font-size'),
      letterSpacing: labelPick('letter-spacing'),
      textTransform: labelPick('text-transform'),
      color: 'ink-3',
    },
    fonts: {
      display: themeVars['--font-display'],
      sans: themeVars['--font-sans'],
      mono: themeVars['--font-mono'],
    },
  };
}

/* ───────────────────────── CLI ───────────────────────── */

export const serialize = (tokens) => `${JSON.stringify(tokens, null, 2)}\n`;

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  const tokens = extract();
  const text = serialize(tokens);

  if (process.argv.includes('--stdout')) {
    process.stdout.write(text);
  } else if (process.argv.includes('--check')) {
    let existing = null;
    try {
      existing = readFileSync(JSON_PATH, 'utf8');
    } catch {
      console.error(`✗ ${JSON_PATH} does not exist — run the generator.`);
      process.exit(1);
    }
    if (existing !== text) {
      console.error('✗ design/canopy-tokens.json is stale — re-run the generator.');
      process.exit(1);
    }
    console.log('✓ design/canopy-tokens.json matches web/src/index.css');
  } else {
    mkdirSync(dirname(JSON_PATH), { recursive: true });
    writeFileSync(JSON_PATH, text);
    console.log(`✓ wrote ${JSON_PATH}`);
  }
}
