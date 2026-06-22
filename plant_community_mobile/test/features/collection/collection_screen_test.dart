import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/collection/collection_screen.dart';
import 'package:plant_community_mobile/models/plant.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/firestore_service.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
  home: child,
);

Plant _plant(String id, String name) => Plant(
  id: id,
  name: name,
  scientificName: '$name scientificus',
  description: 'desc',
  care: const [],
  timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
);

/// Pump [widget] on a portrait phone-sized surface and let the stream provider
/// deliver its first emission (loading -> data). The default 800x600 surface
/// makes the aspect-0.8 grid cells very tall and pushes content out of the
/// findable region.
Future<void> _pump(WidgetTester tester, Widget widget) async {
  await tester.binding.setSurfaceSize(const Size(400, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(widget);
  await tester.pump();
  await tester.pump();
}

void main() {
  const uid = 'test-uid';

  testWidgets('signed-out users see a sign-in prompt', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [currentUserIdProvider.overrideWithValue(null)],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Sign in to see your collection'), findsOneWidget);
  });

  testWidgets('renders identified plants from the stream', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera'), _plant('2', 'Peace Lily')],
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('2 PLANTS IDENTIFIED'), findsOneWidget);
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('Peace Lily'), findsOneWidget);
    expect(find.text('Identify a plant'), findsOneWidget); // the "add" tile
  });

  testWidgets('shows an empty state when the collection is empty', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          plantsStreamProvider(
            uid,
          ).overrideWith((ref) => Stream.value(PlantsSnapshot.empty)),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('No plants yet'), findsOneWidget);
    expect(find.text('0 PLANTS IDENTIFIED'), findsOneWidget);
  });

  testWidgets('shows an Offline badge when data is from cache', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera')],
                isFromCache: true,
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Offline'), findsOneWidget);
  });

  testWidgets('shows a Syncing badge when writes are pending', (tester) async {
    await _pump(
      tester,
      ProviderScope(
        overrides: [
          currentUserIdProvider.overrideWithValue(uid),
          plantsStreamProvider(uid).overrideWith(
            (ref) => Stream.value(
              PlantsSnapshot(
                plants: [_plant('1', 'Monstera')],
                hasPendingWrites: true,
              ),
            ),
          ),
        ],
        child: _wrap(const CollectionScreen()),
      ),
    );

    expect(find.text('Syncing…'), findsOneWidget);
  });
}
