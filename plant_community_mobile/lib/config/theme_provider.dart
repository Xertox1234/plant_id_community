import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'theme_provider.g.dart';

/// Theme mode notifier that manages theme state.
@riverpod
class ThemeModeNotifier extends _$ThemeModeNotifier {
  @override
  ThemeMode build() {
    // TODO: Load saved preference from local storage
    return ThemeMode.system;
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
