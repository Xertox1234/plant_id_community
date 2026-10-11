import 'package:plant_community_mobile/features/garden/models/models.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// In-memory [GardenApi] for widget tests: records every call, and fails
/// any call while [failWith] is set.
class FakeGardenApi implements GardenApi {
  FakeGardenApi({List<GardenPlant>? plants, List<CareTask>? tasks})
    : plants = plants ?? [],
      tasks = tasks ?? [];

  final List<GardenPlant> plants;
  final List<CareTask> tasks;
  final List<String> calls = [];
  ApiException? failWith;

  /// What [completeTask] reports about the care-log write.
  bool logSaves = true;

  void _maybeFail() {
    final e = failWith;
    if (e != null) throw e;
  }

  @override
  Future<List<GardenPlant>> fetchPlants() async {
    calls.add('fetchPlants');
    _maybeFail();
    return List.of(plants);
  }

  @override
  Future<List<CareTask>> fetchPendingTasks() async {
    calls.add('fetchPendingTasks');
    _maybeFail();
    return tasks.where((t) => t.isPending).toList();
  }

  @override
  Future<GardenPlant> createPlant({
    required String commonName,
    required DateTime plantedDate,
  }) async {
    calls.add('createPlant:$commonName');
    _maybeFail();
    final plant = GardenPlant(
      id: 'p${plants.length + 1}',
      commonName: commonName,
    );
    plants.add(plant);
    return plant;
  }

  @override
  Future<void> createTask({
    required String plantId,
    required String taskType,
    required String title,
    required DateTime scheduledDate,
    int? recurrenceDays,
  }) async {
    calls.add('createTask:$plantId:$taskType:$recurrenceDays');
    _maybeFail();
    tasks.add(
      CareTask(
        id: 't${tasks.length + 1}',
        plant: plantId,
        title: title,
        taskType: taskType,
        scheduledDate: scheduledDate,
      ),
    );
  }

  @override
  Future<bool> completeTask(CareTask task) async {
    calls.add('completeTask:${task.id}');
    _maybeFail();
    _replace(task, completed: true);
    return logSaves;
  }

  @override
  Future<void> skipTask(CareTask task) async {
    calls.add('skipTask:${task.id}');
    _maybeFail();
    _replace(task, skipped: true);
  }

  void _replace(CareTask task, {bool completed = false, bool skipped = false}) {
    final i = tasks.indexWhere((t) => t.id == task.id);
    tasks[i] = CareTask(
      id: task.id,
      plant: task.plant,
      plantName: task.plantName,
      title: task.title,
      taskType: task.taskType,
      scheduledDate: task.scheduledDate,
      completed: completed,
      skipped: skipped,
    );
  }
}
