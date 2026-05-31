# Green Thumb Design System — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Flutter app's existing color/type/spacing primitives with the Green Thumb design system (4 palettes × dark/light × 3 density variants), wiring palette and density selection through a new Riverpod notifier — without touching any screen files.

**Architecture:** New `GreenThumbExtension` (ThemeExtension) carries the tokens that have no M3 ColorScheme role. `AppTheme.build(palette, brightness, density)` replaces the static `lightTheme`/`darkTheme` getters and resolves palette data from `app_palettes.dart`. `PaletteNotifier` (Riverpod) persists palette + density alongside the existing `ThemeModeNotifier`.

**Tech Stack:** Flutter 3.x, Material 3, Riverpod 3.x (`riverpod_annotation`), `flutter_secure_storage`, custom bundled fonts (Bricolage Grotesque, Geist, Geist Mono).

**Note on app_colors.dart:** Several screen files import `AppColors` directly. Deleting it now would break compilation. Keep `app_colors.dart` as-is through Phase 1; it will be removed in Phase 2 when screens are migrated to use `Theme.of(context)` tokens.

**Spec:** `docs/superpowers/specs/2026-05-31-green-thumb-design-system-design.md`

---

## File Map

| Status | File | Responsibility |
|---|---|---|
| Create | `plant_community_mobile/assets/fonts/*.ttf` | Bundled font files |
| Create | `plant_community_mobile/assets/images/grain.png` | 256×256 noise texture for grain overlay |
| Create | `lib/core/theme/app_palettes.dart` | `GreenThumbPalette` data class + 4 palette constants |
| Create | `lib/core/theme/green_thumb_extension.dart` | `GreenThumbExtension` ThemeExtension |
| Create | `lib/config/palette_notifier.dart` | `AppPaletteChoice`, `AppDensity`, `PaletteSettings`, `PaletteNotifier` |
| Create | `lib/config/palette_notifier.g.dart` | build_runner generated |
| Create | `lib/core/theme/grain_overlay.dart` | `GrainOverlay` widget |
| Create | `lib/core/theme/theme_preview_screen.dart` | Debug-only 24-combination theme grid |
| Create | `test/core/theme/app_palettes_test.dart` | Palette data correctness tests |
| Create | `test/core/theme/green_thumb_extension_test.dart` | Extension copyWith/lerp tests |
| Create | `test/core/theme/app_typography_test.dart` | Font family assertion tests |
| Create | `test/core/theme/palette_notifier_test.dart` | State + persistence tests |
| Create | `test/core/theme/app_theme_test.dart` | ThemeData correctness for 24 combinations |
| Create | `test/core/theme/grain_overlay_test.dart` | Widget renders/hides grain correctly |
| Modify | `lib/core/constants/app_spacing.dart` | Add new radius/density token constants |
| Modify | `lib/core/theme/app_typography.dart` | Replace CSS font stacks with bundled fonts |
| Modify | `lib/core/theme/app_theme.dart` | Add `build()` factory, remove static getters |
| Modify | `lib/main.dart` | Watch `paletteProvider`, pass to `AppTheme.build()` |
| Modify | `lib/core/routing/app_router.dart` | Add debug `/theme-preview` route |
| Modify | `pubspec.yaml` | Font + image asset declarations |
| Keep | `lib/core/theme/app_colors.dart` | Unchanged — removed in Phase 2 |

All commands below assume `cd plant_community_mobile` first.

---

### Task 1: Font assets and pubspec declarations

**Files:**

- Create: `assets/fonts/BricolageGrotesque-SemiBoldItalic.ttf`
- Create: `assets/fonts/BricolageGrotesque-SemiBold.ttf`
- Create: `assets/fonts/Geist-Regular.ttf`
- Create: `assets/fonts/Geist-Medium.ttf`
- Create: `assets/fonts/Geist-SemiBold.ttf`
- Create: `assets/fonts/GeistMono-Regular.ttf`
- Create: `assets/images/grain.png`
- Modify: `pubspec.yaml`

- [ ] **Step 1: Download font files**

```bash
mkdir -p assets/fonts assets/images
```

Download Bricolage Grotesque from Google Fonts (<https://fonts.google.com/specimen/Bricolage+Grotesque>):

- Download the zip, extract `BricolageGrotesque-SemiBold.ttf` and `BricolageGrotesque-SemiBoldItalic.ttf` (or the variable font — use a subset with SemiBold and Italic axes if available)

Download Geist from Vercel's GitHub (<https://github.com/vercel/geist-font/releases>):

- From the release zip, extract from `Geist/ttf/`: `Geist-Regular.ttf`, `Geist-Medium.ttf`, `Geist-SemiBold.ttf`
- From `GeistMono/ttf/`: `GeistMono-Regular.ttf`

Place all six `.ttf` files in `assets/fonts/`.

- [ ] **Step 2: Add a grain texture**

Download any 256×256 tileable greyscale Perlin/Simplex noise PNG (e.g. search "grain texture png free" on Unsplash or similar, or generate one at <https://grainy-gradients.vercel.app/>). Save as `assets/images/grain.png`. The file should be under 50 KB.

- [ ] **Step 3: Declare assets in pubspec.yaml**

In `pubspec.yaml`, find the `flutter:` section and add assets + fonts declarations:

```yaml
flutter:
  uses-material-design: true

  assets:
    - assets/images/grain.png

  fonts:
    - family: BricolageGrotesque
      fonts:
        - asset: assets/fonts/BricolageGrotesque-SemiBold.ttf
          weight: 600
        - asset: assets/fonts/BricolageGrotesque-SemiBoldItalic.ttf
          weight: 600
          style: italic
    - family: Geist
      fonts:
        - asset: assets/fonts/Geist-Regular.ttf
          weight: 400
        - asset: assets/fonts/Geist-Medium.ttf
          weight: 500
        - asset: assets/fonts/Geist-SemiBold.ttf
          weight: 600
    - family: GeistMono
      fonts:
        - asset: assets/fonts/GeistMono-Regular.ttf
          weight: 400
```

- [ ] **Step 4: Verify pubspec parses**

```bash
flutter pub get
```

Expected: no errors. If `assets/images/grain.png` doesn't exist yet, temporarily comment out that line until the file is added.

- [ ] **Step 5: Commit**

```bash
git add assets/ pubspec.yaml
git commit -m "chore: add design system font assets and grain texture"
```

---

### Task 2: AppSpacing — add new radius and density token constants

**Files:**

- Modify: `lib/core/constants/app_spacing.dart`
- Create: `test/core/theme/app_spacing_test.dart`

- [ ] **Step 1: Write the failing tests**

Create `test/core/theme/app_spacing_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/constants/app_spacing.dart';

void main() {
  group('AppSpacing radius tokens', () {
    test('rXs is 6', () => expect(AppSpacing.rXs, 6.0));
    test('rSm is 10', () => expect(AppSpacing.rSm, 10.0));
    test('rMd is 16', () => expect(AppSpacing.rMd, 16.0));
    test('rLg is 22', () => expect(AppSpacing.rLg, 22.0));
    test('rXl is 28', () => expect(AppSpacing.rXl, 28.0));
    test('rPill is 999', () => expect(AppSpacing.rPill, 999.0));
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/app_spacing_test.dart
```

Expected: FAIL — `AppSpacing.rXs` not defined.

- [ ] **Step 3: Add constants to AppSpacing**

In `lib/core/constants/app_spacing.dart`, add a new section after the existing `BORDER RADIUS` section (keep existing radius constants — screens use them):

```dart
  // ============================================
  // DESIGN SYSTEM RADIUS TOKENS (Green Thumb)
  // ============================================
  static const double rXs = 6.0;
  static const double rSm = 10.0;
  static const double rMd = 16.0;
  static const double rLg = 22.0;
  static const double rXl = 28.0;
  static const double rPill = 999.0;
```

- [ ] **Step 4: Run tests**

```bash
flutter test test/core/theme/app_spacing_test.dart
```

Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/core/constants/app_spacing.dart test/core/theme/app_spacing_test.dart
git commit -m "feat: add Green Thumb radius tokens to AppSpacing"
```

---

### Task 3: app_palettes.dart — GreenThumbPalette data class and palette constants

**Files:**

- Create: `lib/core/theme/app_palettes.dart`
- Create: `test/core/theme/app_palettes_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/app_palettes_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';

void main() {
  group('GreenThumbPalette', () {
    test('Garden light primary (moss) is correct', () {
      expect(AppPalettes.garden.light.moss, const Color(0xFF2F6B3A));
    });
    test('Garden dark primary (moss) is correct', () {
      expect(AppPalettes.garden.dark.moss, const Color(0xFFA8CC6E));
    });
    test('Loam light bg is correct', () {
      expect(AppPalettes.loam.light.bg, const Color(0xFFF6F0E2));
    });
    test('Loam dark bg is correct', () {
      expect(AppPalettes.loam.dark.bg, const Color(0xFF12100A));
    });
    test('Forest has same light and dark (inherently dark palette)', () {
      expect(AppPalettes.forest.light.bg, AppPalettes.forest.dark.bg);
    });
    test('Heritage dark falls back to Garden dark', () {
      expect(AppPalettes.heritage.dark.moss, AppPalettes.garden.dark.moss);
    });
  });

  group('AppPalettes.forChoice', () {
    test('returns correct palette for each choice', () {
      expect(AppPalettes.forChoice(AppPaletteChoice.garden), AppPalettes.garden);
      expect(AppPalettes.forChoice(AppPaletteChoice.loam), AppPalettes.loam);
      expect(AppPalettes.forChoice(AppPaletteChoice.forest), AppPalettes.forest);
      expect(AppPalettes.forChoice(AppPaletteChoice.heritage), AppPalettes.heritage);
    });
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/app_palettes_test.dart
```

Expected: FAIL — `AppPalettes` not defined.

- [ ] **Step 3: Create app_palettes.dart**

Create `lib/core/theme/app_palettes.dart`:

```dart
import 'package:flutter/material.dart';

class GreenThumbColors {
  const GreenThumbColors({
    required this.bg,
    required this.bg2,
    required this.bg3,
    required this.ink,
    required this.ink2,
    required this.ink3,
    required this.line,
    required this.line2,
    required this.moss,
    required this.onMoss,
    required this.sage,
    required this.leaf,
    required this.honey,
    required this.clay,
    required this.onClay,
    required this.berry,
    required this.sky,
    required this.ok,
    required this.warn,
    required this.bad,
  });

  final Color bg, bg2, bg3;
  final Color ink, ink2, ink3;
  final Color line, line2;
  final Color moss, onMoss;
  final Color sage, leaf, honey;
  final Color clay, onClay;
  final Color berry, sky;
  final Color ok, warn, bad;
}

class GreenThumbPalette {
  const GreenThumbPalette({required this.light, required this.dark});
  final GreenThumbColors light;
  final GreenThumbColors dark;
}

enum AppPaletteChoice { loam, garden, forest, heritage }

abstract final class AppPalettes {
  // Extracted so Heritage can reference it without a member-access const expression.
  static const _gardenDark = GreenThumbColors(
    bg: Color(0xFF0E140F), bg2: Color(0xFF161E18), bg3: Color(0xFF1F2A21),
    ink: Color(0xFFEEF4E2), ink2: Color(0xFFC8D5B8), ink3: Color(0xFF8A9A7E),
    line: Color(0xFF2A3628), line2: Color(0xFF3A4A37),
    moss: Color(0xFFA8CC6E), onMoss: Color(0xFF14180F),
    sage: Color(0xFF9BBE82), leaf: Color(0xFFBEDC8C),
    honey: Color(0xFFE8C76B),
    clay: Color(0xFFE58A52), onClay: Color(0xFF14180F),
    berry: Color(0xFFD286A2), sky: Color(0xFF9CC0CA),
    ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
  );

  static const GreenThumbPalette garden = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF4F1E4), bg2: Color(0xFFECE7D2), bg3: Color(0xFFDFD9BD),
      ink: Color(0xFF102015), ink2: Color(0xFF2E4233), ink3: Color(0xFF5C6E5A),
      line: Color(0xFFD2CCAE), line2: Color(0xFFB8B391),
      moss: Color(0xFF2F6B3A), onMoss: Color(0xFFF4F1E4),
      sage: Color(0xFF7FA66B), leaf: Color(0xFFA8CC6E),
      honey: Color(0xFFE5B84B),
      clay: Color(0xFFD86B2C), onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFB8466A), sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
    ),
    dark: _gardenDark,
  );

  static const GreenThumbPalette loam = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF6F0E2), bg2: Color(0xFFECE3CC), bg3: Color(0xFFDDD0AE),
      ink: Color(0xFF1F1A12), ink2: Color(0xFF4A3F2C), ink3: Color(0xFF7C6E55),
      line: Color(0xFFD4C5A0), line2: Color(0xFFBCA97E),
      moss: Color(0xFF4A7034), onMoss: Color(0xFFF6F0E2),
      sage: Color(0xFF97B86A), leaf: Color(0xFFC2D680),
      honey: Color(0xFFE0B445),
      clay: Color(0xFFC9542A), onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFC45577), sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
    ),
    dark: GreenThumbColors(
      bg: Color(0xFF12100A), bg2: Color(0xFF1C1810), bg3: Color(0xFF272218),
      ink: Color(0xFFF2EBD8), ink2: Color(0xFFD4C8A4), ink3: Color(0xFF8A7E60),
      line: Color(0xFF2E2818), line2: Color(0xFF423A26),
      moss: Color(0xFFB8D680), onMoss: Color(0xFF12100A),
      sage: Color(0xFFA3C26C), leaf: Color(0xFFCCE090),
      honey: Color(0xFFE8C76B),
      clay: Color(0xFFE58A52), onClay: Color(0xFF12100A),
      berry: Color(0xFFD286A2), sky: Color(0xFF9CC0CA),
      ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
    ),
  );

  // Forest is inherently dark — light and dark are the same set.
  static const _forestColors = GreenThumbColors(
    bg: Color(0xFF0F1A12), bg2: Color(0xFF16241A), bg3: Color(0xFF1F3024),
    ink: Color(0xFFE8F0D8), ink2: Color(0xFFC2D2AC), ink3: Color(0xFF87987C),
    line: Color(0xFF2A3A2F), line2: Color(0xFF3D5142),
    moss: Color(0xFFB8DC7C), onMoss: Color(0xFF0F1A12),
    sage: Color(0xFFA8CC6E), leaf: Color(0xFFC8E198),
    honey: Color(0xFFF0CC68),
    clay: Color(0xFFF0935A), onClay: Color(0xFF0F1A12),
    berry: Color(0xFFE090A8), sky: Color(0xFF94BFC8),
    ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
  );

  static const GreenThumbPalette forest = GreenThumbPalette(
    light: _forestColors,
    dark: _forestColors,
  );

  // Heritage has no dark override; dark falls back to Garden dark.
  static const GreenThumbPalette heritage = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF0EBDB), bg2: Color(0xFFE4DBC2), bg3: Color(0xFFD3C9AC),
      ink: Color(0xFF1A1F10), ink2: Color(0xFF3A4128), ink3: Color(0xFF756E50),
      line: Color(0xFFCFC4A2), line2: Color(0xFFB8AC85),
      moss: Color(0xFF3D5A22), onMoss: Color(0xFFF0EBDB),
      sage: Color(0xFF768B4E), leaf: Color(0xFFA4B86E),
      honey: Color(0xFFC99B3A),
      clay: Color(0xFFB0481E), onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFB8466A), sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F), warn: Color(0xFFC4A570), bad: Color(0xFFB5451C),
    ),
    dark: garden.dark, // inherits Garden dark — no Heritage-specific dark values in design
  );

  static GreenThumbPalette forChoice(AppPaletteChoice choice) => switch (choice) {
    AppPaletteChoice.garden => garden,
    AppPaletteChoice.loam => loam,
    AppPaletteChoice.forest => forest,
    AppPaletteChoice.heritage => heritage,
  };
}
```

- [ ] **Step 4: Run tests**

```bash
flutter test test/core/theme/app_palettes_test.dart
```

Expected: all 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/core/theme/app_palettes.dart test/core/theme/app_palettes_test.dart
git commit -m "feat: add GreenThumbPalette data class and 4 palette constants"
```

---

### Task 4: green_thumb_extension.dart — ThemeExtension

**Files:**

- Create: `lib/core/theme/green_thumb_extension.dart`
- Create: `test/core/theme/green_thumb_extension_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/green_thumb_extension_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';

void main() {
  final ext = GreenThumbExtension.fromColors(
    colors: AppPalettes.loam.light,
    density: AppDensity.cozy,
    brightness: Brightness.light,
  );

  group('GreenThumbExtension.fromColors', () {
    test('clay comes from palette', () {
      expect(ext.clay, AppPalettes.loam.light.clay);
    });
    test('padCard is cozy value 16', () {
      expect(ext.padCard, 16.0);
    });
    test('padScreen is cozy value 16', () {
      expect(ext.padScreen, 16.0);
    });
    test('gapY is cozy value 12', () {
      expect(ext.gapY, 12.0);
    });
    test('showGrain defaults true', () {
      expect(ext.showGrain, isTrue);
    });
  });

  group('copyWith', () {
    test('overrides specified fields', () {
      final copy = ext.copyWith(showGrain: false, padCard: 18.0);
      expect(copy.showGrain, isFalse);
      expect(copy.padCard, 18.0);
      expect(copy.clay, ext.clay); // unchanged
    });
  });

  group('density padding values', () {
    test('comfortable: padCard=18, padScreen=18, gapY=14', () {
      final e = GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.comfortable,
        brightness: Brightness.light,
      );
      expect(e.padCard, 18.0);
      expect(e.padScreen, 18.0);
      expect(e.gapY, 14.0);
    });
    test('compact: padCard=12, padScreen=14, gapY=10', () {
      final e = GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.compact,
        brightness: Brightness.light,
      );
      expect(e.padCard, 12.0);
      expect(e.padScreen, 14.0);
      expect(e.gapY, 10.0);
    });
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/green_thumb_extension_test.dart
```

Expected: FAIL — `GreenThumbExtension` not defined.

- [ ] **Step 3: Create green_thumb_extension.dart**

Create `lib/core/theme/green_thumb_extension.dart`:

```dart
import 'dart:ui';
import 'package:flutter/material.dart';
import 'app_palettes.dart';

enum AppDensity { comfortable, cozy, compact }

class GreenThumbExtension extends ThemeExtension<GreenThumbExtension> {
  const GreenThumbExtension({
    required this.clay,
    required this.onClay,
    required this.berry,
    required this.sky,
    required this.leaf,
    required this.ink2,
    required this.ink3,
    required this.statusOk,
    required this.statusWarn,
    required this.shadow1,
    required this.shadow2,
    required this.shadow3,
    required this.padCard,
    required this.padScreen,
    required this.gapY,
    required this.showGrain,
  });

  final Color clay, onClay, berry, sky, leaf;
  final Color ink2, ink3;
  final Color statusOk, statusWarn;
  final List<BoxShadow> shadow1, shadow2, shadow3;
  final double padCard, padScreen, gapY;
  final bool showGrain;

  factory GreenThumbExtension.fromColors({
    required GreenThumbColors colors,
    required AppDensity density,
    required Brightness brightness,
  }) {
    final (padCard, padScreen, gapY) = switch (density) {
      AppDensity.comfortable => (18.0, 18.0, 14.0),
      AppDensity.cozy        => (16.0, 16.0, 12.0),
      AppDensity.compact     => (12.0, 14.0, 10.0),
    };

    final shadowColor = brightness == Brightness.light
        ? const Color(0xFF1B2218)
        : Colors.black;

    return GreenThumbExtension(
      clay: colors.clay,
      onClay: colors.onClay,
      berry: colors.berry,
      sky: colors.sky,
      leaf: colors.leaf,
      ink2: colors.ink2,
      ink3: colors.ink3,
      statusOk: colors.ok,
      statusWarn: colors.warn,
      shadow1: [
        BoxShadow(color: shadowColor.withValues(alpha: 0.04), offset: const Offset(0, 1), blurRadius: 0),
        BoxShadow(color: shadowColor.withValues(alpha: 0.05), offset: const Offset(0, 2), blurRadius: 6),
      ],
      shadow2: [
        BoxShadow(color: shadowColor.withValues(alpha: 0.05), offset: const Offset(0, 2), blurRadius: 0),
        BoxShadow(color: shadowColor.withValues(alpha: 0.08), offset: const Offset(0, 8), blurRadius: 22),
      ],
      shadow3: [
        BoxShadow(color: shadowColor.withValues(alpha: 0.06), offset: const Offset(0, 4), blurRadius: 0),
        BoxShadow(color: shadowColor.withValues(alpha: 0.14), offset: const Offset(0, 18), blurRadius: 40),
      ],
      padCard: padCard,
      padScreen: padScreen,
      gapY: gapY,
      showGrain: true,
    );
  }

  @override
  GreenThumbExtension copyWith({
    Color? clay, Color? onClay, Color? berry, Color? sky, Color? leaf,
    Color? ink2, Color? ink3, Color? statusOk, Color? statusWarn,
    List<BoxShadow>? shadow1, List<BoxShadow>? shadow2, List<BoxShadow>? shadow3,
    double? padCard, double? padScreen, double? gapY, bool? showGrain,
  }) {
    return GreenThumbExtension(
      clay: clay ?? this.clay,
      onClay: onClay ?? this.onClay,
      berry: berry ?? this.berry,
      sky: sky ?? this.sky,
      leaf: leaf ?? this.leaf,
      ink2: ink2 ?? this.ink2,
      ink3: ink3 ?? this.ink3,
      statusOk: statusOk ?? this.statusOk,
      statusWarn: statusWarn ?? this.statusWarn,
      shadow1: shadow1 ?? this.shadow1,
      shadow2: shadow2 ?? this.shadow2,
      shadow3: shadow3 ?? this.shadow3,
      padCard: padCard ?? this.padCard,
      padScreen: padScreen ?? this.padScreen,
      gapY: gapY ?? this.gapY,
      showGrain: showGrain ?? this.showGrain,
    );
  }

  @override
  GreenThumbExtension lerp(GreenThumbExtension? other, double t) {
    if (other == null) return this;
    return GreenThumbExtension(
      clay: Color.lerp(clay, other.clay, t)!,
      onClay: Color.lerp(onClay, other.onClay, t)!,
      berry: Color.lerp(berry, other.berry, t)!,
      sky: Color.lerp(sky, other.sky, t)!,
      leaf: Color.lerp(leaf, other.leaf, t)!,
      ink2: Color.lerp(ink2, other.ink2, t)!,
      ink3: Color.lerp(ink3, other.ink3, t)!,
      statusOk: Color.lerp(statusOk, other.statusOk, t)!,
      statusWarn: Color.lerp(statusWarn, other.statusWarn, t)!,
      shadow1: BoxShadow.lerpList(shadow1, other.shadow1, t)!,
      shadow2: BoxShadow.lerpList(shadow2, other.shadow2, t)!,
      shadow3: BoxShadow.lerpList(shadow3, other.shadow3, t)!,
      padCard: lerpDouble(padCard, other.padCard, t)!,
      padScreen: lerpDouble(padScreen, other.padScreen, t)!,
      gapY: lerpDouble(gapY, other.gapY, t)!,
      showGrain: t < 0.5 ? showGrain : other.showGrain,
    );
  }
}
```

- [ ] **Step 4: Run tests**

```bash
flutter test test/core/theme/green_thumb_extension_test.dart
```

Expected: all 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/core/theme/green_thumb_extension.dart test/core/theme/green_thumb_extension_test.dart
git commit -m "feat: add GreenThumbExtension ThemeExtension"
```

---

### Task 5: app_typography.dart — replace CSS font stacks with bundled fonts

**Files:**

- Modify: `lib/core/theme/app_typography.dart`
- Create: `test/core/theme/app_typography_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/app_typography_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_typography.dart';

void main() {
  group('AppTypography font families', () {
    test('display uses BricolageGrotesque', () {
      expect(AppTypography.display.fontFamily, 'BricolageGrotesque');
    });
    test('display is italic', () {
      expect(AppTypography.display.fontStyle, FontStyle.italic);
    });
    test('display weight is 600', () {
      expect(AppTypography.display.fontWeight, FontWeight.w600);
    });
    test('body uses Geist', () {
      expect(AppTypography.body.fontFamily, 'Geist');
    });
    test('mono uses GeistMono', () {
      expect(AppTypography.mono.fontFamily, 'GeistMono');
    });
    test('eyebrow is uppercase Geist SemiBold 11px', () {
      expect(AppTypography.eyebrow.fontFamily, 'Geist');
      expect(AppTypography.eyebrow.fontWeight, FontWeight.w600);
      expect(AppTypography.eyebrow.fontSize, 11.0);
      expect(AppTypography.eyebrow.letterSpacing, closeTo(0.06 * 11, 0.01));
    });
    test('h1–h3 use BricolageGrotesque italic', () {
      for (final style in [AppTypography.h1, AppTypography.h2, AppTypography.h3]) {
        expect(style.fontFamily, 'BricolageGrotesque');
        expect(style.fontStyle, FontStyle.italic);
      }
    });
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/app_typography_test.dart
```

Expected: FAIL — font families are currently CSS strings.

- [ ] **Step 3: Rewrite app_typography.dart**

Replace the entire contents of `lib/core/theme/app_typography.dart`:

```dart
import 'package:flutter/material.dart';

class AppTypography {
  AppTypography._();

  static const String _display = 'BricolageGrotesque';
  static const String _body = 'Geist';
  static const String _mono = 'GeistMono';

  static const TextStyle display = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 32.0,
    height: 1.02,
    letterSpacing: 32.0 * -0.02,
  );

  static const TextStyle h1 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 28.0,
    height: 1.1,
    letterSpacing: 28.0 * -0.02,
  );

  static const TextStyle h2 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 22.0,
    height: 1.15,
    letterSpacing: 22.0 * -0.02,
  );

  static const TextStyle h3 = TextStyle(
    fontFamily: _display,
    fontWeight: FontWeight.w600,
    fontStyle: FontStyle.italic,
    fontSize: 18.0,
    height: 1.2,
    letterSpacing: 18.0 * -0.02,
  );

  static const TextStyle eyebrow = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 11.0,
    letterSpacing: 11.0 * 0.06,
    height: 1.4,
  );

  static const TextStyle body = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 16.0,
    height: 1.625,
  );

  static const TextStyle bodySm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    height: 1.625,
  );

  static const TextStyle bodyXs = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 12.0,
    height: 1.5,
  );

  static const TextStyle label = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w500,
    fontSize: 14.0,
    height: 1.4,
  );

  static const TextStyle button = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 16.0,
    height: 1.4,
    letterSpacing: 0.25,
  );

  static const TextStyle buttonSm = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w600,
    fontSize: 14.0,
    height: 1.4,
    letterSpacing: 0.25,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: _body,
    fontWeight: FontWeight.w400,
    fontSize: 12.0,
    height: 1.4,
  );

  static const TextStyle mono = TextStyle(
    fontFamily: _mono,
    fontWeight: FontWeight.w400,
    fontSize: 14.0,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}
```

- [ ] **Step 4: Run tests**

```bash
flutter test test/core/theme/app_typography_test.dart
```

Expected: all 7 PASS.

- [ ] **Step 5: Confirm app still analyzes**

```bash
flutter analyze lib/core/theme/app_typography.dart lib/core/theme/app_theme.dart
```

Expected: no errors (app_theme.dart uses AppTypography — verify the method calls still exist).

- [ ] **Step 6: Commit**

```bash
git add lib/core/theme/app_typography.dart test/core/theme/app_typography_test.dart
git commit -m "feat: replace CSS font stacks with bundled BricolageGrotesque and Geist fonts"
```

---

### Task 6: palette_notifier.dart — PaletteSettings and PaletteNotifier

**Files:**

- Create: `lib/config/palette_notifier.dart`
- Create: `lib/config/palette_notifier.g.dart` (build_runner)
- Create: `test/core/theme/palette_notifier_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/palette_notifier_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/config/palette_notifier.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  group('PaletteSettings', () {
    test('default is loam + cozy', () {
      const s = PaletteSettings.defaults;
      expect(s.palette, AppPaletteChoice.loam);
      expect(s.density, AppDensity.cozy);
    });

    test('copyWith overrides individual fields', () {
      final s = const PaletteSettings.defaults
          .copyWith(palette: AppPaletteChoice.forest);
      expect(s.palette, AppPaletteChoice.forest);
      expect(s.density, AppDensity.cozy);
    });
  });

  group('PaletteNotifier initial state', () {
    test('starts with defaults before storage loads', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final state = container.read(paletteProvider);
      expect(state.palette, AppPaletteChoice.loam);
      expect(state.density, AppDensity.cozy);
    });
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/palette_notifier_test.dart
```

Expected: FAIL — `PaletteSettings` not defined.

- [ ] **Step 3: Create palette_notifier.dart**

Create `lib/config/palette_notifier.dart`:

```dart
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../core/theme/app_palettes.dart';
import '../core/theme/green_thumb_extension.dart';

part 'palette_notifier.g.dart';

class PaletteSettings {
  const PaletteSettings({required this.palette, required this.density});
  const PaletteSettings.defaults()
      : palette = AppPaletteChoice.loam,
        density = AppDensity.cozy;

  final AppPaletteChoice palette;
  final AppDensity density;

  PaletteSettings copyWith({AppPaletteChoice? palette, AppDensity? density}) {
    return PaletteSettings(
      palette: palette ?? this.palette,
      density: density ?? this.density,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is PaletteSettings &&
      other.palette == palette &&
      other.density == density;

  @override
  int get hashCode => Object.hash(palette, density);
}

@riverpod
class PaletteNotifier extends _$PaletteNotifier {
  static const _storage = FlutterSecureStorage();
  static const _paletteKey = 'palette_choice';
  static const _densityKey = 'palette_density';

  @override
  PaletteSettings build() {
    _loadSaved();
    return const PaletteSettings.defaults();
  }

  void setPalette(AppPaletteChoice choice) {
    state = state.copyWith(palette: choice);
    unawaited(_storage.write(key: _paletteKey, value: choice.name));
  }

  void setDensity(AppDensity density) {
    state = state.copyWith(density: density);
    unawaited(_storage.write(key: _densityKey, value: density.name));
  }

  Future<void> _loadSaved() async {
    try {
      final savedPalette = await _storage.read(key: _paletteKey);
      final savedDensity = await _storage.read(key: _densityKey);

      final palette = AppPaletteChoice.values
          .where((e) => e.name == savedPalette)
          .firstOrNull;
      final density = AppDensity.values
          .where((e) => e.name == savedDensity)
          .firstOrNull;

      if (ref.mounted && (palette != null || density != null)) {
        state = state.copyWith(palette: palette, density: density);
      }
    } catch (e) {
      debugPrint('[PALETTE] Failed to load saved settings: $e');
    }
  }
}
```

- [ ] **Step 4: Run build_runner**

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

Expected: generates `lib/config/palette_notifier.g.dart` with `paletteProvider`.

- [ ] **Step 5: Run tests**

```bash
flutter test test/core/theme/palette_notifier_test.dart
```

Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/config/palette_notifier.dart lib/config/palette_notifier.g.dart \
  test/core/theme/palette_notifier_test.dart
git commit -m "feat: add PaletteNotifier for palette and density persistence"
```

---

### Task 7: app_theme.dart + main.dart — build() factory and MaterialApp wiring

**Files:**

- Modify: `lib/core/theme/app_theme.dart`
- Modify: `lib/main.dart`
- Create: `test/core/theme/app_theme_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/app_theme_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  group('AppTheme.build', () {
    test('Garden light primary equals moss light', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden, Brightness.light, AppDensity.cozy);
      expect(theme.colorScheme.primary, AppPalettes.garden.light.moss);
    });

    test('Garden dark primary equals moss dark', () {
      final theme = AppTheme.build(
        AppPaletteChoice.garden, Brightness.dark, AppDensity.cozy);
      expect(theme.colorScheme.primary, AppPalettes.garden.dark.moss);
    });

    test('Loam light primary equals moss light', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam, Brightness.light, AppDensity.cozy);
      expect(theme.colorScheme.primary, AppPalettes.loam.light.moss);
    });

    test('Forest light and dark produce same primary', () {
      final light = AppTheme.build(
        AppPaletteChoice.forest, Brightness.light, AppDensity.cozy);
      final dark = AppTheme.build(
        AppPaletteChoice.forest, Brightness.dark, AppDensity.cozy);
      expect(light.colorScheme.primary, dark.colorScheme.primary);
    });

    test('Heritage dark falls back to Garden dark primary', () {
      final hDark = AppTheme.build(
        AppPaletteChoice.heritage, Brightness.dark, AppDensity.cozy);
      final gDark = AppTheme.build(
        AppPaletteChoice.garden, Brightness.dark, AppDensity.cozy);
      expect(hDark.colorScheme.primary, gDark.colorScheme.primary);
    });

    test('GreenThumbExtension is attached', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam, Brightness.light, AppDensity.cozy);
      expect(theme.extension<GreenThumbExtension>(), isNotNull);
    });

    test('Compact density sets padCard to 12', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam, Brightness.light, AppDensity.compact);
      final ext = theme.extension<GreenThumbExtension>()!;
      expect(ext.padCard, 12.0);
    });

    test('useMaterial3 is true', () {
      final theme = AppTheme.build(
        AppPaletteChoice.loam, Brightness.light, AppDensity.cozy);
      expect(theme.useMaterial3, isTrue);
    });
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/app_theme_test.dart
```

Expected: FAIL — `AppTheme.build` not defined.

- [ ] **Step 3: Replace app_theme.dart**

Replace the entire contents of `lib/core/theme/app_theme.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../constants/app_spacing.dart';
import 'app_palettes.dart';
import 'app_typography.dart';
import 'green_thumb_extension.dart';

class AppTheme {
  AppTheme._();

  static ThemeData build(
    AppPaletteChoice choice,
    Brightness brightness,
    AppDensity density,
  ) {
    final palette = AppPalettes.forChoice(choice);
    final colors = brightness == Brightness.light ? palette.light : palette.dark;

    final scheme = ColorScheme(
      brightness: brightness,
      primary: colors.moss,
      onPrimary: colors.onMoss,
      secondary: colors.sage,
      onSecondary: colors.bg,
      tertiary: colors.honey,
      onTertiary: colors.bg,
      error: colors.bad,
      onError: colors.onClay,
      surface: colors.bg,
      onSurface: colors.ink,
      surfaceContainerLow: colors.bg2,
      surfaceContainerHigh: colors.bg3,
      outline: colors.line,
      outlineVariant: colors.line2,
    );

    final ext = GreenThumbExtension.fromColors(
      colors: colors,
      density: density,
      brightness: brightness,
    );

    final textTheme = TextTheme(
      displayLarge: AppTypography.display.copyWith(color: colors.ink),
      headlineLarge: AppTypography.h1.copyWith(color: colors.ink),
      headlineMedium: AppTypography.h2.copyWith(color: colors.ink),
      headlineSmall: AppTypography.h3.copyWith(color: colors.ink),
      bodyLarge: AppTypography.body.copyWith(color: colors.ink),
      bodyMedium: AppTypography.bodySm.copyWith(color: colors.ink),
      bodySmall: AppTypography.bodyXs.copyWith(color: colors.ink),
      labelLarge: AppTypography.label.copyWith(color: colors.ink),
      labelMedium: AppTypography.caption.copyWith(color: colors.ink2),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      extensions: [ext],
      scaffoldBackgroundColor: colors.bg,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: colors.bg,
        foregroundColor: colors.ink,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.h2.copyWith(color: colors.ink),
        systemOverlayStyle: brightness == Brightness.light
            ? SystemUiOverlayStyle.dark
            : SystemUiOverlayStyle.light,
      ),
      cardTheme: CardThemeData(
        color: colors.bg2,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
        ),
        margin: EdgeInsets.zero,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.moss,
          foregroundColor: colors.onMoss,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          textStyle: AppTypography.button,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: colors.moss,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.rSm),
          ),
          textStyle: AppTypography.button,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: colors.moss,
          side: BorderSide(color: colors.moss),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          textStyle: AppTypography.button,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colors.bg2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          borderSide: BorderSide(color: colors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          borderSide: BorderSide(color: colors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          borderSide: BorderSide(color: colors.moss, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          borderSide: BorderSide(color: colors.bad),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        hintStyle: AppTypography.body.copyWith(color: colors.ink3),
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: colors.bg2,
        selectedItemColor: colors.moss,
        unselectedItemColor: colors.ink3,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      dividerTheme: DividerThemeData(
        color: colors.line,
        thickness: 1,
        space: AppSpacing.md,
      ),
      iconTheme: IconThemeData(color: colors.ink, size: AppSpacing.iconMD),
    );
  }
}
```

- [ ] **Step 4: Update main.dart to use build()**

In `lib/main.dart`:

1. Add import:

```dart
import 'config/palette_notifier.dart';
```

Then replace the `MyApp.build` method body (find `final themeMode = ref.watch(themeModeProvider);` and update):

```dart
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final settings = ref.watch(paletteProvider);
    final router = ref.watch(appRouterProvider);
    ref.watch(authServiceProvider);
    ref.listen<AuthState>(authServiceProvider, (previous, next) {
      final error = next.error;
      if (error == null || error == previous?.error) return;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final messenger = _rootScaffoldMessengerKey.currentState;
        messenger
          ?..clearSnackBars()
          ..showSnackBar(SnackBar(content: Text(error)));
      });
    });

    return MaterialApp.router(
      title: 'Plant Community',
      debugShowCheckedModeBanner: false,
      scaffoldMessengerKey: _rootScaffoldMessengerKey,
      theme: AppTheme.build(settings.palette, Brightness.light, settings.density),
      darkTheme: AppTheme.build(settings.palette, Brightness.dark, settings.density),
      themeMode: themeMode,
      routerConfig: router,
    );
  }
```

- [ ] **Step 5: Run tests**

```bash
flutter test test/core/theme/app_theme_test.dart
```

Expected: all 8 PASS.

- [ ] **Step 6: Verify full analysis**

```bash
flutter analyze
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add lib/core/theme/app_theme.dart lib/main.dart test/core/theme/app_theme_test.dart
git commit -m "feat: replace static AppTheme getters with build() factory, wire PaletteNotifier"
```

---

### Task 8: grain_overlay.dart — GrainOverlay widget

**Files:**

- Create: `lib/core/theme/grain_overlay.dart`
- Create: `test/core/theme/grain_overlay_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/core/theme/grain_overlay_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/grain_overlay.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';

Widget _wrap({required bool showGrain, required Widget child}) {
  final theme = AppTheme.build(
    AppPaletteChoice.loam, Brightness.light, AppDensity.cozy,
  ).copyWith(
    extensions: [
      GreenThumbExtension.fromColors(
        colors: AppPalettes.loam.light,
        density: AppDensity.cozy,
        brightness: Brightness.light,
      ).copyWith(showGrain: showGrain),
    ],
  );
  return MaterialApp(theme: theme, home: Scaffold(body: GrainOverlay(child: child)));
}

void main() {
  testWidgets('renders child regardless of showGrain', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const Text('hello')));
    expect(find.text('hello'), findsOneWidget);
  });

  testWidgets('shows Image.asset overlay when showGrain is true', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: true, child: const SizedBox()));
    expect(find.byType(Image), findsOneWidget);
  });

  testWidgets('hides Image.asset overlay when showGrain is false', (tester) async {
    await tester.pumpWidget(_wrap(showGrain: false, child: const SizedBox()));
    expect(find.byType(Image), findsNothing);
  });
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
flutter test test/core/theme/grain_overlay_test.dart
```

Expected: FAIL — `GrainOverlay` not defined.

- [ ] **Step 3: Create grain_overlay.dart**

Create `lib/core/theme/grain_overlay.dart`:

```dart
import 'package:flutter/material.dart';
import 'green_thumb_extension.dart';

class GrainOverlay extends StatelessWidget {
  const GrainOverlay({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<GreenThumbExtension>();
    if (ext == null || !ext.showGrain) return child;

    return Stack(
      children: [
        child,
        Positioned.fill(
          child: IgnorePointer(
            child: Image.asset(
              'assets/images/grain.png',
              fit: BoxFit.cover,
              repeat: ImageRepeat.repeat,
              color: Colors.black.withValues(alpha: 0.35),
              colorBlendMode: BlendMode.multiply,
            ),
          ),
        ),
      ],
    );
  }
}
```

- [ ] **Step 4: Run tests**

```bash
flutter test test/core/theme/grain_overlay_test.dart
```

Expected: all 3 PASS. (Note: `Image.asset` in tests uses the `AssetBundle` — if the test fails with a missing asset error, add `TestWidgetsFlutterBinding.ensureInitialized()` and mock the asset bundle, or skip the image-presence assertion and test only the `Stack`/`SizedBox.shrink` branching.)

- [ ] **Step 5: Commit**

```bash
git add lib/core/theme/grain_overlay.dart test/core/theme/grain_overlay_test.dart
git commit -m "feat: add GrainOverlay widget for paper grain texture"
```

---

### Task 9: theme_preview_screen.dart — debug-only 24-combination grid

**Files:**

- Create: `lib/core/theme/theme_preview_screen.dart`
- Modify: `lib/core/routing/app_router.dart`

- [ ] **Step 1: Create theme_preview_screen.dart**

Create `lib/core/theme/theme_preview_screen.dart`:

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'app_palettes.dart';
import 'app_theme.dart';
import 'green_thumb_extension.dart';

class ThemePreviewScreen extends StatelessWidget {
  const ThemePreviewScreen({super.key});

  static const routePath = '/debug/theme-preview';

  @override
  Widget build(BuildContext context) {
    assert(kDebugMode, 'ThemePreviewScreen must only be used in debug builds');

    final combinations = [
      for (final palette in AppPaletteChoice.values)
        for (final brightness in Brightness.values)
          for (final density in AppDensity.values)
            (palette: palette, brightness: brightness, density: density),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Theme Preview (24 combinations)')),
      body: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: combinations.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final c = combinations[i];
          final theme = AppTheme.build(c.palette, c.brightness, c.density);
          final ext = theme.extension<GreenThumbExtension>()!;
          return _CombinationTile(theme: theme, ext: ext, combo: c);
        },
      ),
    );
  }
}

class _CombinationTile extends StatelessWidget {
  const _CombinationTile({
    required this.theme,
    required this.ext,
    required this.combo,
  });

  final ThemeData theme;
  final GreenThumbExtension ext;
  final ({AppPaletteChoice palette, Brightness brightness, AppDensity density}) combo;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: theme.colorScheme.outline),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${combo.palette.name} · ${combo.brightness.name} · ${combo.density.name}',
              style: TextStyle(
                color: theme.colorScheme.onSurface,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          _Swatch(color: theme.colorScheme.primary, label: 'primary'),
          const SizedBox(width: 4),
          _Swatch(color: theme.colorScheme.surface, label: 'surface'),
          const SizedBox(width: 4),
          _Swatch(color: ext.clay, label: 'clay'),
        ],
      ),
    );
  }
}

class _Swatch extends StatelessWidget {
  const _Swatch({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: Colors.black12),
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Add debug route to app_router.dart**

In `lib/core/routing/app_router.dart`, add the following import at the top (inside a `kDebugMode` conditional is not possible at import level — just import it normally):

```dart
import 'package:flutter/foundation.dart';
import '../theme/theme_preview_screen.dart';
```

Then, inside the `GoRouter` routes list, add a debug-only route. Find the routes list and add at the end before the closing bracket:

```dart
if (kDebugMode)
  GoRoute(
    path: ThemePreviewScreen.routePath,
    builder: (context, state) => const ThemePreviewScreen(),
  ),
```

- [ ] **Step 3: Verify analysis**

```bash
flutter analyze
```

Expected: no errors.

- [ ] **Step 4: Manually verify (simulator)**

```bash
flutter run -d ios
```

In a debug build, navigate to `/debug/theme-preview` (e.g. via `context.push(ThemePreviewScreen.routePath)` from a temporary button, or add it temporarily to the profile screen). Verify all 24 rows render with correct swatches — compare primary swatch against the design reference file.

- [ ] **Step 5: Commit**

```bash
git add lib/core/theme/theme_preview_screen.dart lib/core/routing/app_router.dart
git commit -m "feat: add debug ThemePreviewScreen for 24-combination theme verification"
```

---

### Task 10: Full test suite and final analysis

**Files:** no new files

- [ ] **Step 1: Run all theme tests**

```bash
flutter test test/core/theme/
```

Expected: all tests PASS. Count should be at least 35 (sum of all tasks above).

- [ ] **Step 2: Run full test suite**

```bash
flutter test
```

Expected: all existing tests continue to pass. If any existing test imports `AppTheme.lightTheme` or `AppTheme.darkTheme`, update those calls to `AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)` and `AppTheme.build(AppPaletteChoice.loam, Brightness.dark, AppDensity.cozy)`.

- [ ] **Step 3: Run flutter analyze**

```bash
flutter analyze
```

Expected: zero errors, zero warnings on new files.

- [ ] **Step 4: Confirm screen files unchanged**

```bash
git diff HEAD -- lib/features/
```

Expected: empty diff. No feature screen files should have been modified.

- [ ] **Step 5: Final commit**

```bash
git add -p  # stage any cleanup
git commit -m "chore: Green Thumb design system Phase 1 — wire-up complete"
```
