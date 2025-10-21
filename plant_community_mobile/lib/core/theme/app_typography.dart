import 'package:flutter/material.dart';

/// App typography system extracted from design tokens.
/// Follows Material Design typography with custom adjustments.
class AppTypography {
  AppTypography._(); // Private constructor to prevent instantiation

  // ============================================
  // FONT FAMILY
  // ============================================
  /// Primary font family (system fonts)
  static const String fontFamilySans = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
  
  /// Monospace font family
  static const String fontFamilyMono = 'SF Mono, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';

  // ============================================
  // FONT SIZES
  // ============================================
  static const double fontSizeXS = 12.0; // 0.75rem
  static const double fontSizeSM = 14.0; // 0.875rem
  static const double fontSizeBase = 16.0; // 1rem - Body text
  static const double fontSizeLG = 18.0; // 1.125rem
  static const double fontSizeXL = 20.0; // 1.25rem
  static const double fontSize2XL = 24.0; // 1.5rem - Main headings

  // ============================================
  // FONT WEIGHTS
  // ============================================
  static const FontWeight fontWeightNormal = FontWeight.w400; // Body text
  static const FontWeight fontWeightMedium = FontWeight.w500; // Headings, buttons, labels

  // ============================================
  // LINE HEIGHTS
  // ============================================
  static const double lineHeightTight = 1.5; // Headings
  static const double lineHeightRelaxed = 1.625; // Body paragraphs

  // ============================================
  // TEXT STYLES
  // ============================================
  
  /// Display text (2xl)
  static const TextStyle display = TextStyle(
    fontSize: fontSize2XL,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
    letterSpacing: -0.5,
  );

  /// Heading 1 (xl)
  static const TextStyle h1 = TextStyle(
    fontSize: fontSizeXL,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
    letterSpacing: -0.25,
  );

  /// Heading 2 (lg)
  static const TextStyle h2 = TextStyle(
    fontSize: fontSizeLG,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
  );

  /// Heading 3 (base)
  static const TextStyle h3 = TextStyle(
    fontSize: fontSizeBase,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
  );

  /// Body text (base)
  static const TextStyle body = TextStyle(
    fontSize: fontSizeBase,
    fontWeight: fontWeightNormal,
    height: lineHeightRelaxed,
  );

  /// Body text small (sm)
  static const TextStyle bodySM = TextStyle(
    fontSize: fontSizeSM,
    fontWeight: fontWeightNormal,
    height: lineHeightRelaxed,
  );

  /// Body text extra small (xs)
  static const TextStyle bodyXS = TextStyle(
    fontSize: fontSizeXS,
    fontWeight: fontWeightNormal,
    height: lineHeightRelaxed,
  );

  /// Label text (sm, medium weight)
  static const TextStyle label = TextStyle(
    fontSize: fontSizeSM,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
  );

  /// Button text (base, medium weight)
  static const TextStyle button = TextStyle(
    fontSize: fontSizeBase,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
    letterSpacing: 0.25,
  );

  /// Button text small (sm, medium weight)
  static const TextStyle buttonSM = TextStyle(
    fontSize: fontSizeSM,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
    letterSpacing: 0.25,
  );

  /// Caption text (xs)
  static const TextStyle caption = TextStyle(
    fontSize: fontSizeXS,
    fontWeight: fontWeightNormal,
    height: lineHeightTight,
  );

  /// Overline text (xs, medium, uppercase)
  static const TextStyle overline = TextStyle(
    fontSize: fontSizeXS,
    fontWeight: fontWeightMedium,
    height: lineHeightTight,
    letterSpacing: 1.0,
  );

  // ============================================
  // HELPER METHODS
  // ============================================
  
  /// Apply color to text style
  static TextStyle withColor(TextStyle style, Color color) {
    return style.copyWith(color: color);
  }

  /// Apply font weight to text style
  static TextStyle withWeight(TextStyle style, FontWeight weight) {
    return style.copyWith(fontWeight: weight);
  }

  /// Apply font size to text style
  static TextStyle withSize(TextStyle style, double size) {
    return style.copyWith(fontSize: size);
  }
}
