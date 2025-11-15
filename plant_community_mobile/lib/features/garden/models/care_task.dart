/// Care Task Model
///
/// Represents a care reminder or task for an individual plant.
/// Maps to backend CareTask model from apps/garden_calendar/models.py
class CareTask {
  /// Unique identifier (UUID from backend)
  final String id;

  /// Plant this task is for
  final String plantId;

  /// User who created this task
  final String createdById;

  /// Task details
  final CareTaskType taskType;
  final String? customTaskName;
  final String title;
  final String? notes;
  final TaskPriority priority;

  /// Scheduling
  final DateTime scheduledDate;
  final bool isRecurring;
  final int? recurrenceIntervalDays;
  final DateTime? recurrenceEndDate;

  /// Completion status
  final bool completed;
  final DateTime? completedAt;
  final String? completedById;

  /// Skip status
  final bool skipped;
  final String? skipReason;
  final DateTime? skippedAt;

  /// Notification
  final bool sendNotification;
  final DateTime? notificationSentAt;

  /// Timestamps
  final DateTime createdAt;
  final DateTime updatedAt;

  const CareTask({
    required this.id,
    required this.plantId,
    required this.createdById,
    required this.taskType,
    this.customTaskName,
    required this.title,
    this.notes,
    required this.priority,
    required this.scheduledDate,
    this.isRecurring = false,
    this.recurrenceIntervalDays,
    this.recurrenceEndDate,
    this.completed = false,
    this.completedAt,
    this.completedById,
    this.skipped = false,
    this.skipReason,
    this.skippedAt,
    this.sendNotification = true,
    this.notificationSentAt,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Create from JSON
  factory CareTask.fromJson(Map<String, dynamic> json) {
    return CareTask(
      id: json['uuid'] as String,
      plantId: json['plant'] as String,
      createdById: json['created_by'] as String,
      taskType: CareTaskType.fromString(json['task_type'] as String),
      customTaskName: json['custom_task_name'] as String?,
      title: json['title'] as String,
      notes: json['notes'] as String?,
      priority: TaskPriority.fromString(json['priority'] as String),
      scheduledDate: DateTime.parse(json['scheduled_date'] as String),
      isRecurring: json['is_recurring'] as bool? ?? false,
      recurrenceIntervalDays: json['recurrence_interval_days'] as int?,
      recurrenceEndDate: json['recurrence_end_date'] != null
          ? DateTime.parse(json['recurrence_end_date'] as String)
          : null,
      completed: json['completed'] as bool? ?? false,
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
      completedById: json['completed_by'] as String?,
      skipped: json['skipped'] as bool? ?? false,
      skipReason: json['skip_reason'] as String?,
      skippedAt: json['skipped_at'] != null
          ? DateTime.parse(json['skipped_at'] as String)
          : null,
      sendNotification: json['send_notification'] as bool? ?? true,
      notificationSentAt: json['notification_sent_at'] != null
          ? DateTime.parse(json['notification_sent_at'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  /// Convert to JSON for API
  Map<String, dynamic> toJson() {
    return {
      'uuid': id,
      'plant': plantId,
      'created_by': createdById,
      'task_type': taskType.value,
      'custom_task_name': customTaskName,
      'title': title,
      'notes': notes,
      'priority': priority.value,
      'scheduled_date': scheduledDate.toIso8601String(),
      'is_recurring': isRecurring,
      'recurrence_interval_days': recurrenceIntervalDays,
      'recurrence_end_date': recurrenceEndDate?.toIso8601String().split('T')[0],
      'completed': completed,
      'completed_at': completedAt?.toIso8601String(),
      'completed_by': completedById,
      'skipped': skipped,
      'skip_reason': skipReason,
      'skipped_at': skippedAt?.toIso8601String(),
      'send_notification': sendNotification,
      'notification_sent_at': notificationSentAt?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  /// Copy with new values
  CareTask copyWith({
    String? id,
    String? plantId,
    String? createdById,
    CareTaskType? taskType,
    String? customTaskName,
    String? title,
    String? notes,
    TaskPriority? priority,
    DateTime? scheduledDate,
    bool? isRecurring,
    int? recurrenceIntervalDays,
    DateTime? recurrenceEndDate,
    bool? completed,
    DateTime? completedAt,
    String? completedById,
    bool? skipped,
    String? skipReason,
    DateTime? skippedAt,
    bool? sendNotification,
    DateTime? notificationSentAt,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return CareTask(
      id: id ?? this.id,
      plantId: plantId ?? this.plantId,
      createdById: createdById ?? this.createdById,
      taskType: taskType ?? this.taskType,
      customTaskName: customTaskName ?? this.customTaskName,
      title: title ?? this.title,
      notes: notes ?? this.notes,
      priority: priority ?? this.priority,
      scheduledDate: scheduledDate ?? this.scheduledDate,
      isRecurring: isRecurring ?? this.isRecurring,
      recurrenceIntervalDays: recurrenceIntervalDays ?? this.recurrenceIntervalDays,
      recurrenceEndDate: recurrenceEndDate ?? this.recurrenceEndDate,
      completed: completed ?? this.completed,
      completedAt: completedAt ?? this.completedAt,
      completedById: completedById ?? this.completedById,
      skipped: skipped ?? this.skipped,
      skipReason: skipReason ?? this.skipReason,
      skippedAt: skippedAt ?? this.skippedAt,
      sendNotification: sendNotification ?? this.sendNotification,
      notificationSentAt: notificationSentAt ?? this.notificationSentAt,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// Is task overdue?
  bool get isOverdue {
    if (completed || skipped) return false;
    return DateTime.now().isAfter(scheduledDate);
  }

  /// Is task due today?
  bool get isDueToday {
    if (completed || skipped) return false;
    final now = DateTime.now();
    final scheduled = scheduledDate;
    return now.year == scheduled.year &&
        now.month == scheduled.month &&
        now.day == scheduled.day;
  }

  /// Is task upcoming (within next 7 days)?
  bool get isUpcoming {
    if (completed || skipped) return false;
    final daysUntil = scheduledDate.difference(DateTime.now()).inDays;
    return daysUntil > 0 && daysUntil <= 7;
  }

  /// Get task status
  TaskStatus get status {
    if (completed) return TaskStatus.completed;
    if (skipped) return TaskStatus.skipped;
    if (isOverdue) return TaskStatus.overdue;
    if (isDueToday) return TaskStatus.dueToday;
    if (isUpcoming) return TaskStatus.upcoming;
    return TaskStatus.scheduled;
  }
}

/// Care Task Type Enum
enum CareTaskType {
  water('water', 'Water'),
  fertilize('fertilize', 'Fertilize'),
  prune('prune', 'Prune'),
  transplant('transplant', 'Transplant'),
  pest_control('pest_control', 'Pest Control'),
  disease_treatment('disease_treatment', 'Disease Treatment'),
  mulch('mulch', 'Mulch'),
  harvest('harvest', 'Harvest'),
  deadhead('deadhead', 'Deadhead'),
  stake('stake', 'Stake/Support'),
  thin('thin', 'Thin Seedlings'),
  custom('custom', 'Custom Task');

  const CareTaskType(this.value, this.label);
  final String value;
  final String label;

  static CareTaskType fromString(String value) {
    return CareTaskType.values.firstWhere(
      (e) => e.value == value,
      orElse: () => CareTaskType.custom,
    );
  }
}

/// Task Priority Enum
enum TaskPriority {
  low('low', 'Low'),
  medium('medium', 'Medium'),
  high('high', 'High'),
  urgent('urgent', 'Urgent');

  const TaskPriority(this.value, this.label);
  final String value;
  final String label;

  static TaskPriority fromString(String value) {
    return TaskPriority.values.firstWhere(
      (e) => e.value == value,
      orElse: () => TaskPriority.medium,
    );
  }
}

/// Task Status Enum (derived from task state)
enum TaskStatus {
  completed('Completed'),
  skipped('Skipped'),
  overdue('Overdue'),
  dueToday('Due Today'),
  upcoming('Upcoming'),
  scheduled('Scheduled');

  const TaskStatus(this.label);
  final String label;
}
