import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
// The extractor is plain ESM Node, deliberately outside src/ — it is a build
// tool shared by both platforms, not app code.
import {
  extract,
  serialize,
  JSON_PATH,
  CSS_PATH,
} from '../../../scripts/design/extract_canopy_tokens.mjs';

/**
 * Web half of the cross-platform token guard.
 *
 * `design/canopy-tokens.json` is the canonical contract, generated from
 * `web/src/index.css`. Two tests pin it from opposite sides:
 *
 *  - HERE: the CSS changing without regenerating the JSON fails.
 *  - `plant_community_mobile/test/core/theme/canopy_parity_test.dart`: the Dart
 *    palette drifting from the JSON fails.
 *
 * Neither can pass by coincidence — they compare different artefacts against
 * the same committed file.
 *
 * NOTE ON SCOPE: this asserts the committed JSON is a faithful re-extraction.
 * It does NOT verify the oklab maths — jsdom has no `color-mix`, so a test here
 * could never catch a wrong blend. That is covered by
 * `scripts/design/verify_canopy_tokens_in_browser.mjs`, which compares against
 * the pixels Chromium actually paints. Do not "improve" this file by trying to
 * resolve colours in jsdom; it will silently agree with anything.
 */
describe('Canopy token contract', () => {
  it('has a committed contract and a canonical stylesheet', () => {
    // Guard the loader: a parity test whose fixture is missing must fail, never
    // quietly pass having checked nothing.
    expect(existsSync(CSS_PATH), `missing canonical stylesheet ${CSS_PATH}`).toBe(true);
    expect(
      existsSync(JSON_PATH),
      `missing ${JSON_PATH} — run: node scripts/design/extract_canopy_tokens.mjs`
    ).toBe(true);
  });

  it('committed JSON matches a fresh extraction from index.css', () => {
    const committed = readFileSync(JSON_PATH, 'utf8');
    expect(
      serialize(extract()),
      'design/canopy-tokens.json is stale. Re-run: node scripts/design/extract_canopy_tokens.mjs'
    ).toBe(committed);
  });

  it('every semantic role resolves to a concrete colour in both modes', () => {
    const tokens = extract();
    for (const mode of ['dark', 'light'] as const) {
      const roles = tokens.modes[mode].colors;
      expect(Object.keys(roles).length).toBeGreaterThanOrEqual(22);
      for (const [role, value] of Object.entries(roles)) {
        // `#RRGGBB` or `#RRGGBBAA` — never an unresolved `color-mix(...)`.
        expect(value.hex, `${mode}/${role}`).toMatch(/^#[0-9A-F]{6}([0-9A-F]{2})?$/);
        expect(value.dart, `${mode}/${role}`).toMatch(/^0x[0-9A-F]{8}$/);
      }
    }
  });

  it('pins the defaults both platforms must share', () => {
    const tokens = extract();
    expect(tokens.defaults).toEqual({ mode: 'dark', density: 'cozy' });
    expect(tokens.density.cozy).toEqual({
      padCard: '16px',
      padScreen: '16px',
      gap: '12px',
    });
  });

  it('keeps headings roman — the italic display face was Flutter-only', () => {
    const { display } = extract();
    for (const name of ['display', 'h1', 'h2', 'h3']) {
      expect(display[name].fontStyle, name).toBe('normal');
    }
  });
});
