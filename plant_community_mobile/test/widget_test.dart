// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:plant_community_mobile/main.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';

void main() {
  testWidgets('App launches and shows splash screen', (
    WidgetTester tester,
  ) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authServiceProvider.overrideWithValue(const AuthState())],
        child: const MyApp(),
      ),
    );

    // Let animations start
    await tester.pump(const Duration(milliseconds: 100));

    // Verify the splash shows the canonical product branding.
    expect(find.text('Houseplant MD'), findsOneWidget);
    // CanopyLabel uppercases the canonical tagline.
    expect(find.text('THE PLANT CLINIC'), findsOneWidget);
    // The leaf glyph now comes from the product mark, not a bespoke disc.
    expect(find.byType(BrandMark), findsOneWidget);

    // Clean up timers
    await tester.pumpAndSettle(const Duration(seconds: 3));
  });
}
