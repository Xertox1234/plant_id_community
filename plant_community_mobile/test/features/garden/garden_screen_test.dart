import 'dart:async';

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

/// A [FakeGardenApi] whose [completeTask] hangs on [gate] until the test
/// completes it — a mutation still in flight.
class _GatedGardenApi extends FakeGardenApi {
  _GatedGardenApi({super.tasks});

  final Completer<void> gate = Completer<void>();

  @override
  Future<bool> completeTask(CareTask task) async {
    calls.add('completeTask:${task.id}');
    await gate.future;
    return logSaves;
  }
}

/// A [FakeGardenApi] whose task fetches hang on [reloadGate] once
/// [holdReloads] is set: a garden reload still in flight. Its mutations
/// leave the task pending, so the tile outlives the reload.
class _SlowReloadGardenApi extends FakeGardenApi {
  _SlowReloadGardenApi({super.tasks});

  bool holdReloads = false;
  Completer<void> reloadGate = Completer<void>();

  @override
  Future<GardenList<CareTask>> fetchPendingTasks() async {
    if (holdReloads) await reloadGate.future;
    return super.fetchPendingTasks();
  }

  @override
  Future<bool> completeTask(CareTask task) async {
    calls.add('completeTask:${task.id}');
    return true;
  }
}

/// A [FakeGardenApi] whose skip fails with something that is not an
/// [ApiException]: a response that did not parse, say.
class _BrokenSkipGardenApi extends FakeGardenApi {
  _BrokenSkipGardenApi({super.tasks});

  @override
  Future<void> skipTask(CareTask task) async {
    calls.add('skipTask:${task.id}');
    throw TypeError();
  }
}

IconButton _button(WidgetTester tester, String tooltip) => tester.widget(
  find.ancestor(of: find.byTooltip(tooltip), matching: find.byType(IconButton)),
);

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
        final api = RecordingApiService({
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
        expect(plants.items.map((p) => p.commonName), ['Monstera', 'Fern']);
        expect(plants.truncated, isFalse);
        expect(api.requests.first.$4, {'is_active': 'true'});
        expect(api.requests[1].$4, isNull);
      },
    );

    test('fetchPendingTasks filters out completed and skipped tasks, and '
        "inactive plants' tasks", () async {
      final api = RecordingApiService({
        'GET /calendar/api/care-tasks/': {
          'count': 1,
          'next': null,
          'results': [_taskJson()],
        },
      });
      final tasks = await HttpGardenApi(api).fetchPendingTasks();
      expect(tasks.items, hasLength(1));
      expect(api.requests.single.$4, {
        'completed': 'false',
        'skipped': 'false',
        'plant__is_active': 'true',
        'ordering': 'scheduled_date',
      });
    });

    test('createPlant sends a bedless plant with a calendar date', () async {
      final api = RecordingApiService({
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
      final api = RecordingApiService({'POST /calendar/api/care-tasks/': {}});
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
      final api = RecordingApiService({'POST /calendar/api/care-tasks/': {}});
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
      final api = RecordingApiService({
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
      final api = RecordingApiService({
        'POST /calendar/api/care-tasks/t1/complete/': {},
      });
      expect(await HttpGardenApi(api).completeTask(_task()), isFalse);
    });

    test('a failed completion throws and writes no care log', () async {
      final api = RecordingApiService({});
      await expectLater(
        HttpGardenApi(api).completeTask(_task()),
        throwsA(isA<ApiException>()),
      );
      expect(api.requests, hasLength(1));
    });
  });

  group('careTaskTitle (todo 570 #4, #7)', () {
    test('a short title is unchanged', () {
      expect(careTaskTitle('Watering', 'Fern'), 'Watering Fern');
    });

    test('a long one is cut to the server max with an ellipsis', () {
      final title = careTaskTitle('Pest inspection', 'x' * 200);
      expect(title.length, careTaskTitleMaxLength);
      expect(title, startsWith('Pest inspection xxx'));
      expect(title, endsWith('…'));
    });

    test('an emoji at the cut is never split (todo 593 #3)', () {
      // 'Watering ' is 9 code points; the emoji sits at code point 198, the
      // last one kept, and is two UTF-16 code units.
      final name = '${'x' * 189}🌿${'y' * 10}';
      final title = careTaskTitle('Watering', name);
      expect(title.runes.length, careTaskTitleMaxLength);
      expect(title, endsWith('🌿…'));
      // No lone surrogate: every rune round-trips.
      expect(String.fromCharCodes(title.runes), title);
      expect(title.runes.where((r) => r >= 0xD800 && r <= 0xDFFF), isEmpty);
    });

    test('200 code points with emoji are not cut (todo 593 #3)', () {
      final name = '🌿' * 191; // 9 + 191 = 200 code points, 391 code units
      final title = careTaskTitle('Watering', name);
      expect(title, 'Watering $name');
    });
  });

  group('firstDueAt (todo 570 #10)', () {
    test('a future day is due at 9 am local, from its date fields', () {
      final now = DateTime(2026, 3, 1, 12);
      for (final day in [
        DateTime(2026, 3, 8), // US spring-forward
        DateTime(2026, 3, 29), // EU spring-forward
        DateTime(2026, 11, 1), // US fall-back
        DateTime(2026, 10, 25), // EU fall-back
      ]) {
        final due = firstDueAt(day, now: now);
        expect(due.hour, 9, reason: '$day');
        expect(due.minute, 0, reason: '$day');
        expect((due.year, due.month, due.day), (day.year, day.month, day.day));
      }
    });

    test('today after 9 am is due now, not in the past', () {
      final now = DateTime(2026, 10, 11, 14, 30);
      expect(firstDueAt(DateTime(2026, 10, 11), now: now), now);
    });

    test('today before 9 am is due at 9', () {
      final now = DateTime(2026, 10, 11, 7);
      expect(
        firstDueAt(DateTime(2026, 10, 11), now: now),
        DateTime(2026, 10, 11, 9),
      );
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

    testWidgets(
      'Done and Skip are disabled while a completion is in flight, so a '
      'double tap sends one request (todo 386 review)',
      (tester) async {
        final api = _GatedGardenApi(tasks: [_task()]);
        await _pump(tester, api);

        await tester.tap(find.byTooltip('Mark done'));
        await tester.pump();

        expect(_button(tester, 'Mark done').onPressed, isNull);
        expect(_button(tester, 'Skip').onPressed, isNull);

        await tester.tap(find.byTooltip('Mark done'), warnIfMissed: false);
        await tester.tap(find.byTooltip('Skip'), warnIfMissed: false);
        await tester.pump();
        expect(
          api.calls.where((c) => c.startsWith('completeTask')),
          hasLength(1),
        );
        expect(api.calls.where((c) => c.startsWith('skipTask')), isEmpty);

        api.gate.complete();
        await tester.pumpAndSettle();

        // The fake leaves the task pending, so the tile stays; it is usable
        // again once the request settles.
        expect(_button(tester, 'Mark done').onPressed, isNotNull);
        expect(_button(tester, 'Skip').onPressed, isNotNull);
      },
    );

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

    testWidgets('a short list still pulls to refresh (todo 570 #1)', (
      tester,
    ) async {
      final api = await _pump(tester, FakeGardenApi());
      final before = api.calls.where((c) => c == 'fetchPlants').length;

      await tester.fling(find.text('DUE CARE'), const Offset(0, 300), 1000);
      await tester.pumpAndSettle();

      expect(
        api.calls.where((c) => c == 'fetchPlants').length,
        greaterThan(before),
      );
    });

    testWidgets('the error state pulls to refresh too (todo 570 #1)', (
      tester,
    ) async {
      final api = FakeGardenApi()
        ..failWith = ApiException('down', statusCode: 403);
      await _pump(tester, api);
      expect(find.text('Could not load your garden.'), findsOneWidget);
      api.failWith = null;

      await tester.fling(
        find.text('Could not load your garden.'),
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      expect(find.text('No plants yet.'), findsOneWidget);
    });

    testWidgets(
      'the refresh spinner stays up until the reload lands (todo 570 #11)',
      (tester) async {
        final api = _SlowReloadGardenApi();
        await _pump(tester, api);
        api.holdReloads = true;

        await tester.fling(find.text('DUE CARE'), const Offset(0, 300), 1000);
        await tester.pump();
        await tester.pump(const Duration(seconds: 1));
        expect(find.byType(RefreshProgressIndicator), findsOneWidget);

        await tester.pump(const Duration(seconds: 5));
        expect(find.byType(RefreshProgressIndicator), findsOneWidget);

        api.reloadGate.complete();
        await tester.pumpAndSettle();
        expect(find.byType(RefreshProgressIndicator), findsNothing);
      },
    );

    testWidgets(
      "a finished task's buttons stay disabled until the reload lands "
      '(todo 570 #9)',
      (tester) async {
        final api = _SlowReloadGardenApi(tasks: [_task()]);
        await _pump(tester, api);
        api.holdReloads = true;

        await tester.tap(find.byTooltip('Mark done'));
        await tester.pump();
        await tester.pump();
        expect(api.calls, contains('completeTask:t1'));
        expect(find.text('Done.'), findsOneWidget);

        // The request is done; the reload is not.
        expect(_button(tester, 'Mark done').onPressed, isNull);
        expect(_button(tester, 'Skip').onPressed, isNull);

        api.reloadGate.complete();
        await tester.pumpAndSettle();
        // The fake left the task pending, so it is usable again.
        expect(_button(tester, 'Mark done').onPressed, isNotNull);
      },
    );

    testWidgets('an unexpected error is reported, not thrown (todo 570 #5)', (
      tester,
    ) async {
      final api = await _pump(tester, _BrokenSkipGardenApi(tasks: [_task()]));
      final before = api.calls.where((c) => c == 'fetchPlants').length;

      await tester.tap(find.byTooltip('Skip'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('That did not work. Please try again.'), findsOneWidget);
      expect(
        api.calls.where((c) => c == 'fetchPlants').length,
        greaterThan(before),
      );
    });

    testWidgets('a truncated list says so (todo 570 #8)', (tester) async {
      await _pump(tester, FakeGardenApi()..truncated = true);
      expect(find.text(gardenTruncatedNotice), findsOneWidget);
    });

    testWidgets('a complete list shows no truncation notice', (tester) async {
      await _pump(tester, FakeGardenApi());
      expect(find.text(gardenTruncatedNotice), findsNothing);
    });

    testWidgets(
      'scheduling care for a long-named plant sends a title the server '
      'accepts (todo 570 #4, #7)',
      (tester) async {
        final name = 'F' * 200;
        final api = await _pump(
          tester,
          FakeGardenApi(
            plants: [GardenPlant(id: 'p1', commonName: name)],
          ),
        );
        await tester.tap(find.byTooltip('Schedule care for $name'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Schedule'));
        await tester.pumpAndSettle();

        expect(api.calls, contains('createTask:p1:watering:7'));
        expect(api.tasks.single.title.length, careTaskTitleMaxLength);
        expect(api.tasks.single.title, startsWith('Watering FFF'));
      },
    );

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
