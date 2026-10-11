import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/garden/garden_screen.dart';
import 'package:plant_community_mobile/features/garden/models/models.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import 'support/garden_test_support.dart';

/// `PlantListSerializer`'s fields, as the API sends them for a plant with
/// no bed (todo 410 made the bed optional; todo 457 item 8).
Map<String, dynamic> _bedlessPlantJson() => {
  'uuid': 'a1b2c3d4-0000-4000-8000-000000000001',
  'garden_bed': null,
  'garden_bed_name': null,
  'common_name': 'Monstera',
  'variety': '',
  'health_status': 'healthy',
  'health_status_display': 'Healthy',
  'growth_stage': 'vegetative',
  'growth_stage_display': 'Vegetative Growth',
  'planted_date': '2026-09-01',
  'primary_image': null,
  'days_since_planted': 39,
  'age_display': '1 month',
  'is_active': true,
};

/// `CareTaskListSerializer`'s fields.
Map<String, dynamic> _taskJson() => {
  'uuid': 'b1b2c3d4-0000-4000-8000-000000000001',
  'plant': 'a1b2c3d4-0000-4000-8000-000000000001',
  'plant_name': 'Monstera',
  'task_type': 'watering',
  'task_type_display': 'Watering',
  'title': 'Water Monstera',
  'priority': 'medium',
  'priority_display': 'Medium',
  'scheduled_date': '2026-10-12T09:00:00Z',
  'completed': false,
  'skipped': false,
  'is_recurring': true,
  'is_overdue': false,
};

/// Records requests and answers them from [responses], keyed by
/// `METHOD path`. A missing key throws a 500 [ApiException].
class _RecordingApiService extends ApiService {
  _RecordingApiService(this.responses) : super(baseUrl: 'http://test/api/v1');

  final Map<String, Object?> responses;
  final List<(String, String, Object?, Map<String, dynamic>?)> requests = [];

  Response<dynamic> _answer(String method, String path) {
    final key = '$method $path';
    if (!responses.containsKey(key)) {
      throw ApiException('no fake for $key', statusCode: 500);
    }
    return Response(
      requestOptions: RequestOptions(path: path),
      data: responses[key],
      statusCode: 200,
    );
  }

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    requests.add(('GET', path, null, queryParameters));
    return _answer('GET', path);
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    requests.add(('POST', path, data, queryParameters));
    return _answer('POST', path);
  }
}

CareTask _task({
  String id = 't1',
  String plant = 'p1',
  String title = 'Water Fern',
  bool overdue = false,
  DateTime? when,
}) => CareTask(
  id: id,
  plant: plant,
  plantName: 'Fern',
  title: title,
  taskType: 'watering',
  taskTypeDisplay: 'Watering',
  scheduledDate: when ?? DateTime.now().add(const Duration(days: 3)),
  isOverdue: overdue,
);

Future<FakeGardenApi> _pump(WidgetTester tester, FakeGardenApi api) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [gardenApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        theme: AppTheme.build(Brightness.light, AppDensity.cozy),
        home: const GardenScreen(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return api;
}

void main() {
  group('models', () {
    test('a bedless plant parses: gardenBed is null (todo 457 item 8)', () {
      final plant = GardenPlant.fromJson(_bedlessPlantJson());
      expect(plant.gardenBed, isNull);
      expect(plant.gardenBedName, isNull);
      expect(plant.id, 'a1b2c3d4-0000-4000-8000-000000000001');
      expect(plant.commonName, 'Monstera');
      expect(plant.plantedDate, DateTime(2026, 9, 1));
    });

    test('a plant in a bed keeps the bed UUID', () {
      final plant = GardenPlant.fromJson({
        ..._bedlessPlantJson(),
        'garden_bed': 'c1b2c3d4-0000-4000-8000-000000000009',
        'garden_bed_name': 'Windowsill',
      });
      expect(plant.gardenBed, 'c1b2c3d4-0000-4000-8000-000000000009');
      expect(plant.gardenBedName, 'Windowsill');
    });

    test('a care task parses from the list payload', () {
      final task = CareTask.fromJson(_taskJson());
      expect(task.plant, 'a1b2c3d4-0000-4000-8000-000000000001');
      expect(task.taskType, 'watering');
      expect(task.isRecurring, isTrue);
      expect(task.isPending, isTrue);
      expect(task.scheduledDate.isUtc, isFalse);
      expect(task.scheduledDate.toUtc(), DateTime.utc(2026, 10, 12, 9));
    });

    test('an unknown task type survives (the server has 14)', () {
      final task = CareTask.fromJson({..._taskJson(), 'task_type': 'mulching'});
      expect(task.taskType, 'mulching');
      expect(careLogActivityFor('mulching'), 'other');
      expect(careLogActivityFor('watering'), 'watering');
    });
  });

  group('HttpGardenApi', () {
    test(
      'fetchPlants follows DRF pagination and asks for active plants',
      () async {
        final api = _RecordingApiService({
          'GET /calendar/api/plants/': {
            'count': 2,
            'next': 'http://test/api/v1/calendar/api/plants/?page=2',
            'results': [_bedlessPlantJson()],
          },
          'GET http://test/api/v1/calendar/api/plants/?page=2': {
            'count': 2,
            'next': null,
            'results': [
              {..._bedlessPlantJson(), 'uuid': 'second', 'common_name': 'Fern'},
            ],
          },
        });
        final plants = await HttpGardenApi(api).fetchPlants();
        expect(plants.map((p) => p.commonName), ['Monstera', 'Fern']);
        expect(api.requests.first.$4, {'is_active': 'true'});
        expect(api.requests[1].$4, isNull);
      },
    );

    test('fetchPendingTasks filters out completed and skipped tasks', () async {
      final api = _RecordingApiService({
        'GET /calendar/api/care-tasks/': {
          'count': 1,
          'next': null,
          'results': [_taskJson()],
        },
      });
      final tasks = await HttpGardenApi(api).fetchPendingTasks();
      expect(tasks, hasLength(1));
      expect(api.requests.single.$4, {
        'completed': 'false',
        'skipped': 'false',
        'ordering': 'scheduled_date',
      });
    });

    test('createPlant sends a bedless plant with a calendar date', () async {
      final api = _RecordingApiService({
        'POST /calendar/api/plants/': _bedlessPlantJson(),
      });
      await HttpGardenApi(
        api,
      ).createPlant(commonName: 'Monstera', plantedDate: DateTime(2026, 3, 7));
      expect(api.requests.single.$3, {
        'common_name': 'Monstera',
        'planted_date': '2026-03-07',
      });
    });

    test('createTask sends a UTC due time and the recurrence', () async {
      final api = _RecordingApiService({'POST /calendar/api/care-tasks/': {}});
      final when = DateTime(2026, 10, 12, 9);
      await HttpGardenApi(api).createTask(
        plantId: 'p1',
        taskType: 'watering',
        title: 'Watering Fern',
        scheduledDate: when,
        recurrenceDays: 7,
      );
      expect(api.requests.single.$3, {
        'plant': 'p1',
        'task_type': 'watering',
        'title': 'Watering Fern',
        'scheduled_date': when.toUtc().toIso8601String(),
        'is_recurring': true,
        'recurrence_interval_days': 7,
      });
    });

    test('a one-off task is not recurring and sends no interval', () async {
      final api = _RecordingApiService({'POST /calendar/api/care-tasks/': {}});
      await HttpGardenApi(api).createTask(
        plantId: 'p1',
        taskType: 'pruning',
        title: 'Pruning Fern',
        scheduledDate: DateTime(2026, 10, 12, 9),
      );
      final body = api.requests.single.$3! as Map;
      expect(body['is_recurring'], isFalse);
      expect(body.containsKey('recurrence_interval_days'), isFalse);
    });

    test('completeTask completes, then writes the care log', () async {
      final api = _RecordingApiService({
        'POST /calendar/api/care-tasks/t1/complete/': {},
        'POST /calendar/api/care-logs/': {},
      });
      final logged = await HttpGardenApi(api).completeTask(_task());
      expect(logged, isTrue);
      expect(api.requests.map((r) => r.$2), [
        '/calendar/api/care-tasks/t1/complete/',
        '/calendar/api/care-logs/',
      ]);
      expect(api.requests.last.$3, {
        'plant': 'p1',
        'activity_type': 'watering',
        'notes': 'Water Fern',
      });
    });

    test('a failed care-log write still reports the task complete', () async {
      final api = _RecordingApiService({
        'POST /calendar/api/care-tasks/t1/complete/': {},
      });
      expect(await HttpGardenApi(api).completeTask(_task()), isFalse);
    });

    test('a failed completion throws and writes no care log', () async {
      final api = _RecordingApiService({});
      await expectLater(
        HttpGardenApi(api).completeTask(_task()),
        throwsA(isA<ApiException>()),
      );
      expect(api.requests, hasLength(1));
    });
  });

  group('GardenScreen', () {
    testWidgets('shows due tasks and plants', (tester) async {
      await _pump(
        tester,
        FakeGardenApi(
          plants: [const GardenPlant(id: 'p1', commonName: 'Fern')],
          tasks: [
            _task(
              overdue: true,
              when: DateTime.now().subtract(const Duration(days: 4)),
            ),
          ],
        ),
      );
      expect(find.text('DUE CARE'), findsOneWidget);
      expect(find.text('Water Fern'), findsOneWidget);
      expect(find.textContaining('Overdue'), findsOneWidget);
      expect(find.text('YOUR PLANTS'), findsOneWidget);
      expect(find.text('1 task scheduled'), findsOneWidget);
    });

    testWidgets('empty garden explains the first step', (tester) async {
      await _pump(tester, FakeGardenApi());
      expect(find.text('Add a plant, then schedule its care.'), findsOneWidget);
      expect(find.text('No plants yet.'), findsOneWidget);
    });

    testWidgets('Mark done completes the task and refreshes', (tester) async {
      final api = await _pump(
        tester,
        FakeGardenApi(
          plants: [const GardenPlant(id: 'p1', commonName: 'Fern')],
          tasks: [_task()],
        ),
      );
      await tester.tap(find.byTooltip('Mark done'));
      await tester.pumpAndSettle();
      expect(api.calls, contains('completeTask:t1'));
      expect(find.text('Water Fern'), findsNothing);
      expect(find.text('Done.'), findsOneWidget);
    });

    testWidgets('a care log that did not save is reported', (tester) async {
      final api = FakeGardenApi(tasks: [_task()])..logSaves = false;
      await _pump(tester, api);
      await tester.tap(find.byTooltip('Mark done'));
      await tester.pumpAndSettle();
      expect(
        find.text('Done, but the care log was not saved.'),
        findsOneWidget,
      );
    });

    testWidgets('Skip skips the task', (tester) async {
      final api = await _pump(tester, FakeGardenApi(tasks: [_task()]));
      await tester.tap(find.byTooltip('Skip'));
      await tester.pumpAndSettle();
      expect(api.calls, contains('skipTask:t1'));
      expect(find.text('Water Fern'), findsNothing);
    });

    testWidgets('a rate-limited action says so', (tester) async {
      final api = await _pump(tester, FakeGardenApi(tasks: [_task()]));
      api.failWith = ApiException('slow down', statusCode: 429);
      await tester.tap(find.byTooltip('Skip'));
      await tester.pump();
      await tester.pump();
      expect(find.textContaining('Too many changes'), findsOneWidget);
      api.failWith = null;
      await tester.pumpAndSettle();
    });

    testWidgets('Add plant creates a plant', (tester) async {
      final api = await _pump(tester, FakeGardenApi());
      await tester.tap(find.text('Add plant'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('garden-plant-name')),
        'Pothos',
      );
      await tester.tap(find.text('Add'));
      await tester.pumpAndSettle();
      expect(api.calls, contains('createPlant:Pothos'));
      expect(find.text('Pothos'), findsOneWidget);
    });

    testWidgets('scheduling care creates a weekly task by default', (
      tester,
    ) async {
      final api = await _pump(
        tester,
        FakeGardenApi(
          plants: [const GardenPlant(id: 'p1', commonName: 'Fern')],
        ),
      );
      await tester.tap(find.byTooltip('Schedule care for Fern'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Schedule'));
      await tester.pumpAndSettle();
      expect(api.calls, contains('createTask:p1:watering:7'));
      expect(find.text('Watering Fern'), findsOneWidget);
    });

    testWidgets('a load failure offers Retry', (tester) async {
      final api = FakeGardenApi()
        ..failWith = ApiException('forbidden', statusCode: 403);
      await _pump(tester, api);
      expect(find.text('Could not load your garden.'), findsOneWidget);
      api.failWith = null;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.text('No plants yet.'), findsOneWidget);
    });
  });
}
