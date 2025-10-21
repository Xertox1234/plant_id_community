import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Theme mode notifier that manages theme state.
class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.system) {
    // TODO: Load saved preference from local storage
  }

  /// Set theme to light mode
  void setLight() {
    state = ThemeMode.light;
    // TODO: Persist to local storage
  }

  /// Set theme to dark mode
  void setDark() {
    state = ThemeMode.dark;
    // TODO: Persist to local storage
  }

  /// Set theme to system mode
  void setSystem() {
    state = ThemeMode.system;
    // TODO: Persist to local storage
  }

  /// Toggle between light and dark mode
  void toggle(Brightness brightness) {
    if (brightness == Brightness.light) {
      setDark();
    } else {
      setLight();
    }
  }
}

/// Provider for theme mode state
final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>(
  (ref) => ThemeModeNotifier(),
);
