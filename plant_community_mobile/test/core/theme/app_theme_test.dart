import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/constants/app_spacing.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/canopy_palette.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

void main() {
  final light = AppTheme.build(Brightness.light, AppDensity.cozy);
  final dark = AppTheme.build(Brightness.dark, AppDensity.cozy);

  group('Material 3 NavigationBar theme (todo 384)', () {
    // MainShell renders a NavigationBar. The `bottomNavigationBarTheme` that
    // used to sit alongside it styles BottomNavigationBar — a DIFFERENT,
    // Material 2 widget — and todo 384 read its presence as proof the nav bar
    // was themed. It was not: without `navigationBarTheme` the shell renders
    // in stock M3 purple.
    test('navigationBarTheme is defined, not just the legacy M2 one', () {
      expect(
        dark.navigationBarTheme.backgroundColor,
        CanopyPalette.dark.surface,
        reason: 'the shell nav bar must use the Canopy surface, not M3 default',
      );
    });

    test('selected and unselected destinations are distinguishable', () {
      final icons = dark.navigationBarTheme.iconTheme;
      expect(icons, isNotNull);

      final selected = icons!.resolve({WidgetState.selected})?.color;
      final unselected = icons.resolve(<WidgetState>{})?.color;

      expect(selected, CanopyPalette.dark.ink);
      expect(unselected, CanopyPalette.dark.ink3);
      // Lucide has no filled variants, so colour is the ONLY thing marking the
      // active tab. If these ever resolve the same, the user cannot tell which
      // tab they are on.
      expect(selected, isNot(unselected));
    });
  });

  group('AppTheme.build', () {
    test('primary is the Canopy CTA colour in each mode', () {
      expect(light.colorScheme.primary, CanopyPalette.light.primary);
      expect(dark.colorScheme.primary, CanopyPalette.dark.primary);
      // Light derives from the same ramp rather than inverting, so the two
      // modes must NOT share a primary.
      expect(light.colorScheme.primary, isNot(dark.colorScheme.primary));
    });

    test('the four Canopy ground levels map onto ColorScheme', () {
      // Canopy has ground → surface → surface-2 → surface-3 where Material has
      // `surface` plus containers. Getting this mapping wrong flattens the
      // whole design, so it is pinned explicitly.
      expect(dark.scaffoldBackgroundColor, CanopyPalette.dark.ground);
      expect(dark.colorScheme.surface, CanopyPalette.dark.surface);
      expect(dark.colorScheme.surfaceContainerLow, CanopyPalette.dark.surface2);
      expect(
        dark.colorScheme.surfaceContainerHigh,
        CanopyPalette.dark.surface3,
      );
    });

    test('GreenThumbExtension is attached', () {
      expect(light.extension<GreenThumbExtension>(), isNotNull);
    });

    test('density drives the extension padding', () {
      final compact = AppTheme.build(Brightness.light, AppDensity.compact);
      expect(compact.extension<GreenThumbExtension>()!.padCard, 12.0);
      expect(light.extension<GreenThumbExtension>()!.padCard, 16.0);
    });

    test('useMaterial3 is true', () {
      expect(light.useMaterial3, isTrue);
    });
  });

  group('controls are explicitly themed, not left at M3 defaults', () {
    // Objective 5: an unthemed control silently leaves the design system. Each
    // of these asserts a Canopy token reached the widget's theme.
    test('inputs use the canonical radius and border colours', () {
      final input = dark.inputDecorationTheme;
      final border = input.enabledBorder! as OutlineInputBorder;
      expect(
        border.borderRadius.topLeft.x,
        AppSpacing.rLg,
        reason: 'web inputs are rounded-lg (22px), not the old 10px',
      );
      expect(border.borderSide.color, CanopyPalette.dark.line2);
      expect(
        (input.focusedBorder! as OutlineInputBorder).borderSide.color,
        CanopyPalette.dark.primary,
      );
      expect(
        (input.errorBorder! as OutlineInputBorder).borderSide.color,
        CanopyPalette.dark.error,
      );
    });

    test('an enabled field is unfilled and a disabled one is not', () {
      // Mirrors the web: transparent over the card until `disabled:bg-surface-2`.
      final fill = dark.inputDecorationTheme.fillColor!;
      expect(
        WidgetStateProperty.resolveAs<Color>(fill, <WidgetState>{}),
        Colors.transparent,
      );
      expect(
        WidgetStateProperty.resolveAs<Color>(fill, {WidgetState.disabled}),
        CanopyPalette.dark.surface2,
      );
    });

    test('dialogs, sheets, snackbars and chips carry Canopy surfaces', () {
      expect(dark.dialogTheme.backgroundColor, CanopyPalette.dark.surface2);
      expect(
        dark.bottomSheetTheme.backgroundColor,
        CanopyPalette.dark.surface2,
      );
      expect(dark.snackBarTheme.backgroundColor, CanopyPalette.dark.surface3);
      expect(dark.chipTheme.backgroundColor, CanopyPalette.dark.surface2);
      expect(dark.badgeTheme.backgroundColor, CanopyPalette.dark.error);
      expect(dark.popupMenuTheme.color, CanopyPalette.dark.surface2);
      expect(dark.tooltipTheme.textStyle!.color, CanopyPalette.dark.ink);
    });

    test('every button variant is themed and pill-shaped', () {
      for (final (name, shape) in [
        ('filled', dark.filledButtonTheme.style?.shape),
        ('elevated', dark.elevatedButtonTheme.style?.shape),
        ('outlined', dark.outlinedButtonTheme.style?.shape),
        ('text', dark.textButtonTheme.style?.shape),
      ]) {
        final resolved =
            shape?.resolve(<WidgetState>{}) as RoundedRectangleBorder?;
        expect(resolved, isNotNull, reason: '$name button is unthemed');
        expect(
          (resolved!.borderRadius as BorderRadius).topLeft.x,
          AppSpacing.rPill,
          reason: '$name button must be a pill',
        );
      }
    });

    test('no control is left on the stock M3 purple', () {
      // The baseline M3 seed colour. If any of these ever equals it, that
      // control never got a Canopy value.
      const m3Purple = Color(0xFF6750A4);
      for (final color in <Color?>[
        dark.colorScheme.primary,
        dark.navigationBarTheme.backgroundColor,
        dark.chipTheme.backgroundColor,
        dark.dialogTheme.backgroundColor,
        dark.floatingActionButtonTheme.backgroundColor,
      ]) {
        expect(color, isNot(m3Purple));
      }
    });
  });
}
