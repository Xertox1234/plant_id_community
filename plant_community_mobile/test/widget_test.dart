// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:plant_community_mobile/main.dart';

void main() {
  testWidgets('App launches and shows splash screen', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ProviderScope(child: MyApp()));

    // Let animations start
    await tester.pump(const Duration(milliseconds: 100));

    // Verify that the splash screen is shown with PlantID branding.
    expect(find.text('PlantID'), findsOneWidget);
    expect(find.text('Discover Nature\'s Secrets'), findsOneWidget);
    expect(find.byIcon(Icons.eco), findsOneWidget);

    // Clean up timers
    await tester.pumpAndSettle(const Duration(seconds: 3));
  });
}
