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
  // _gardenDark is extracted so both garden.dark AND heritage.dark can reference it.
  // Dart const expressions cannot use member-access like `garden.dark` in const position.
  static const _gardenDark = GreenThumbColors(
    bg: Color(0xFF0E140F),
    bg2: Color(0xFF161E18),
    bg3: Color(0xFF1F2A21),
    ink: Color(0xFFEEF4E2),
    ink2: Color(0xFFC8D5B8),
    ink3: Color(0xFF8A9A7E),
    line: Color(0xFF2A3628),
    line2: Color(0xFF3A4A37),
    moss: Color(0xFFA8CC6E),
    onMoss: Color(0xFF14180F),
    sage: Color(0xFF9BBE82),
    leaf: Color(0xFFBEDC8C),
    honey: Color(0xFFE8C76B),
    clay: Color(0xFFE58A52),
    onClay: Color(0xFF14180F),
    berry: Color(0xFFD286A2),
    sky: Color(0xFF9CC0CA),
    ok: Color(0xFF3F5D3F),
    warn: Color(0xFFC4A570),
    bad: Color(0xFFB5451C),
  );

  static const GreenThumbPalette garden = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF4F1E4),
      bg2: Color(0xFFECE7D2),
      bg3: Color(0xFFDFD9BD),
      ink: Color(0xFF102015),
      ink2: Color(0xFF2E4233),
      ink3: Color(0xFF5C6E5A),
      line: Color(0xFFD2CCAE),
      line2: Color(0xFFB8B391),
      moss: Color(0xFF2F6B3A),
      onMoss: Color(0xFFF4F1E4),
      sage: Color(0xFF7FA66B),
      leaf: Color(0xFFA8CC6E),
      honey: Color(0xFFE5B84B),
      clay: Color(0xFFD86B2C),
      onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFB8466A),
      sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F),
      warn: Color(0xFFC4A570),
      bad: Color(0xFFB5451C),
    ),
    dark: _gardenDark,
  );

  static const GreenThumbPalette loam = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF6F0E2),
      bg2: Color(0xFFECE3CC),
      bg3: Color(0xFFDDD0AE),
      ink: Color(0xFF1F1A12),
      ink2: Color(0xFF4A3F2C),
      ink3: Color(0xFF7C6E55),
      line: Color(0xFFD4C5A0),
      line2: Color(0xFFBCA97E),
      moss: Color(0xFF4A7034),
      onMoss: Color(0xFFF6F0E2),
      sage: Color(0xFF97B86A),
      leaf: Color(0xFFC2D680),
      honey: Color(0xFFE0B445),
      clay: Color(0xFFC9542A),
      onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFC45577),
      sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F),
      warn: Color(0xFFC4A570),
      bad: Color(0xFFB5451C),
    ),
    dark: GreenThumbColors(
      bg: Color(0xFF12100A),
      bg2: Color(0xFF1C1810),
      bg3: Color(0xFF272218),
      ink: Color(0xFFF2EBD8),
      ink2: Color(0xFFD4C8A4),
      ink3: Color(0xFF8A7E60),
      line: Color(0xFF2E2818),
      line2: Color(0xFF423A26),
      moss: Color(0xFFB8D680),
      onMoss: Color(0xFF12100A),
      sage: Color(0xFFA3C26C),
      leaf: Color(0xFFCCE090),
      honey: Color(0xFFE8C76B),
      clay: Color(0xFFE58A52),
      onClay: Color(0xFF12100A),
      berry: Color(0xFFD286A2),
      sky: Color(0xFF9CC0CA),
      ok: Color(0xFF3F5D3F),
      warn: Color(0xFFC4A570),
      bad: Color(0xFFB5451C),
    ),
  );

  // Forest is inherently dark — light and dark are the same set.
  static const _forestColors = GreenThumbColors(
    bg: Color(0xFF0F1A12),
    bg2: Color(0xFF16241A),
    bg3: Color(0xFF1F3024),
    ink: Color(0xFFE8F0D8),
    ink2: Color(0xFFC2D2AC),
    ink3: Color(0xFF87987C),
    line: Color(0xFF2A3A2F),
    line2: Color(0xFF3D5142),
    moss: Color(0xFFB8DC7C),
    onMoss: Color(0xFF0F1A12),
    sage: Color(0xFFA8CC6E),
    leaf: Color(0xFFC8E198),
    honey: Color(0xFFF0CC68),
    clay: Color(0xFFF0935A),
    onClay: Color(0xFF0F1A12),
    berry: Color(0xFFE090A8),
    sky: Color(0xFF94BFC8),
    ok: Color(0xFF3F5D3F),
    warn: Color(0xFFC4A570),
    bad: Color(0xFFB5451C),
  );

  static const GreenThumbPalette forest = GreenThumbPalette(
    light: _forestColors,
    dark: _forestColors,
  );

  // Heritage has no dark override; dark falls back to Garden dark (_gardenDark).
  static const GreenThumbPalette heritage = GreenThumbPalette(
    light: GreenThumbColors(
      bg: Color(0xFFF0EBDB),
      bg2: Color(0xFFE4DBC2),
      bg3: Color(0xFFD3C9AC),
      ink: Color(0xFF1A1F10),
      ink2: Color(0xFF3A4128),
      ink3: Color(0xFF756E50),
      line: Color(0xFFCFC4A2),
      line2: Color(0xFFB8AC85),
      moss: Color(0xFF3D5A22),
      onMoss: Color(0xFFF0EBDB),
      sage: Color(0xFF768B4E),
      leaf: Color(0xFFA4B86E),
      honey: Color(0xFFC99B3A),
      clay: Color(0xFFB0481E),
      onClay: Color(0xFFFFF8EA),
      berry: Color(0xFFB8466A),
      sky: Color(0xFF6FA0AA),
      ok: Color(0xFF3F5D3F),
      warn: Color(0xFFC4A570),
      bad: Color(0xFFB5451C),
    ),
    dark: _gardenDark,
  );

  static GreenThumbPalette forChoice(AppPaletteChoice choice) =>
      switch (choice) {
        AppPaletteChoice.garden => garden,
        AppPaletteChoice.loam => loam,
        AppPaletteChoice.forest => forest,
        AppPaletteChoice.heritage => heritage,
      };
}
