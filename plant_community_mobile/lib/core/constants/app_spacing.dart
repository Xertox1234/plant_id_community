/// App spacing constants extracted from design system.
/// Based on 0.25rem (4px) unit.
class AppSpacing {
  AppSpacing._(); // Private constructor to prevent instantiation

  // ============================================
  // SPACING SCALE
  // ============================================
  static const double xs = 4.0; // 0.25rem
  static const double sm = 8.0; // 0.5rem
  static const double md = 16.0; // 1rem
  static const double lg = 24.0; // 1.5rem
  static const double xl = 32.0; // 2rem
  static const double xl2 = 48.0; // 3rem
  static const double xl3 = 64.0; // 4rem

  // ============================================
  // BORDER RADIUS
  // ============================================
  static const double radiusSM = 4.0; // Small elements
  static const double radiusMD = 8.0; // Default radius
  static const double radiusLG = 12.0; // Cards, modals
  static const double radiusXL = 16.0; // Large components
  static const double radiusFull = 9999.0; // Circular (pill buttons)

  // ============================================
  // COMMON PADDING/MARGIN VALUES
  // ============================================
  /// Page padding (horizontal)
  static const double pagePadding = md;

  /// Section spacing (vertical)
  static const double sectionSpacing = xl;

  /// Card padding
  static const double cardPadding = md;

  /// Button padding (horizontal)
  static const double buttonPaddingH = lg;

  /// Button padding (vertical)
  static const double buttonPaddingV = sm;

  /// Icon size (small)
  static const double iconSM = 16.0;

  /// Icon size (medium)
  static const double iconMD = 20.0;

  /// Icon size (large)
  static const double iconLG = 48.0;

  // ============================================
  // ELEVATION (Box Shadow)
  // ============================================
  static const double elevationSM = 2.0;
  static const double elevationMD = 4.0;
  static const double elevationLG = 8.0;
  static const double elevationXL = 16.0;
}
