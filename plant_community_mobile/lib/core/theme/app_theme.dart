import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../constants/app_spacing.dart';
import 'app_typography.dart';
import 'canopy_palette.dart';
import 'green_thumb_extension.dart';

/// Builds the Canopy `ThemeData`.
///
/// Every Material control the app uses is themed explicitly. An unthemed M3
/// control falls back to the baseline purple scheme and silently leaves the
/// design system — `navigationBarTheme` was exactly that bug once (the app read
/// `bottomNavigationBarTheme`, a different Material 2 widget, as proof the nav
/// bar was styled, while it rendered stock purple).
class AppTheme {
  AppTheme._();

  /// Dark is the design's identity, not a preference — the web's `ThemeContext`
  /// seeds `mode: 'dark'` and `:root` carries the dark values (spec §3.4).
  /// Asserted against the canonical contract by `canopy_parity_test.dart`.
  static const ThemeMode defaultThemeMode = ThemeMode.dark;

  /// Matches the web's `density: 'cozy'` default.
  static const AppDensity defaultDensity = AppDensity.cozy;

  static ThemeData build(Brightness brightness, AppDensity density) {
    final colors = CanopyPalette.of(brightness);
    final ext = GreenThumbExtension.fromColors(
      colors: colors,
      density: density,
      brightness: brightness,
    );

    // Canopy has FOUR ground levels (ground → surface → surface-2 → surface-3)
    // where ColorScheme has one `surface` plus containers. `ground` is the page
    // behind everything (the scaffold), `surface` the app-frame canvas.
    final scheme = ColorScheme(
      brightness: brightness,
      primary: colors.primary,
      onPrimary: colors.onPrimary,
      secondary: colors.secondary,
      onSecondary: colors.ground,
      tertiary: colors.tertiary,
      onTertiary: colors.ground,
      error: colors.error,
      onError: colors.onError,
      // Material 3 DERIVES the four `*Container` pairs from the seed when they
      // are not given, and those derived colours are not Canopy colours — the
      // auth error banner was rendering a mauve-pink that appears nowhere in
      // the design system, and the avatar discs a lilac. The web has one
      // recipe for an accent-tinted surface: `bg-<accent>/15..20` with
      // `text-ink` (PostCard's selected reaction, TipTapEditor's active tool,
      // ThreadCard's selection). A translucent role composites over whatever
      // surface is behind it, which is what the CSS does too.
      primaryContainer: colors.primary.withValues(alpha: 0.20),
      onPrimaryContainer: colors.ink,
      secondaryContainer: colors.secondary.withValues(alpha: 0.15),
      onSecondaryContainer: colors.ink,
      tertiaryContainer: colors.tertiary.withValues(alpha: 0.15),
      onTertiaryContainer: colors.ink,
      errorContainer: colors.error.withValues(alpha: 0.10),
      onErrorContainer: colors.ink,
      surface: colors.surface,
      onSurface: colors.ink,
      onSurfaceVariant: colors.ink2,
      surfaceContainerLowest: colors.ground,
      surfaceContainerLow: colors.surface2,
      surfaceContainer: colors.surface2,
      surfaceContainerHigh: colors.surface3,
      surfaceContainerHighest: colors.surface3,
      outline: colors.line,
      outlineVariant: colors.line2,
      shadow: colors.shadowColor,
      scrim: colors.shadowColor,
      inverseSurface: colors.ink,
      onInverseSurface: colors.ground,
    );

    final textTheme = TextTheme(
      displayLarge: AppTypography.display.copyWith(color: colors.ink),
      displayMedium: AppTypography.h1.copyWith(color: colors.ink),
      headlineLarge: AppTypography.h1.copyWith(color: colors.ink),
      headlineMedium: AppTypography.h2.copyWith(color: colors.ink),
      headlineSmall: AppTypography.h3.copyWith(color: colors.ink),
      // `title*` are the display face too: a card heading is a heading.
      titleLarge: AppTypography.h3.copyWith(color: colors.ink),
      titleMedium: AppTypography.bodyLg.copyWith(
        color: colors.ink,
        fontWeight: FontWeight.w600,
      ),
      titleSmall: AppTypography.body.copyWith(
        color: colors.ink,
        fontWeight: FontWeight.w600,
      ),
      bodyLarge: AppTypography.bodyLg.copyWith(color: colors.ink),
      bodyMedium: AppTypography.body.copyWith(color: colors.ink),
      bodySmall: AppTypography.bodySm.copyWith(color: colors.ink2),
      labelLarge: AppTypography.uiLabel.copyWith(color: colors.ink),
      labelMedium: AppTypography.meta.copyWith(color: colors.ink2),
      labelSmall: AppTypography.micro.copyWith(color: colors.ink3),
    );

    /// Shared shape for the pill controls.
    final pill = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppSpacing.rPill),
    );
    const buttonPadding = EdgeInsets.symmetric(
      horizontal: AppSpacing.lg,
      vertical: 12,
    );

    // Web's `disabled:opacity-50 disabled:cursor-not-allowed`. Material has no
    // whole-widget opacity, so disabled fills/foregrounds are resolved per state.
    Color disabledOn(Color c) => c.withValues(alpha: 0.38);

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      extensions: [ext],
      // `ground`, not `surface`: the scaffold is the page behind the frame.
      scaffoldBackgroundColor: colors.ground,
      canvasColor: colors.surface,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,

      appBarTheme: AppBarTheme(
        backgroundColor: colors.ground,
        foregroundColor: colors.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.h3.copyWith(color: colors.ink),
        iconTheme: IconThemeData(color: colors.ink, size: AppSpacing.iconMD),
        systemOverlayStyle: brightness == Brightness.light
            ? SystemUiOverlayStyle.dark
            : SystemUiOverlayStyle.light,
      ),

      // A plain `Card` cannot paint `--gt-grad-card`, so stock Cards get the
      // flat mid surface. Use `CanopyCard` for the real gradient material.
      cardTheme: CardThemeData(
        color: colors.surface2,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
          side: BorderSide(color: colors.line),
        ),
        margin: EdgeInsets.zero,
      ),

      // ── buttons ─────────────────────────────────────────────────────────
      // Web recipes (buttonStyles.ts):
      //   primary   → gradient CTA + shadow-1, lifts on hover
      //   secondary → surface-2 fill, line border
      //   outline   → line-2 border, no fill
      //   ghost     → ink-2 text, surface-2 on hover
      // Flutter has no gradient in `ButtonStyle`, so the gradient primary lives
      // in `ClayButton`; `FilledButton` uses the CTA's end colour flat.
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: colors.primary,
          foregroundColor: colors.onPrimary,
          disabledBackgroundColor: colors.surface3,
          disabledForegroundColor: disabledOn(colors.ink),
          shape: pill,
          padding: buttonPadding,
          textStyle: AppTypography.button,
          elevation: 0,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colors.primary,
          foregroundColor: colors.onPrimary,
          disabledBackgroundColor: colors.surface3,
          disabledForegroundColor: disabledOn(colors.ink),
          shape: pill,
          padding: buttonPadding,
          textStyle: AppTypography.button,
          elevation: 0,
          shadowColor: Colors.transparent,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style:
            OutlinedButton.styleFrom(
              foregroundColor: colors.ink,
              disabledForegroundColor: disabledOn(colors.ink),
              side: BorderSide(color: colors.line2),
              shape: pill,
              padding: buttonPadding,
              textStyle: AppTypography.button,
            ).copyWith(
              overlayColor: WidgetStatePropertyAll(
                colors.surface2.withValues(alpha: 0.6),
              ),
            ),
      ),
      textButtonTheme: TextButtonThemeData(
        style:
            TextButton.styleFrom(
              // Ghost: ink-2 text, NOT a coloured link — the web's ghost variant.
              foregroundColor: colors.ink2,
              disabledForegroundColor: disabledOn(colors.ink),
              shape: pill,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              textStyle: AppTypography.button,
            ).copyWith(
              overlayColor: WidgetStatePropertyAll(
                colors.surface2.withValues(alpha: 0.6),
              ),
            ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: colors.ink2,
          highlightColor: colors.surface2,
        ),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? colors.surface3
                : Colors.transparent,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? colors.ink : colors.ink2,
          ),
          side: WidgetStatePropertyAll(BorderSide(color: colors.line2)),
          shape: WidgetStatePropertyAll(pill),
          textStyle: WidgetStatePropertyAll(AppTypography.buttonSm),
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: colors.primary,
        foregroundColor: colors.onPrimary,
        elevation: 4,
        focusElevation: 4,
        hoverElevation: 6,
        splashColor: colors.secondary.withValues(alpha: 0.24),
        shape: const CircleBorder(),
      ),

      // ── inputs ──────────────────────────────────────────────────────────
      // The web input is an OUTLINED field on the card surface — no fill until
      // disabled (`disabled:bg-surface-2`) — with `rounded-lg` (22px), a
      // `line-2` resting border and a 2px primary focus border standing in for
      // `focus:border-primary` + `focus:ring-2`. Matched here rather than kept
      // at Flutter's previous filled/10px treatment.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: WidgetStateColor.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? colors.surface2
              : Colors.transparent,
        ),
        border: _inputBorder(colors.line2),
        enabledBorder: _inputBorder(colors.line2),
        disabledBorder: _inputBorder(colors.line),
        focusedBorder: _inputBorder(colors.primary, width: 2),
        errorBorder: _inputBorder(colors.error),
        focusedErrorBorder: _inputBorder(colors.error, width: 2),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 14,
        ),
        labelStyle: AppTypography.uiLabel.copyWith(color: colors.ink2),
        floatingLabelStyle: AppTypography.uiLabel.copyWith(color: colors.ink2),
        hintStyle: AppTypography.body.copyWith(color: colors.ink3),
        helperStyle: AppTypography.bodySm.copyWith(color: colors.ink3),
        errorStyle: AppTypography.bodySm.copyWith(color: colors.error),
        prefixIconColor: colors.ink3,
        suffixIconColor: colors.ink3,
      ),

      // ── navigation ──────────────────────────────────────────────────────
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: colors.surface,
        surfaceTintColor: Colors.transparent,
        // Mirrors the web's `.app-nav-active` pill.
        indicatorColor: colors.surface3,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rPill),
        ),
        elevation: 0,
        height: 64,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            size: AppSpacing.iconMD,
            color: states.contains(WidgetState.selected)
                ? colors.ink
                : colors.ink3,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => AppTypography.micro.copyWith(
            color: states.contains(WidgetState.selected)
                ? colors.ink
                : colors.ink3,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w600
                : FontWeight.w500,
          ),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: colors.surface,
        indicatorColor: colors.surface3,
        selectedIconTheme: IconThemeData(
          color: colors.ink,
          size: AppSpacing.iconMD,
        ),
        unselectedIconTheme: IconThemeData(
          color: colors.ink3,
          size: AppSpacing.iconMD,
        ),
        selectedLabelTextStyle: AppTypography.micro.copyWith(color: colors.ink),
        unselectedLabelTextStyle: AppTypography.micro.copyWith(
          color: colors.ink3,
        ),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: colors.ink,
        unselectedLabelColor: colors.ink3,
        labelStyle: AppTypography.uiLabel.copyWith(fontWeight: FontWeight.w600),
        unselectedLabelStyle: AppTypography.uiLabel,
        indicatorColor: colors.primary,
        dividerColor: colors.line,
      ),
      drawerTheme: DrawerThemeData(
        backgroundColor: colors.surface,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.horizontal(
            right: Radius.circular(AppSpacing.rLg),
          ),
        ),
      ),

      // ── surfaces & overlays ─────────────────────────────────────────────
      dialogTheme: DialogThemeData(
        backgroundColor: colors.surface2,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rLg),
          side: BorderSide(color: colors.line),
        ),
        titleTextStyle: AppTypography.h3.copyWith(color: colors.ink),
        contentTextStyle: AppTypography.body.copyWith(color: colors.ink2),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: colors.surface2,
        surfaceTintColor: Colors.transparent,
        modalBackgroundColor: colors.surface2,
        elevation: 0,
        modalElevation: 0,
        showDragHandle: true,
        dragHandleColor: colors.line2,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(AppSpacing.rLg),
          ),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: colors.surface2,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
          side: BorderSide(color: colors.line),
        ),
        textStyle: AppTypography.body.copyWith(color: colors.ink),
      ),
      menuTheme: MenuThemeData(
        style: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(colors.surface2),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppSpacing.rMd),
              side: BorderSide(color: colors.line),
            ),
          ),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: colors.surface3,
        contentTextStyle: AppTypography.body.copyWith(color: colors.ink),
        actionTextColor: colors.primary,
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
          side: BorderSide(color: colors.line),
        ),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: colors.surface3,
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          border: Border.all(color: colors.line),
        ),
        textStyle: AppTypography.meta.copyWith(color: colors.ink),
      ),

      // ── small elements ──────────────────────────────────────────────────
      chipTheme: ChipThemeData(
        backgroundColor: colors.surface2,
        selectedColor: colors.surface3,
        disabledColor: colors.surface2,
        surfaceTintColor: Colors.transparent,
        labelStyle: AppTypography.bodySm.copyWith(color: colors.ink2),
        secondaryLabelStyle: AppTypography.bodySm.copyWith(color: colors.ink),
        side: BorderSide(color: colors.line),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rPill),
        ),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        elevation: 0,
        pressElevation: 0,
      ),
      badgeTheme: BadgeThemeData(
        backgroundColor: colors.error,
        textColor: colors.onError,
        textStyle: AppTypography.micro.copyWith(fontWeight: FontWeight.w600),
        padding: const EdgeInsets.symmetric(horizontal: 5),
      ),
      dividerTheme: DividerThemeData(
        color: colors.line,
        thickness: 1,
        space: AppSpacing.md,
      ),
      iconTheme: IconThemeData(color: colors.ink, size: AppSpacing.iconMD),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: colors.primary,
        linearTrackColor: colors.surface3,
        circularTrackColor: colors.surface3,
      ),
      listTileTheme: ListTileThemeData(
        iconColor: colors.ink2,
        textColor: colors.ink,
        titleTextStyle: AppTypography.body.copyWith(color: colors.ink),
        subtitleTextStyle: AppTypography.bodySm.copyWith(color: colors.ink3),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (s) =>
              s.contains(WidgetState.selected) ? colors.onPrimary : colors.ink3,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected)
              ? colors.primary
              : colors.surface3,
        ),
        trackOutlineColor: WidgetStatePropertyAll(colors.line2),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected)
              ? colors.primary
              : Colors.transparent,
        ),
        checkColor: WidgetStatePropertyAll(colors.onPrimary),
        side: BorderSide(color: colors.line2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.rXs),
        ),
      ),
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith(
          (s) =>
              s.contains(WidgetState.selected) ? colors.primary : colors.line2,
        ),
      ),
      sliderTheme: SliderThemeData(
        activeTrackColor: colors.primary,
        inactiveTrackColor: colors.surface3,
        thumbColor: colors.primary,
        overlayColor: colors.secondary.withValues(alpha: 0.16),
      ),
      // The app-wide focus accent — the web uses `ring-secondary` everywhere.
      focusColor: colors.secondary.withValues(alpha: 0.24),
      highlightColor: colors.secondary.withValues(alpha: 0.12),
      splashColor: colors.secondary.withValues(alpha: 0.12),
    );
  }

  static OutlineInputBorder _inputBorder(Color color, {double width = 1}) =>
      OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.rLg),
        borderSide: BorderSide(color: color, width: width),
      );
}
