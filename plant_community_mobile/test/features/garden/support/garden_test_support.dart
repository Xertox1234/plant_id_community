import 'package:dio/dio.dart';
import 'package:plant_community_mobile/features/garden/models/models.dart';
import 'package:plant_community_mobile/features/garden/services/garden_api_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Records requests and answers them from [responses], keyed by
/// `METHOD path`. A missing key throws a 500 [ApiException].
class RecordingApiService extends ApiService {
  RecordingApiService(this.responses) : super(baseUrl: 'http://test/api/v1');

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

  /// Whether the fetches report hitting [gardenMaxPages].
  bool truncated = false;

  void _maybeFail() {
    final e = failWith;
    if (e != null) throw e;
  }

  @override
  Future<GardenList<GardenPlant>> fetchPlants() async {
    calls.add('fetchPlants');
    _maybeFail();
    return GardenList(List.of(plants), truncated: truncated);
  }

  @override
  Future<GardenList<CareTask>> fetchPendingTasks() async {
    calls.add('fetchPendingTasks');
    _maybeFail();
    return GardenList(tasks.where((t) => t.isPending).toList());
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
