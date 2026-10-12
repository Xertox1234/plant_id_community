import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../services/auth_service.dart';

/// What a tapped care-reminder push asked the garden to show (todo 621).
///
/// Carried in a provider, not in the route: the garden may already be open,
/// and pushing it again would stack a second GardenScreen (todo 570 #6).
@immutable
class GardenFocus {
  /// One task: the push named exactly one due task.
  const GardenFocus.task(String this.taskId) : dueList = false;

  /// The aggregate due list: the push was for several tasks.
  const GardenFocus.dueList() : taskId = null, dueList = true;

  final String? taskId;
  final bool dueList;

  @override
  bool operator ==(Object other) =>
      other is GardenFocus &&
      other.taskId == taskId &&
      other.dueList == dueList;

  @override
  int get hashCode => Object.hash(taskId, dueList);

  @override
  String toString() =>
      dueList ? 'GardenFocus.dueList()' : 'GardenFocus.task($taskId)';
}

/// The pending [GardenFocus], or null. The garden screen consumes it: it
/// highlights the task, or says the task is no longer due, then clears it.
///
/// Cleared whenever the session signs in or out: a target set by a tap that
/// met the login screen belongs to whoever the push was for, not to the
/// account that signs in next.
class GardenFocusNotifier extends Notifier<GardenFocus?> {
  @override
  GardenFocus? build() {
    ref.listen<bool>(authServiceProvider.select((s) => s.isAuthenticated), (
      previous,
      next,
    ) {
      if (previous != next) state = null;
    });
    return null;
  }

  void set(GardenFocus? focus) => state = focus;

  void clear() => state = null;
}

final gardenFocusProvider = NotifierProvider<GardenFocusNotifier, GardenFocus?>(
  GardenFocusNotifier.new,
);
