/// Canopy spacing, radius and icon scales — ONE authoritative set.
///
/// This file previously carried two conflicting radius scales: a legacy
/// `radiusSM/MD/LG/XL` (4/8/12/16) alongside the design-system `rXs…rPill`
/// (6/10/16/22/28/999). `radiusMD` (8) and `rMd` (16) sat two lines apart and
/// meant different things, so a card and the tile inside it could both claim to
/// use "the medium radius" and disagree by 8px. The legacy rungs — and the
/// unused `elevation*` and derived-padding constants — are gone; `rXs…rPill`
/// is the only radius scale, pinned to the canonical `--radius-*` tokens by
/// `test/core/theme/canopy_parity_test.dart`.
///
/// Density-dependent spacing (card padding, screen padding, vertical gap) does
/// NOT live here — it varies by density, so it comes from
/// `GreenThumbExtension` (`ext.padCard` / `ext.padScreen` / `ext.gapY`).
class AppSpacing {
  AppSpacing._();

  // ── spacing scale (4px base) ──────────────────────────────────────────────
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 16.0;
  static const double lg = 24.0;
  static const double xl = 32.0;
  static const double xl2 = 48.0;
  static const double xl3 = 64.0;

  // ── radius scale (canonical --radius-*) ───────────────────────────────────
  /// Chips, badges, small inline controls.
  static const double rXs = 6.0;

  /// Inputs' inner elements, code blocks, small tiles.
  static const double rSm = 10.0;

  /// The default card radius.
  static const double rMd = 16.0;

  /// Hero cards, sheets, dialogs.
  static const double rLg = 22.0;

  /// The largest panels.
  static const double rXl = 28.0;

  /// Fully rounded — buttons and pills.
  static const double rPill = 999.0;

  /// Accent icon tiles. Deliberately off the main scale: these mirror the web's
  /// `TILE_RADIUS` (`rounded-[11px]` / `rounded-[14px]`), which are tuned to
  /// the tile box rather than the card scale. Keep the pair in step with
  /// `web/src/components/ui/dimensions.ts`.
  static const double rTileSm = 11.0;
  static const double rTileMd = 14.0;

  // ── icon sizes ────────────────────────────────────────────────────────────
  /// Inline with body text.
  static const double iconSM = 16.0;

  /// The default UI icon size — nav bar, buttons, list rows.
  static const double iconMD = 20.0;

  /// Accent-tile and card-header icons.
  static const double iconLG = 24.0;

  /// Empty-state and hero illustrations.
  static const double iconXL = 48.0;
}
