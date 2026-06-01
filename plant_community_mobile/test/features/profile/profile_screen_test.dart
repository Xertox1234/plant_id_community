import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/profile/profile_screen.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
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

Widget _wrap(AppDensity density) => ProviderScope(
  overrides: [
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
}
