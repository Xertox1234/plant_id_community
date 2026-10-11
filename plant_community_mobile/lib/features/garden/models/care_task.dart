/// A scheduled care task: `garden_calendar.CareTask`, as the LIST payload of
/// `GET /calendar/api/care-tasks/` serializes it (`CareTaskListSerializer`).
///
/// When a pending task falls due the server's reminder sweep sends a
/// `care_task_due` push (todo 410); tapping it opens the garden (todo 386).
class CareTask {
  const CareTask({
    required this.id,
    required this.plant,
    required this.title,
    required this.taskType,
    required this.scheduledDate,
    this.plantName = '',
    this.taskTypeDisplay = '',
    this.priority = 'medium',
    this.priorityDisplay = '',
    this.completed = false,
    this.skipped = false,
    this.isRecurring = false,
    this.isOverdue = false,
  });

  /// The task's UUID.
  final String id;

  /// The plant's UUID.
  final String plant;
  final String plantName;

  /// `CARE_TASK_TYPES` key (`watering`, `fertilizing`, ...). Kept raw: the
  /// server has 14 types and sends the label in [taskTypeDisplay].
  final String taskType;
  final String taskTypeDisplay;
  final String title;

  /// `low | medium | high | urgent`.
  final String priority;
  final String priorityDisplay;

  /// When the task is due, in local time.
  final DateTime scheduledDate;
  final bool completed;
  final bool skipped;
  final bool isRecurring;

  /// Computed by the server: pending and past [scheduledDate].
  final bool isOverdue;

  bool get isPending => !completed && !skipped;

  factory CareTask.fromJson(Map<String, dynamic> json) {
    final type = json['task_type'] as String? ?? 'custom';
    return CareTask(
      id: json['uuid'] as String,
      plant: json['plant'] as String,
      plantName: json['plant_name'] as String? ?? '',
      taskType: type,
      taskTypeDisplay: json['task_type_display'] as String? ?? type,
      title: json['title'] as String? ?? '',
      priority: json['priority'] as String? ?? 'medium',
      priorityDisplay: json['priority_display'] as String? ?? '',
      scheduledDate: DateTime.parse(json['scheduled_date'] as String).toLocal(),
      completed: json['completed'] as bool? ?? false,
      skipped: json['skipped'] as bool? ?? false,
      isRecurring: json['is_recurring'] as bool? ?? false,
      isOverdue: json['is_overdue'] as bool? ?? false,
    );
  }
}

/// The task types the add-task form offers: the houseplant subset of the
/// server's `CARE_TASK_TYPES` (no mulching, harvesting or winterization —
/// todo 386 owner decision: houseplant core only). Keys must stay valid
/// server choices; anything else is a 400.
const Map<String, String> houseplantTaskTypes = {
  'watering': 'Watering',
  'fertilizing': 'Fertilizing',
  'pruning': 'Pruning',
  'repotting': 'Repotting',
  'pest_check': 'Pest inspection',
  'custom': 'Other',
};

/// The CareLog activity a completed task of [taskType] records. CareLog's
/// vocabulary (`ACTIVITY_TYPE_CHOICES`) differs from CareTask's, so map the
/// overlap and file the rest as `other`.
String careLogActivityFor(String taskType) => switch (taskType) {
  'watering' || 'fertilizing' || 'pruning' || 'repotting' => taskType,
  'pest_check' => 'observation',
  _ => 'other',
};
