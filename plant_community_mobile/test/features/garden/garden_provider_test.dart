import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/garden/models/models.dart';
import 'package:plant_community_mobile/features/garden/providers/garden_provider.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import 'support/garden_test_support.dart';

void main() {
  group('gardenRetry (todo 570 #2)', () {
    test('a 4xx fails at once: retrying cannot change it', () {
      for (final status in [400, 401, 403, 404, 429, 499]) {
        expect(
          gardenRetry(0, ApiException('no', statusCode: status)),
          isNull,
          reason: 'status $status',
        );
      }
    });

    test('a 5xx or a network error keeps the default backoff', () {
      for (final error in <Object>[
        ApiException('down', statusCode: 500),
        ApiException('offline'),
        Exception('socket closed'),
      ]) {
        final delay = gardenRetry(0, error);
        expect(
          delay,
          ProviderContainer.defaultRetry(0, error),
          reason: '$error',
        );
        expect(delay, isNotNull, reason: '$error');
      }
    });
  });

  group('garden', () {
    test('reports a truncated list (todo 570 #8)', () async {
      final api = FakeGardenApi(
        plants: [const GardenPlant(id: 'p1', commonName: 'Fern')],
      )..truncated = true;
      final container = ProviderContainer(
        overrides: [gardenApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);

      final data = await container.read(gardenProvider.future);

      expect(data.truncated, isTrue);
      expect(data.plants, hasLength(1));
    });

    test('a complete list is not truncated', () async {
      final container = ProviderContainer(
        overrides: [gardenApiProvider.overrideWithValue(FakeGardenApi())],
      );
      addTearDown(container.dispose);

      expect((await container.read(gardenProvider.future)).truncated, isFalse);
    });
  });
}
