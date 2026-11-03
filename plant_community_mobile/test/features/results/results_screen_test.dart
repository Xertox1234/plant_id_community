import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/results/results_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/scan/scan_job_api.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

ThemeData _theme() => AppTheme.build(Brightness.light, AppDensity.cozy);

Widget _wrap(Widget child) => MaterialApp(theme: _theme(), home: child);

final _mockDate = DateTime(2024, 1, 15);

Plant _mockPlant() => Plant(
  id: 'test-123',
  name: 'Test Plant',
  scientificName: 'Testus plantus',
  description: 'A test plant description.',
  care: ['Water weekly', 'Bright indirect light'],
  timestamp: _mockDate,
);

void main() {
  testWidgets('shows Identified badge', (tester) async {
    await tester.pumpWidget(_wrap(ResultsScreen(plant: _mockPlant())));
    expect(find.text('Identified'), findsOneWidget);
    expect(find.byIcon(LucideIcons.circleCheck), findsOneWidget);
  });

  testWidgets('shows care instructions', (tester) async {
    await tester.pumpWidget(_wrap(ResultsScreen(plant: _mockPlant())));
    expect(find.text('Care Instructions'), findsOneWidget);
    expect(find.text('Water weekly'), findsOneWidget);
    expect(find.text('Bright indirect light'), findsOneWidget);
  });

  // Todo 662: the backend sends no care until it has plant-specific advice,
  // and an empty card titled "Care Instructions" would still read as advice.
  testWidgets('hides the care card when there is no care', (tester) async {
    final plant = _mockPlant().copyWith(care: const []);
    await tester.pumpWidget(_wrap(ResultsScreen(plant: plant)));
    expect(find.text('Care Instructions'), findsNothing);
    expect(find.text('Test Plant'), findsOneWidget);
  });

  testWidgets('no crash on pump', (tester) async {
    await tester.pumpWidget(_wrap(ResultsScreen(plant: _mockPlant())));
    expect(tester.takeException(), isNull);
  });

  testWidgets('results shows found diagnosis with percent', (tester) async {
    await tester.pumpWidget(
      _wrap(
        ResultsScreen(
          plant: _mockPlant(),
          diagnosis: const ScanDiagnosis(
            state: 'found',
            name: 'Root rot',
            probability: 0.72,
            description: 'Soggy soil is killing the roots.',
          ),
        ),
      ),
    );
    expect(find.text('Root rot'), findsOneWidget);
    expect(find.text('72%'), findsOneWidget);
    expect(find.text('Soggy soil is killing the roots.'), findsOneWidget);
  });

  testWidgets('results shows Looks healthy', (tester) async {
    await tester.pumpWidget(
      _wrap(
        ResultsScreen(
          plant: _mockPlant(),
          diagnosis: const ScanDiagnosis(state: 'healthy'),
        ),
      ),
    );
    expect(find.text('Looks healthy'), findsOneWidget);
  });

  testWidgets('results shows degraded copy', (tester) async {
    const copy =
        "We named your plant but couldn't check its health. "
        "Your check wasn't used.";
    await tester.pumpWidget(
      _wrap(ResultsScreen(plant: _mockPlant(), degraded: true)),
    );
    expect(find.text(copy), findsOneWidget);

    await tester.pumpWidget(
      _wrap(
        ResultsScreen(
          plant: _mockPlant(),
          diagnosis: const ScanDiagnosis(state: 'unavailable'),
        ),
      ),
    );
    expect(find.text(copy), findsOneWidget);
  });

  testWidgets('results shows identification confidence', (tester) async {
    await tester.pumpWidget(
      _wrap(ResultsScreen(plant: _mockPlant(), confidence: 0.91)),
    );
    expect(find.text('91% match'), findsOneWidget);
  });

  testWidgets('results shows degraded copy for an unknown state', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ResultsScreen(
          plant: _mockPlant(),
          diagnosis: const ScanDiagnosis(state: 'brand_new_state'),
        ),
      ),
    );
    expect(find.text(ResultsScreen.degradedCopy), findsOneWidget);
    expect(find.text('Looks healthy'), findsNothing);
  });

  testWidgets('results found with no name shows no empty title', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ResultsScreen(
          plant: _mockPlant(),
          diagnosis: const ScanDiagnosis(
            state: 'found',
            probability: 0.5,
            description: 'x',
          ),
        ),
      ),
    );
    expect(find.text(ResultsScreen.degradedCopy), findsOneWidget);
    expect(find.textContaining('50%'), findsNothing);
    expect(find.text('Looks healthy'), findsNothing);
  });
}
