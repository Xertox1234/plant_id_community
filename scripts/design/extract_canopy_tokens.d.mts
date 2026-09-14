/**
 * Types for the Canopy token extractor.
 *
 * The extractor itself is plain Node ESM (it is run by `node`, by the Flutter
 * parity workflow and by a Vitest test), so it is not TypeScript — but the web
 * test importing it is, and `allowJs` is off. This declaration is the contract
 * between them; keep it in step with what `extract()` actually returns.
 */

/** A resolved colour: the authored expression plus its concrete forms. */
export interface CanopyColorToken {
  /** The CSS as authored, e.g. `color-mix(in oklab, var(--canopy-sage) 85%, …)`. */
  css: string;
  /** `#RRGGBB`, or `#RRGGBBAA` when the token carries alpha. */
  hex: string;
  /** `rgb(r, g, b)` / `rgba(r, g, b, a)` — the browser-comparable form. */
  rgba: string;
  /** `0xAARRGGBB` — a Flutter `Color()` literal. */
  dart: string;
}

export interface CanopyMode {
  colors: Record<string, CanopyColorToken>;
  gradients: Record<string, string>;
  tiles: Record<string, string>;
  shadows: Record<string, string>;
}

export interface CanopyTextRung {
  size: string;
  lineHeight: string;
}

export interface CanopyDisplayRung {
  fontFamily: string;
  fontWeight: number;
  fontSize: string;
  lineHeight: number;
  letterSpacing: string;
  fontStyle: string;
}

export interface CanopyDensity {
  padCard: string;
  padScreen: string;
  gap: string;
}

export interface CanopyTokens {
  $schema: string;
  $generator: string;
  $source: string;
  $doc: string;
  ramp: Record<string, string>;
  modes: Record<'dark' | 'light', CanopyMode>;
  defaults: { mode: string; density: string };
  density: Record<string, CanopyDensity>;
  radius: Record<string, string>;
  text: Record<string, CanopyTextRung>;
  display: Record<string, CanopyDisplayRung>;
  label: Record<string, string>;
  fonts: Record<string, string>;
}

/** Parse `web/src/index.css` and resolve every semantic token. */
export function extract(): CanopyTokens;

/** Canonical JSON serialisation — byte-comparable with the committed file. */
export function serialize(tokens: CanopyTokens): string;

export const REPO_ROOT: string;
export const CSS_PATH: string;
export const JSON_PATH: string;
