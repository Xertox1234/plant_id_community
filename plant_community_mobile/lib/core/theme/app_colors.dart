import 'package:flutter/material.dart';

/// App color palette extracted from design system.
/// Colors use Flutter's Color class with ARGB hex values.
class AppColors {
  AppColors._(); // Private constructor to prevent instantiation

  // ============================================
  // BRAND COLORS - GREEN PALETTE
  // ============================================
  /// Primary brand color representing nature and plant life
  static const Color green50 = Color(0xFFF7FDF7);
  static const Color green100 = Color(0xFFEEFBEE);
  static const Color green200 = Color(0xFFDDF7DD);
  static const Color green400 = Color(0xFFA8E6A8);
  static const Color green500 = Color(0xFF7FD97F); // Base green
  static const Color green600 = Color(0xFF4CAF50); // Primary CTA color
  static const Color green700 = Color(0xFF388E3C); // Dark mode primary
  static const Color green800 = Color(0xFF2E7D32);
  static const Color green900 = Color(0xFF1B5E20);
  static const Color green950 = Color(0xFF0D2F10); // Darkest shade

  // ============================================
  // BRAND COLORS - EMERALD PALETTE
  // ============================================
  /// Complementary emerald tones for gradients and accents
  static const Color emerald100 = Color(0xFFECFDF5);
  static const Color emerald400 = Color(0xFF6EE7B7);
  static const Color emerald600 = Color(0xFF059669); // Gradient partner
  static const Color emerald700 = Color(0xFF047857);
  static const Color emerald800 = Color(0xFF065F46);
  static const Color emerald900 = Color(0xFF064E3B);
  static const Color emerald950 = Color(0xFF022C22);

  // ============================================
  // ACCENT COLORS
  // ============================================
  /// Care instructions color
  static const Color blue500 = Color(0xFF3B82F6);
  static const Color blue600 = Color(0xFF2563EB);

  /// Community features color
  static const Color purple500 = Color(0xFFA855F7);
  static const Color purple600 = Color(0xFF9333EA);

  /// Tracking/history color
  static const Color amber500 = Color(0xFFF59E0B);
  static const Color amber600 = Color(0xFFD97706);

  // ============================================
  // LIGHT THEME COLORS
  // ============================================
  static const Color lightBackground = Color(0xFFFFFFFF);
  static const Color lightForeground = Color(0xFF1A1A1A);
  static const Color lightCard = Color(0xFFFFFFFF);
  static const Color lightCardForeground = Color(0xFF1A1A1A);
  static const Color lightPrimary = Color(0xFF030213);
  static const Color lightPrimaryForeground = Color(0xFFFFFFFF);
  static const Color lightSecondary = Color(0xFFF5F5F7);
  static const Color lightSecondaryForeground = Color(0xFF030213);
  static const Color lightMuted = Color(0xFFECECF0);
  static const Color lightMutedForeground = Color(0xFF717182);
  static const Color lightAccent = Color(0xFFE9EBEF);
  static const Color lightAccentForeground = Color(0xFF030213);
  static const Color lightDestructive = Color(0xFFD4183D);
  static const Color lightDestructiveForeground = Color(0xFFFFFFFF);
  static const Color lightBorder = Color(0x1A000000); // rgba(0, 0, 0, 0.1)
  static const Color lightInputBackground = Color(0xFFF3F3F5);
  static const Color lightSwitchBackground = Color(0xFFCBCED4);
  static const Color lightRing = Color(0xFFB5B5B5);

  // ============================================
  // DARK THEME COLORS
  // ============================================
  static const Color darkBackground = Color(0xFF1A1A1A);
  static const Color darkForeground = Color(0xFFFAFAFA);
  static const Color darkCard = Color(0xFF1A1A1A);
  static const Color darkCardForeground = Color(0xFFFAFAFA);
  static const Color darkPrimary = Color(0xFFFAFAFA);
  static const Color darkPrimaryForeground = Color(0xFF2A2A2A);
  static const Color darkSecondary = Color(0xFF3A3A3A);
  static const Color darkSecondaryForeground = Color(0xFFFAFAFA);
  static const Color darkMuted = Color(0xFF3A3A3A);
  static const Color darkMutedForeground = Color(0xFFB5B5B5);
  static const Color darkAccent = Color(0xFF3A3A3A);
  static const Color darkAccentForeground = Color(0xFFFAFAFA);
  static const Color darkDestructive = Color(0xFFEF4444);
  static const Color darkDestructiveForeground = Color(0xFFFCA5A5);
  static const Color darkBorder = Color(0xFF3A3A3A);
  static const Color darkInput = Color(0xFF3A3A3A);
  static const Color darkRing = Color(0xFF6B6B6B);

  // ============================================
  // GRADIENTS
  // ============================================
  /// Splash screen background gradient (light)
  static const List<Color> splashGradientLight = [green50, emerald100];

  /// Splash screen background gradient (dark)
  static const List<Color> splashGradientDark = [green950, emerald950];

  /// Icon/button gradient
  static const List<Color> iconGradient = [green500, emerald600];

  /// Text gradient (light)
  static const List<Color> textGradientLight = [green700, emerald700];

  /// Text gradient (dark)
  static const List<Color> textGradientDark = [green400, emerald400];

  /// Hero background gradient (light)
  static const List<Color> heroGradientLight = [green100, emerald100];

  /// Hero background gradient (dark)
  static List<Color> get heroGradientDark => [
        green900.withOpacity(0.3),
        emerald900.withOpacity(0.3),
      ];

  // ============================================
  // HELPER METHODS
  // ============================================
  /// Get color by brightness
  static Color getBackgroundColor(Brightness brightness) {
    return brightness == Brightness.light ? lightBackground : darkBackground;
  }

  static Color getForegroundColor(Brightness brightness) {
    return brightness == Brightness.light ? lightForeground : darkForeground;
  }

  static Color getPrimaryColor(Brightness brightness) {
    return brightness == Brightness.light ? lightPrimary : darkPrimary;
  }

  static Color getCardColor(Brightness brightness) {
    return brightness == Brightness.light ? lightCard : darkCard;
  }

  static Color getBorderColor(Brightness brightness) {
    return brightness == Brightness.light ? lightBorder : darkBorder;
  }
}
