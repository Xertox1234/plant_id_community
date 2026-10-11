import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';

import 'support/garden_test_support.dart';

/// A plant row, as `PlantListSerializer` sends it.
Map<String, dynamic> _plant(int i) => {
  'uuid': 'plant-$i',
  'garden_bed': null,
  'garden_bed_name': null,
  'common_name': 'Plant $i',
  'planted_date': '2026-09-01',
  'is_active': true,
};

/// [pages] pages of one plant each; the last one links to [after] (null
/// ends the list).
RecordingApiService _pagedPlants(int pages, {String? after}) {
  String url(int page) => 'http://test/api/v1/calendar/api/plants/?page=$page';
  final responses = <String, Object?>{};
  for (var page = 1; page <= pages; page++) {
    final key = page == 1 ? 'GET /calendar/api/plants/' : 'GET ${url(page)}';
    responses[key] = {
      'next': page < pages ? url(page + 1) : after,
      'results': [_plant(page)],
    };
  }
  return RecordingApiService(responses);
}

void main() {
  group('the page cap (todo 570, owner decision 2026-10-11)', () {
    test('a list that ends within the cap is not truncated', () async {
      final api = _pagedPlants(gardenMaxPages);

      final plants = await HttpGardenApi(api).fetchPlants();

      expect(plants.items, hasLength(gardenMaxPages));
      expect(plants.truncated, isFalse);
    });

    test('a list with pages past the cap stops there and says so', () async {
      final api = _pagedPlants(
        gardenMaxPages,
        after: 'http://test/api/v1/calendar/api/plants/?page=11',
      );

      final plants = await HttpGardenApi(api).fetchPlants();

      expect(plants.items, hasLength(gardenMaxPages));
      expect(plants.truncated, isTrue);
      expect(api.requests, hasLength(gardenMaxPages)); // page 11 never read
    });
  });
}
