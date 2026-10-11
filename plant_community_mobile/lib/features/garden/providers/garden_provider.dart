import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../services/api_service.dart';
import '../models/models.dart';
import '../services/garden_api_service.dart';

part 'garden_provider.g.dart';

/// A 4xx (signed out, forbidden) will not change on retry, so it fails at
/// once instead of spinning for Riverpod's ~40 s of retries (see
/// `blogRetry`, docs/rules/flutter.md). Network and server errors keep the
/// default backoff.
Duration? gardenRetry(int retryCount, Object error) {
  if (error is ApiException) {
    final status = error.statusCode ?? 0;
    if (status >= 400 && status < 500) return null;
  }
  return ProviderContainer.defaultRetry(retryCount, error);
}

/// Everything the garden screen shows: the user's plants and their pending
/// care tasks, fetched together. Mutations invalidate this provider.
@Riverpod(retry: gardenRetry)
Future<GardenData> garden(Ref ref) async {
  final api = ref.watch(gardenApiProvider);
  final (plants, tasks) = await (
    api.fetchPlants(),
    api.fetchPendingTasks(),
  ).wait;
  return GardenData(plants: plants, tasks: tasks);
}

class GardenData {
  const GardenData({required this.plants, required this.tasks});

  final List<GardenPlant> plants;

  /// Pending tasks, soonest first (the server orders them).
  final List<CareTask> tasks;

  /// Pending tasks for one plant.
  List<CareTask> tasksFor(String plantId) =>
      tasks.where((t) => t.plant == plantId).toList();
}
