# Green Thumb Design System — Phase 1: Mobile Design System

**Date:** 2026-05-31
**Scope:** Flutter mobile app (`plant_community_mobile/`) design system only — no screen changes
**Source design:** Green Thumb Redesign (standalone).html (Claude Design export)
**Next phase:** Screen-by-screen application (separate spec)

## Context

The Green Thumb app has a full visual redesign (7 mobile screens + web landing page). This spec covers Phase 1 only: extracting the new design system into Flutter infrastructure. All existing screen/widget files remain untouched. Phase 2 (screen application) is a separate spec and plan.

The existing `AppTheme` already uses Material 3 with static light/dark getters and a `ThemeModeNotifier` Riverpod provider. This spec replaces the color, typography, and spacing values while preserving that overall structure.

## Approach

**M3 ColorScheme + ThemeExtensions.** Map the primary design tokens to Material 3 color roles so existing Material widgets (FilledButton, AppBar, Card, etc.) pick up the new palette automatically. Tokens without M3 equivalents go into a `GreenThumbExtension` ThemeExtension. Palette switching and density are managed by a new `PaletteNotifier` alongside the existing `ThemeModeNotifier`.

## 1. Color System

### M3 ColorScheme role mapping (Garden palette — all palettes follow same structure)

| M3 Role | Design token | Light | Dark |
|---|---|---|---|
| primary | moss | #2F6B3A | #A8CC6E |
| onPrimary | on-moss | #F4F1E4 | #14180F |
| secondary | sage | #7FA66B | #9BBE82 |
| onSecondary | bg | #F4F1E4 | #0E140F |
| tertiary | honey | #E5B84B | #E8C76B |
| onTertiary | bg | #F4F1E4 | #0E140F |
| error | bad | #B5451C | #B5451C |
| onError | on-clay | #FFF8EA | #FFF8EA |
| surface | bg | #F4F1E4 | #0E140F |
| onSurface | ink | #102015 | #EEF4E2 |
| surfaceContainerLow | bg-2 | #ECE7D2 | #161E18 |
| surfaceContainerHigh | bg-3 | #DFD9BD | #1F2A21 |
| outline | line | #D2CCAE | #2A3628 |
| outlineVariant | line-2 | #B8B391 | #3A4A37 |

### Palettes

Four palettes are supported. `app_palettes.dart` defines a `GreenThumbPalette` class holding all light and dark color values for each. The `AppTheme.build()` factory selects the right palette data.

| Palette | Character | Default? | Dark override? |
|---|---|---|---|
| Loam | Warm earth tones — potting soil + bloom | ★ | Yes (explicit dark values) |
| Garden | Fresh greens, soft cream | | Yes (explicit dark values) |
| Forest | Deep greens, dramatic — always dark | | No (single dark-by-nature set) |
| Heritage | Parchment + plate-illustration greens | | No (uses Garden dark values) |

Default palette: **Loam**. Default mode: **system** (existing `ThemeModeNotifier` behaviour unchanged).

#### Appendix: full hex values by palette

**Garden**

| Token | Light | Dark |
|---|---|---|
| bg | #F4F1E4 | #0E140F |
| bg-2 | #ECE7D2 | #161E18 |
| bg-3 | #DFD9BD | #1F2A21 |
| ink | #102015 | #EEF4E2 |
| ink-2 | #2E4233 | #C8D5B8 |
| ink-3 | #5C6E5A | #8A9A7E |
| line | #D2CCAE | #2A3628 |
| line-2 | #B8B391 | #3A4A37 |
| moss | #2F6B3A | #A8CC6E |
| on-moss | #F4F1E4 | #14180F |
| sage | #7FA66B | #9BBE82 |
| leaf | #A8CC6E | #BEDC8C |
| honey | #E5B84B | #E8C76B |
| clay | #D86B2C | #E58A52 |
| on-clay | #FFF8EA | #14180F |
| berry | #B8466A | #D286A2 |
| sky | #6FA0AA | #9CC0CA |
| ok | #3F5D3F | #3F5D3F |
| warn | #C4A570 | #C4A570 |

**Loam**

| Token | Light | Dark |
|---|---|---|
| bg | #F6F0E2 | #12100A |
| bg-2 | #ECE3CC | #1C1810 |
| bg-3 | #DDD0AE | #272218 |
| ink | #1F1A12 | #F2EBD8 |
| ink-2 | #4A3F2C | #D4C8A4 |
| ink-3 | #7C6E55 | #8A7E60 |
| line | #D4C5A0 | #2E2818 |
| line-2 | #BCA97E | #423A26 |
| moss | #4A7034 | #B8D680 |
| on-moss | #F6F0E2 | #12100A |
| sage | #97B86A | #A3C26C |
| leaf | #C2D680 | #CCE090 |
| honey | #E0B445 | #E8C76B |
| clay | #C9542A | #E58A52 |
| on-clay | #FFF8EA | #12100A |
| berry | #C45577 | #D286A2 |
| sky | #6FA0AA | #9CC0CA |

**Forest** (no light/dark split — single dark-by-nature set used for both modes)

| Token | Value |
|---|---|
| bg | #0F1A12 |
| bg-2 | #16241A |
| bg-3 | #1F3024 |
| ink | #E8F0D8 |
| ink-2 | #C2D2AC |
| ink-3 | #87987C |
| line | #2A3A2F |
| line-2 | #3D5142 |
| moss | #B8DC7C |
| on-moss | #0F1A12 |
| sage | #A8CC6E |
| leaf | #C8E198 |
| honey | #F0CC68 |
| clay | #F0935A |
| berry | #E090A8 |
| sky | #94BFC8 |

**Heritage** (light values only — uses Garden dark values when in dark mode)

| Token | Light |
|---|---|
| bg | #F0EBDB |
| bg-2 | #E4DBC2 |
| bg-3 | #D3C9AC |
| ink | #1A1F10 |
| ink-2 | #3A4128 |
| ink-3 | #756E50 |
| line | #CFC4A2 |
| line-2 | #B8AC85 |
| moss | #3D5A22 |
| on-moss | #F0EBDB |
| sage | #768B4E |
| leaf | #A4B86E |
| honey | #C99B3A |
| clay | #B0481E |
| berry | (inherits Garden) |

### GreenThumbExtension tokens (no M3 equivalent)

These are accessed via `Theme.of(context).extension<GreenThumbExtension>()!`.

| Field | Type | Purpose |
|---|---|---|
| clay | Color | CTA accent (warm orange) |
| onClay | Color | Text on clay backgrounds |
| berry | Color | Alert / notification badge |
| sky | Color | Info / water care indicators |
| leaf | Color | Confidence badge / highlight |
| ink2 | Color | Secondary text |
| ink3 | Color | Caption / muted text |
| statusOk | Color | Plant health / success |
| statusWarn | Color | Needs attention |
| shadow1 | List\<BoxShadow\> | Subtle (cards at rest) |
| shadow2 | List\<BoxShadow\> | Elevated (active cards) |
| shadow3 | List\<BoxShadow\> | Modal / sheet |
| padCard | double | Card internal padding |
| padScreen | double | Screen edge padding |
| gapY | double | Vertical gap between list items |
| showGrain | bool | Paper grain overlay enabled — rendered by a root `GrainOverlay` widget wrapping the app scaffold (see below) |

## 2. Typography

### Font delivery: bundled local assets

Fonts are downloaded and committed to `assets/fonts/`. This guarantees rendering on first launch with no network dependency — critical for outdoor use.

**Licenses:** Bricolage Grotesque — SIL Open Font License 1.1. Geist and Geist Mono — MIT (Vercel). All three are free to bundle in commercial apps.

### Font files required

```text
assets/fonts/
  BricolageGrotesque-SemiBoldItalic.ttf   — display + headings
  BricolageGrotesque-SemiBold.ttf         — display + headings (non-italic fallback)
  Geist-Regular.ttf                        — body
  Geist-Medium.ttf                         — label, button
  Geist-SemiBold.ttf                       — eyebrow, strong labels
  GeistMono-Regular.ttf                    — mono / scientific names
```

### Type scale

| Style | Font | Weight | Style | Notes |
|---|---|---|---|---|
| display | Bricolage Grotesque | 600 | italic | line-height 1.02, tracking −0.02em |
| h1 | Bricolage Grotesque | 600 | italic | |
| h2 | Bricolage Grotesque | 600 | italic | |
| h3 | Bricolage Grotesque | 600 | italic | |
| eyebrow | Geist | 600 | normal uppercase | 11px, tracking +0.06em, ink3 color |
| body | Geist | 400 | normal | |
| bodySm | Geist | 400 | normal | |
| label | Geist | 500 | normal | |
| button | Geist | 600 | normal | |
| mono | Geist Mono | 400 | normal | tabular-nums |

`AppTypography` is rewritten to use these families. All `TextStyle` constants become non-const (font family is a runtime string via the font asset name).

## 3. Shape Tokens

Defined as constants in `AppSpacing` (existing file, values updated).

| Token | Value | Usage |
|---|---|---|
| rXs | 6 | Tags, chips, badges |
| rSm | 10 | Input fields, small buttons |
| rMd | 16 | Cards, sheets, dialogs |
| rLg | 22 | Large cards, bottom sheets |
| rXl | 28 | Hero cards, modals |
| rPill | 999 | FABs, pill buttons, toggles |

## 4. Density System

Three density variants, default **Cozy**. Stored in `GreenThumbExtension` and persisted by `PaletteNotifier`.

| Variant | padCard | padScreen | gapY | Default? |
|---|---|---|---|---|
| Comfortable | 18 | 18 | 14 | |
| Cozy | 16 | 16 | 12 | ★ |
| Compact | 12 | 14 | 10 | |

## 5. Architecture

### New files

```text
lib/core/theme/green_thumb_extension.dart
lib/core/theme/app_palettes.dart
lib/config/palette_notifier.dart
lib/config/palette_notifier.g.dart          (build_runner generated)
assets/fonts/<font files>
```

### Modified files

| File | Change |
|---|---|
| `lib/core/theme/app_theme.dart` | Replace static `lightTheme`/`darkTheme` getters with `AppTheme.build(AppPaletteChoice, Brightness, AppDensity)` factory |
| `lib/core/theme/app_typography.dart` | Replace CSS font stacks with Bricolage Grotesque + Geist; add eyebrow style; italic display |
| `lib/core/theme/app_colors.dart` | Delete — absorbed into `app_palettes.dart` |
| `lib/core/constants/app_spacing.dart` | Update radius constants to new token values |
| `pubspec.yaml` | Add font asset declarations |
| `lib/main.dart` | Wire `MaterialApp` to watch both `themeModeNotifier` and `paletteNotifier` |

### Untouched

- `lib/config/theme_provider.dart` — `ThemeModeNotifier` stays exactly as-is
- All screen and widget files — zero changes in Phase 1

### GrainOverlay widget

`GrainOverlay` is a new widget in `lib/core/theme/grain_overlay.dart`. It wraps its child in a `Stack`, placing a noise texture image (`assets/images/grain.png`) on top at 0.35 opacity with `BlendMode.multiply`. It reads `showGrain` from `GreenThumbExtension` and renders a `SizedBox.shrink()` when false.

Usage: wrap the root `Scaffold` body (or the `MaterialApp` builder) once — not per-screen.

```dart
class GrainOverlay extends StatelessWidget {
  const GrainOverlay({required this.child, super.key});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;
    if (!ext.showGrain) return child;
    return Stack(children: [
      child,
      Positioned.fill(
        child: IgnorePointer(
          child: Image.asset(
            'assets/images/grain.png',
            fit: BoxFit.cover,
            color: Colors.black.withValues(alpha: 0.35),
            colorBlendMode: BlendMode.multiply,
          ),
        ),
      ),
    ]);
  }
}
```

A 256×256 tileable Perlin noise PNG at `assets/images/grain.png` must be added (any public-domain noise texture).

### ThemePreviewScreen (debug only)

`lib/core/theme/theme_preview_screen.dart` — a debug-only screen (guarded by `kDebugMode`) that renders a scrollable grid of all 24 theme combinations (4 palettes × 2 modes × 3 densities). Each cell shows the palette name, mode, density, and a small swatch of primary/surface/ink colors. Accessible from the Settings screen in debug builds only.

Added to `lib/core/theme/` alongside other theme files. No production code paths reference it outside the debug guard.

### PaletteNotifier

New `@riverpod` class alongside `ThemeModeNotifier`. Manages two pieces of state: `AppPaletteChoice` (enum: loam, garden, forest, heritage) and `AppDensity` (enum: comfortable, cozy, compact). Both persisted to `FlutterSecureStorage` under separate keys. Defaults: loam + cozy.

### PaletteSettings (state class)

```dart
class PaletteSettings {
  final AppPaletteChoice palette;   // enum: loam, garden, forest, heritage
  final AppDensity density;         // enum: comfortable, cozy, compact
}
```

`PaletteNotifier` state is a `PaletteSettings`. Both fields persisted to `FlutterSecureStorage`.

### AppTheme.build()

```dart
static ThemeData build(AppPaletteChoice palette, Brightness brightness, AppDensity density)
```

Resolves palette color data internally from `app_palettes.dart`, then returns a complete `ThemeData` with:

- `ColorScheme` built from palette × brightness
- `GreenThumbExtension` attached via `extensions` (includes density vars)
- All widget themes updated: colors inherit automatically from `ColorScheme`; only shapes (using `AppSpacing` radius tokens) and paddings need explicit values in widget theme overrides
- `TextTheme` built from `AppTypography` with new font families

### MaterialApp wiring

```dart
// lib/main.dart
final themeMode = ref.watch(themeModeNotifierProvider);
final settings = ref.watch(paletteNotifierProvider);

MaterialApp(
  themeMode: themeMode,
  theme: AppTheme.build(settings.palette, Brightness.light, settings.density),
  darkTheme: AppTheme.build(settings.palette, Brightness.dark, settings.density),
)
```

## 6. Completion Criteria

Phase 1 is complete when:

1. `flutter analyze` passes with zero errors
2. `AppTheme.build()` produces correct `ThemeData` for all 4 × 2 × 3 = 24 combinations (covered by widget tests)
3. All four palettes render correctly in light and dark mode on the simulator — verified via `ThemePreviewScreen` against the Claude Design reference
4. `PaletteNotifier` persists and restores palette + density across app restarts
5. `GrainOverlay` composites correctly at 0.35 opacity; toggling `showGrain` shows/hides texture without affecting touch targets
6. No screen files were modified (other than the debug Settings entry point for `ThemePreviewScreen`)
