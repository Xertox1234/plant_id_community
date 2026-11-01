/**
 * Per-forum themes (todo 681): every theme index.css defines is a token scope
 * for BOTH modes, and its text passes WCAG contrast in light and dark.
 *
 * Reads index.css itself, so a hex edited there is checked here. Thresholds:
 * 4.5:1 for body text (ink, ink-2, on-primary on primary), 3:1 for the
 * muted ink-3 labels and for the mode's own accent tokens (todo 669's forum
 * colour sits on top of a theme, owner decision 2026-10-30), which render as
 * rings, icons and large text.
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';
import { FORUM_THEMES } from './forumDisplay';

// Vitest runs from web/ (the jsdom environment gives no file: import.meta.url).
const CSS_PATH = [
  resolve(process.cwd(), 'src/index.css'),
  resolve(process.cwd(), 'web/src/index.css'),
].find((path) => existsSync(path));
if (!CSS_PATH) throw new Error('cannot find web/src/index.css from the working directory');
const css = readFileSync(CSS_PATH, 'utf8');

type Tokens = Record<string, string>;

function block(selector: string): Tokens {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`index.css has no block for ${selector}`);
  const body = css.slice(start + selector.length + 2, css.indexOf('}', start));
  const tokens: Tokens = {};
  for (const match of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) tokens[match[1]] = match[2].trim();
  return tokens;
}

const root = block(':root');

/** A token's hex, resolving one `var(--canopy-*)` hop to :root. */
function hex(tokens: Tokens, name: string): string {
  const value = tokens[name];
  if (!value) throw new Error(`missing ${name}`);
  const ref = value.match(/^var\((--[\w-]+)\)$/);
  const resolved = ref ? root[ref[1]] : value;
  if (!resolved || !/^#[0-9a-f]{6}$/i.test(resolved)) {
    throw new Error(`${name} is not a literal hex: ${value}`);
  }
  return resolved;
}

function luminance(color: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(color.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const SURFACES = ['--gt-ground', '--gt-surface', '--gt-surface-2', '--gt-surface-3'];
const ACCENTS = ['--gt-leaf', '--gt-tertiary', '--gt-berry', '--gt-sky'];

describe('forum theme contrast (todo 681)', () => {
  it('computes WCAG contrast correctly', () => {
    expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 1);
    expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 1);
  });

  it('defines exactly the four owner themes', () => {
    expect([...FORUM_THEMES]).toEqual(['botanical', 'moss', 'terracotta', 'slate']);
    const defined = new Set(
      [...css.matchAll(/\[data-forum-theme='([\w-]+)'\]/g)].map((match) => match[1])
    );
    expect([...defined].sort()).toEqual([...FORUM_THEMES].sort());
  });

  for (const mode of ['light', 'dark'] as const) {
    const base = block(`[data-mode='${mode}']`);
    for (const theme of FORUM_THEMES) {
      it(`${theme} passes in ${mode} mode`, () => {
        const tokens = block(`[data-mode='${mode}'] [data-forum-theme='${theme}']`);
        const failures: string[] = [];
        const check = (fg: string, fgHex: string, bg: string, min: number) => {
          const ratio = contrast(fgHex, hex(tokens, bg));
          if (ratio < min) failures.push(`${fg} on ${bg}: ${ratio.toFixed(2)} < ${min}`);
        };
        for (const surface of SURFACES) {
          check('--gt-ink', hex(tokens, '--gt-ink'), surface, 4.5);
          check('--gt-ink-2', hex(tokens, '--gt-ink-2'), surface, 4.5);
          check('--gt-ink-3', hex(tokens, '--gt-ink-3'), surface, 3);
          for (const accent of ACCENTS) check(accent, hex(base, accent), surface, 3);
        }
        check('--gt-on-primary', hex(tokens, '--gt-on-primary'), '--gt-primary', 4.5);
        expect(failures).toEqual([]);
      });
    }
  }
});
