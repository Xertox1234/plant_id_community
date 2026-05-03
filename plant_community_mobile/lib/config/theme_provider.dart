import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'theme_provider.g.dart';

/// Theme mode notifier that manages theme state.
@riverpod
class ThemeModeNotifier extends _$ThemeModeNotifier {
  static const _storage = FlutterSecureStorage();
  static const _themeModeKey = 'theme_mode';
  bool _isDisposed = false;

  @override
  ThemeMode build() {
    _isDisposed = false;
    ref.onDispose(() {
      _isDisposed = true;
    });
    _loadSavedPreference();
    return ThemeMode.system;
  }

  /// Set theme to light mode
  void setLight() {
    _setThemeMode(ThemeMode.light);
  }

  /// Set theme to dark mode
  void setDark() {
    _setThemeMode(ThemeMode.dark);
  }

  /// Set theme to system mode
  void setSystem() {
    _setThemeMode(ThemeMode.system);
  }

  /// Toggle between light and dark mode
  void toggle(Brightness brightness) {
    if (brightness == Brightness.light) {
      setDark();
    } else {
      setLight();
    }
  }

  Future<void> _loadSavedPreference() async {
    try {
      final savedValue = await _storage.read(key: _themeModeKey);
      final savedMode = _themeModeFromStorageValue(savedValue);
      if (!_isDisposed && savedMode != null) {
        state = savedMode;
      }
    } catch (error) {
      debugPrint('[THEME] Failed to load saved theme preference: $error');
    }
  }

  void _setThemeMode(ThemeMode mode) {
    state = mode;
    unawaited(_saveThemeMode(mode));
  }

  Future<void> _saveThemeMode(ThemeMode mode) async {
    try {
      await _storage.write(key: _themeModeKey, value: mode.name);
    } catch (error) {
      debugPrint('[THEME] Failed to save theme preference: $error');
    }
  }

  ThemeMode? _themeModeFromStorageValue(String? value) {
    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      case 'system':
        return ThemeMode.system;
      default:
        return null;
    }
  }
}
