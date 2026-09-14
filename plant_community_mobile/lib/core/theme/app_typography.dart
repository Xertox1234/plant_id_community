import 'package:flutter/material.dart';

/// Canopy type scale — the Flutter mirror of the canonical web scale.
///
/// Sizes, line-heights, letter-spacing and weights are pinned to
/// `design/canopy-tokens.json` by `test/core/theme/canopy_parity_test.dart`;
/// that contract is generated from `web/src/index.css`. Change the CSS and
/// re-run the generator — do not hand-tune a number here.
///
/// Three faces, three jobs (spec §5), all bundled in `pubspec.yaml`:
///   - **Bricolage Grotesque 600** — display/headings
///   - **Geist 400–600** — body and UI
///   - **Geist Mono** — data, eyebrows, tabular numbers
///
/// Two deliberate corrections to what Flutter shipped before:
///
/// 1. **Headings are roman, not italic.** The canonical `.gt-*` rules carry no
///    `font-style`, so the italic display face was a Flutter-only invention.
/// 2. **The body scale was a whole rung too large** (body 16/1.625 against the
///    web's 14/1.5). Line-heights were loose in the same way. Both now track
///    the web rungs exactly.
class AppTypography {
  AppTypography._();

  static const String _display = 'BricolageGrotesque';
  static const String _body = 'Geist';
  static const String _mono = 'GeistMono';

  /// Display rungs. `letterSpacing` is the canonical `-0.02em` resolved against
  /// each size, because Flutter measures letter-spacing in logical pixels.
  static const TextStyle display = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontSize: 32.0,
    height: 1.02,
    letterSpacing: 32.0 * -0.02,
  );

  static const TextStyle h1 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontSize: 28.0,
    height: 1.1,
    letterSpacing: 28.0 * -0.02,
  );

  static const TextStyle h2 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontSize: 22.0,
    height: 1.15,
    letterSpacing: 22.0 * -0.02,
  );

  static const TextStyle h3 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontSize: 18.0,
    height: 1.2,
    letterSpacing: 18.0 * -0.02,
  );

  // ── body rungs (`--text-*`) ───────────────────────────────────────────────
  // The web also defines a `hero` rung at 38px, but it is a `md:` breakpoint
  // override (`gt-h1 md:text-hero`) — desktop only. On a phone the hero IS
  // [h1], so no `hero` rung is defined here on purpose.

  /// 11px — badge counts, the smallest legible rung.
  static const TextStyle micro = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 11.0,
    height: 1.35,
  );

  /// 12.5px — timestamps, stat lines, secondary metadata.
  static const TextStyle meta = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 12.5,
    height: 1.4,
  );

  /// 13px — dense body copy (card descriptions, list subtitles).
  static const TextStyle bodySm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 13.0,
    height: 1.45,
  );

  /// 14px — the default body rung.
  static const TextStyle body = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    height: 1.5,
  );

  /// 15px — long-form reading (post bodies, article text).
  static const TextStyle bodyLg = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 15.0,
    height: 1.5,
  );

  /// 17px — hero standfirst / lead paragraph.
  static const TextStyle lead = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 17.0,
    height: 1.4,
  );

  // ── UI rungs ──────────────────────────────────────────────────────────────

  /// The canonical `.gt-label`: mono, uppercase, tracked — the app's ONE
  /// eyebrow/data-label treatment. Callers must apply `ink3` and
  /// `TextTransform`-style uppercasing at the call site (Flutter has no
  /// `text-transform`), and should not invent a second eyebrow style.
  static const TextStyle label = TextStyle(
    fontFamily: _mono,
    fontWeight: FontWeight.w400,
    fontSize: 11.0,
    height: 1.35,
    letterSpacing: 11.0 * 0.08,
  );

  /// Form field labels and other medium-weight UI text.
  static const TextStyle uiLabel = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w500,
    fontSize: 14.0,
    height: 1.4,
  );

  /// Button text. The web button sizes are Tailwind's `text-sm` / `text-base` /
  /// `text-lg`, i.e. 14 / 16 / 18 — not the `--text-*` rungs.
  static const TextStyle buttonSm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 14.0,
    height: 1.4,
  );

  static const TextStyle button = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 16.0,
    height: 1.4,
  );

  static const TextStyle buttonLg = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 18.0,
    height: 1.4,
  );

  /// Numbers and other tabular data — `font-mono` with `tabular-nums`, per
  /// spec §5. Use for counts, measurements and timestamps in a column.
  static const TextStyle mono = TextStyle(
    fontFamily: _mono,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    height: 1.5,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}
