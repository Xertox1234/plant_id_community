import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/profile/profile_screen.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

final _mockDate = DateTime(2024, 1, 15);

UserProfile _mockProfile() => UserProfile(
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  firstName: 'Test',
  lastName: 'User',
  bio: 'A test gardener.',
  location: 'Test City',
  dateJoined: _mockDate,
);

/// Fake notifier that resolves to a fixed profile without hitting the backend,
/// so the screen renders its `data` branch (the `SingleChildScrollView`).
class _FakeUserProfileService extends UserProfileService {
  @override
  Future<UserProfile?> build() async => _mockProfile();
}

/// ProfileScreen reads auth BEFORE the profile provider (todo 384), so every
/// test here needs an auth override: the real `AuthService.build()` reaches
/// `FirebaseAuth.instance` and throws `[core/no-app]` under `flutter test`.
/// `isAuthenticated` is `jwtToken != null`, so a token is what "signed in"
/// means -- not a Firebase user.
class _FakeAuthService extends AuthService {
  _FakeAuthService({required this.loggedIn});
  final bool loggedIn;

  @override
  AuthState build() =>
      loggedIn ? const AuthState(jwtToken: 'test-jwt') : const AuthState();
}

Widget _wrap(AppDensity density, {bool loggedIn = true}) => ProviderScope(
  overrides: [
    authServiceProvider.overrideWith(
      () => _FakeAuthService(loggedIn: loggedIn),
    ),
    userProfileServiceProvider.overrideWith(_FakeUserProfileService.new),
  ],
  child: MaterialApp(
    theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, density),
    home: const ProfileScreen(),
  ),
);

void main() {
  testWidgets('scroll padding uses ext.padScreen (compact = 14)', (
    tester,
  ) async {
    // compact.padScreen == 14, which differs from BOTH the old hardcoded 16
    // AND the fallback's 18 — so this proves the real extension is wired and
    // the padding is density-responsive (not silently falling back).
    await tester.pumpWidget(_wrap(AppDensity.compact));
    await tester.pumpAndSettle();

    final scrollView = tester.widget<SingleChildScrollView>(
      find.byType(SingleChildScrollView),
    );
    final padding = scrollView.padding as EdgeInsets?;
    expect(padding?.left, equals(14.0));
  });

  testWidgets('renders profile data without crashing', (tester) async {
    await tester.pumpWidget(_wrap(AppDensity.cozy));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Test User'), findsOneWidget);
  });

  testWidgets('signed out it offers sign-in instead of a failed fetch', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(AppDensity.cozy, loggedIn: false));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);

    // The regression this guards: signed out, the screen used to watch
    // userProfileServiceProvider, take a 401, and render "Failed to load
    // profile" over the raw exception plus a Retry that could never succeed --
    // on the one tab that is meant to offer sign-in (todo 384).
    expect(find.text('Failed to load profile'), findsNothing);
    expect(find.widgetWithText(ElevatedButton, 'Retry'), findsNothing);

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(
      find.widgetWithText(OutlinedButton, 'Create an account'),
      findsOneWidget,
    );
  });
}
