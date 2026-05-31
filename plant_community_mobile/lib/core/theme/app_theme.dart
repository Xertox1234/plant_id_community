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
    final colors = brightness == Brightness.light
        ? palette.light
        : palette.dark;

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
