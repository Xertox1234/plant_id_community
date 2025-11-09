import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';
import 'app_typography.dart';
import '../constants/app_spacing.dart';

/// Main theme configuration for the Plant Community app.
/// Provides light and dark theme data based on the design system.
class AppTheme {
  AppTheme._(); // Private constructor to prevent instantiation

  // ============================================
  // LIGHT THEME
  // ============================================
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,

      // Color scheme
      colorScheme: ColorScheme.light(
        primary: AppColors.green600,
        onPrimary: AppColors.lightPrimaryForeground,
        secondary: AppColors.lightSecondary,
        onSecondary: AppColors.lightSecondaryForeground,
        error: AppColors.lightDestructive,
        onError: AppColors.lightDestructiveForeground,
        surface: AppColors.lightCard,
        onSurface: AppColors.lightForeground,
        surfaceContainerHighest: AppColors.lightMuted,
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.lightBackground,

      // App bar
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.lightBackground,
        foregroundColor: AppColors.lightForeground,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.h2.copyWith(
          color: AppColors.lightForeground,
        ),
        systemOverlayStyle: SystemUiOverlayStyle.dark,
      ),

      // Card
      cardTheme: const CardThemeData(
        color: AppColors.lightCard,
        elevation: AppSpacing.elevationSM,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppSpacing.radiusLG)),
        ),
        margin: EdgeInsets.all(AppSpacing.sm),
      ),

      // Input decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.lightInputBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.lightBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.lightBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.green600, width: 2.0),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.lightDestructive),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        hintStyle: AppTypography.body.copyWith(
          color: AppColors.lightMutedForeground,
        ),
      ),

      // Elevated button
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green600,
          foregroundColor: AppColors.lightPrimaryForeground,
          elevation: AppSpacing.elevationSM,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.buttonPaddingH,
            vertical: AppSpacing.buttonPaddingV,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Text button
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.green600,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Outlined button
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.green600,
          side: BorderSide(color: AppColors.green600),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.buttonPaddingH,
            vertical: AppSpacing.buttonPaddingV,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Bottom navigation bar
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: AppColors.lightCard,
        selectedItemColor: AppColors.green600,
        unselectedItemColor: AppColors.lightMutedForeground,
        type: BottomNavigationBarType.fixed,
        elevation: AppSpacing.elevationMD,
      ),

      // Divider
      dividerTheme: DividerThemeData(
        color: AppColors.lightBorder,
        thickness: 1.0,
        space: AppSpacing.md,
      ),

      // Text theme
      textTheme: TextTheme(
        displayLarge: AppTypography.display.copyWith(color: AppColors.lightForeground),
        headlineLarge: AppTypography.h1.copyWith(color: AppColors.lightForeground),
        headlineMedium: AppTypography.h2.copyWith(color: AppColors.lightForeground),
        headlineSmall: AppTypography.h3.copyWith(color: AppColors.lightForeground),
        bodyLarge: AppTypography.body.copyWith(color: AppColors.lightForeground),
        bodyMedium: AppTypography.bodySM.copyWith(color: AppColors.lightForeground),
        bodySmall: AppTypography.bodyXS.copyWith(color: AppColors.lightForeground),
        labelLarge: AppTypography.label.copyWith(color: AppColors.lightForeground),
        labelMedium: AppTypography.caption.copyWith(color: AppColors.lightMutedForeground),
      ),

      // Icon theme
      iconTheme: IconThemeData(
        color: AppColors.lightForeground,
        size: AppSpacing.iconMD,
      ),
    );
  }

  // ============================================
  // DARK THEME
  // ============================================
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,

      // Color scheme
      colorScheme: ColorScheme.dark(
        primary: AppColors.green600,
        onPrimary: AppColors.darkPrimaryForeground,
        secondary: AppColors.darkSecondary,
        onSecondary: AppColors.darkSecondaryForeground,
        error: AppColors.darkDestructive,
        onError: AppColors.darkDestructiveForeground,
        surface: AppColors.darkCard,
        onSurface: AppColors.darkForeground,
        surfaceContainerHighest: AppColors.darkMuted,
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.darkBackground,

      // App bar
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.darkBackground,
        foregroundColor: AppColors.darkForeground,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.h2.copyWith(
          color: AppColors.darkForeground,
        ),
        systemOverlayStyle: SystemUiOverlayStyle.light,
      ),

      // Card
      cardTheme: const CardThemeData(
        color: AppColors.darkCard,
        elevation: AppSpacing.elevationSM,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppSpacing.radiusLG)),
        ),
        margin: EdgeInsets.all(AppSpacing.sm),
      ),

      // Input decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.darkInput,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.darkBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.darkBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.green600, width: 2.0),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          borderSide: BorderSide(color: AppColors.darkDestructive),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        hintStyle: AppTypography.body.copyWith(
          color: AppColors.darkMutedForeground,
        ),
      ),

      // Elevated button
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green600,
          foregroundColor: AppColors.lightPrimaryForeground,
          elevation: AppSpacing.elevationSM,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.buttonPaddingH,
            vertical: AppSpacing.buttonPaddingV,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Text button
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.green600,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Outlined button
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.green600,
          side: BorderSide(color: AppColors.green600),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.buttonPaddingH,
            vertical: AppSpacing.buttonPaddingV,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          ),
          textStyle: AppTypography.button,
        ),
      ),

      // Bottom navigation bar
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: AppColors.darkCard,
        selectedItemColor: AppColors.green600,
        unselectedItemColor: AppColors.darkMutedForeground,
        type: BottomNavigationBarType.fixed,
        elevation: AppSpacing.elevationMD,
      ),

      // Divider
      dividerTheme: DividerThemeData(
        color: AppColors.darkBorder,
        thickness: 1.0,
        space: AppSpacing.md,
      ),

      // Text theme
      textTheme: TextTheme(
        displayLarge: AppTypography.display.copyWith(color: AppColors.darkForeground),
        headlineLarge: AppTypography.h1.copyWith(color: AppColors.darkForeground),
        headlineMedium: AppTypography.h2.copyWith(color: AppColors.darkForeground),
        headlineSmall: AppTypography.h3.copyWith(color: AppColors.darkForeground),
        bodyLarge: AppTypography.body.copyWith(color: AppColors.darkForeground),
        bodyMedium: AppTypography.bodySM.copyWith(color: AppColors.darkForeground),
        bodySmall: AppTypography.bodyXS.copyWith(color: AppColors.darkForeground),
        labelLarge: AppTypography.label.copyWith(color: AppColors.darkForeground),
        labelMedium: AppTypography.caption.copyWith(color: AppColors.darkMutedForeground),
      ),

      // Icon theme
      iconTheme: IconThemeData(
        color: AppColors.darkForeground,
        size: AppSpacing.iconMD,
      ),
    );
  }
}
