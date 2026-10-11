import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../services/api_service.dart';
import '../models/models.dart';

/// HTTP contract for the garden: the houseplant core of
/// `apps/garden_calendar`, mounted at `/api/v1/calendar/api/` (todo 386).
///
/// An interface so tests override [gardenApiProvider] with a fake, the same
/// convention as `BlogApi` and `DiagnoseApi`.
abstract class GardenApi {
  /// The signed-in user's active plants, newest planting first.
  Future<List<GardenPlant>> fetchPlants();

  /// The user's pending care tasks (neither completed nor skipped), soonest
  /// first.
  Future<List<CareTask>> fetchPendingTasks();

  /// Create a plant with no bed. [plantedDate] is a calendar date.
  Future<GardenPlant> createPlant({
    required String commonName,
    required DateTime plantedDate,
  });

  /// Schedule a care task for [plantId]. A [recurrenceDays] makes it recur:
  /// completing it creates the next one on the server.
  Future<void> createTask({
    required String plantId,
    required String taskType,
    required String title,
    required DateTime scheduledDate,
    int? recurrenceDays,
  });

  /// Mark [task] done, then record it in the plant's care log. Returns
  /// whether the log entry was saved: the task IS complete either way, so a
  /// failed log must not read as a failed completion (a retry would 400 on
  /// "already completed").
  Future<bool> completeTask(CareTask task);

  /// Skip [task]. A recurring task still schedules its next occurrence.
  Future<void> skipTask(CareTask task);
}

/// Pages followed per list. The API pages at 20 (`PAGE_SIZE`); a houseplant
/// collection past 200 plants or pending tasks is not a case worth an
/// unbounded loop.
const int gardenMaxPages = 10;

class HttpGardenApi implements GardenApi {
  HttpGardenApi(this._api);

  final ApiService _api;

  static const _base = '/calendar/api';

  /// Follows DRF `PageNumberPagination`'s `next` links. Dio uses an
  /// absolute `next` URL as-is.
  Future<List<Map<String, dynamic>>> _all(
    String path,
    Map<String, dynamic> query,
  ) async {
    final rows = <Map<String, dynamic>>[];
    String? url = path;
    Map<String, dynamic>? params = query;
    for (var page = 0; url != null && page < gardenMaxPages; page++) {
      final resp = await _api.get(url, queryParameters: params);
      final body = resp.data as Map<String, dynamic>;
      rows.addAll((body['results'] as List).cast<Map<String, dynamic>>());
      url = body['next'] as String?;
      params = null; // `next` already carries the query.
    }
    return rows;
  }

  @override
  Future<List<GardenPlant>> fetchPlants() async {
    final rows = await _all('$_base/plants/', {'is_active': 'true'});
    return rows.map(GardenPlant.fromJson).toList();
  }

  @override
  Future<List<CareTask>> fetchPendingTasks() async {
    final rows = await _all('$_base/care-tasks/', {
      'completed': 'false',
      'skipped': 'false',
      'ordering': 'scheduled_date',
    });
    return rows.map(CareTask.fromJson).toList();
  }

  @override
  Future<GardenPlant> createPlant({
    required String commonName,
    required DateTime plantedDate,
  }) async {
    final resp = await _api.post(
      '$_base/plants/',
      data: {'common_name': commonName, 'planted_date': _date(plantedDate)},
    );
    return GardenPlant.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<void> createTask({
    required String plantId,
    required String taskType,
    required String title,
    required DateTime scheduledDate,
    int? recurrenceDays,
  }) async {
    await _api.post(
      '$_base/care-tasks/',
      data: {
        'plant': plantId,
        'task_type': taskType,
        'title': title,
        // UTC with an offset: the field is a DateTimeField, and a naive
        // local time would be read in the server's zone.
        'scheduled_date': scheduledDate.toUtc().toIso8601String(),
        'is_recurring': recurrenceDays != null,
        'recurrence_interval_days': ?recurrenceDays,
      },
    );
  }

  @override
  Future<bool> completeTask(CareTask task) async {
    await _api.post('$_base/care-tasks/${task.id}/complete/');
    // The task endpoint does not log care; the care log is what "when did I
    // last water it" reads from.
    try {
      await _api.post(
        '$_base/care-logs/',
        data: {
          'plant': task.plant,
          'activity_type': careLogActivityFor(task.taskType),
          'notes': task.title,
        },
      );
      return true;
    } on ApiException {
      return false;
    }
  }

  @override
  Future<void> skipTask(CareTask task) async {
    await _api.post('$_base/care-tasks/${task.id}/skip/');
  }
}

String _date(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-'
    '${d.month.toString().padLeft(2, '0')}-'
    '${d.day.toString().padLeft(2, '0')}';

final gardenApiProvider = Provider<GardenApi>(
  (ref) => HttpGardenApi(ref.watch(apiServiceProvider)),
);
