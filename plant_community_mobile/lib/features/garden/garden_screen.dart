import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../services/api_service.dart';
import 'models/models.dart';
import 'providers/garden_provider.dart';
import 'services/garden_api_service.dart';

/// The garden: the user's plants and their care schedule (todo 386).
///
/// Built on the houseplant core of `apps/garden_calendar` only — plants
/// without beds, CareTasks and the CareLog (owner decision 2026-09-24). A
/// pending task that falls due is pushed to the device by the server's
/// reminder sweep (todo 410), and tapping that push opens this screen.
///
/// Auth-only: the route is in the router's `protectedRoutes`.
class GardenScreen extends ConsumerWidget {
  const GardenScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final garden = ref.watch(gardenProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Care Schedule'), centerTitle: true),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _addPlant(context, ref),
        icon: const Icon(LucideIcons.plus),
        label: const Text('Add plant'),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(gardenProvider),
          child: garden.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => ListView(
              children: [
                const SizedBox(height: 120),
                const Center(child: Text('Could not load your garden.')),
                const SizedBox(height: AppSpacing.md),
                Center(
                  child: OutlinedButton(
                    onPressed: () => ref.invalidate(gardenProvider),
                    child: const Text('Retry'),
                  ),
                ),
              ],
            ),
            data: (data) => _GardenList(data: data),
          ),
        ),
      ),
    );
  }
}

class _GardenList extends ConsumerWidget {
  const _GardenList({required this.data});

  final GardenData data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final eyebrow = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);
    final muted = Theme.of(
      context,
    ).textTheme.bodyMedium?.copyWith(color: ext.ink2);

    return ListView(
      padding: EdgeInsets.fromLTRB(
        ext.padScreen,
        ext.padScreen,
        ext.padScreen,
        AppSpacing.xl3 * 2,
      ),
      children: [
        Text('DUE CARE', style: eyebrow),
        SizedBox(height: ext.gapY),
        if (data.tasks.isEmpty)
          Text(
            data.plants.isEmpty
                ? 'Add a plant, then schedule its care.'
                : 'Nothing due. Schedule care from one of your plants below.',
            style: muted,
          )
        else
          for (final task in data.tasks) _TaskTile(task: task),
        SizedBox(height: ext.gapY * 2),
        Text('YOUR PLANTS', style: eyebrow),
        SizedBox(height: ext.gapY),
        if (data.plants.isEmpty)
          Text('No plants yet.', style: muted)
        else
          for (final plant in data.plants)
            _PlantTile(plant: plant, pending: data.tasksFor(plant.id).length),
      ],
    );
  }
}

class _TaskTile extends ConsumerWidget {
  const _TaskTile({required this.task});

  final CareTask task;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final due = _dueLabel(task);
    return Card(
      child: ListTile(
        title: Text(task.title.isEmpty ? task.taskTypeDisplay : task.title),
        subtitle: Text(
          '${task.plantName} · $due',
          style: task.isOverdue ? TextStyle(color: cs.error) : null,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: 'Skip',
              icon: const Icon(LucideIcons.skipForward),
              onPressed: () => _run(
                context,
                ref,
                () => ref.read(gardenApiProvider).skipTask(task),
                done: 'Skipped.',
              ),
            ),
            IconButton(
              tooltip: 'Mark done',
              icon: Icon(LucideIcons.check, color: cs.primary),
              onPressed: () => _run(context, ref, () async {
                final logged = await ref
                    .read(gardenApiProvider)
                    .completeTask(task);
                return logged ? null : 'Done, but the care log was not saved.';
              }, done: 'Done.'),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlantTile extends ConsumerWidget {
  const _PlantTile({required this.plant, required this.pending});

  final GardenPlant plant;
  final int pending;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: ListTile(
        leading: const Icon(LucideIcons.sprout),
        title: Text(plant.displayName),
        subtitle: Text(
          pending == 0
              ? 'No care scheduled'
              : '$pending task${pending == 1 ? '' : 's'} scheduled',
        ),
        trailing: IconButton(
          tooltip: 'Schedule care for ${plant.commonName}',
          icon: const Icon(LucideIcons.calendarPlus),
          onPressed: () => _addTask(context, ref, plant),
        ),
      ),
    );
  }
}

/// "Overdue · Oct 3", "Due today" or "Due Oct 12".
String _dueLabel(CareTask task) {
  final now = DateTime.now();
  final d = task.scheduledDate;
  final sameDay =
      d.year == now.year && d.month == now.month && d.day == now.day;
  final date = DateFormat.MMMd().format(d);
  if (task.isOverdue && !sameDay) return 'Overdue · $date';
  if (sameDay) return 'Due today';
  return 'Due $date';
}

/// Runs a mutation, refreshes the garden, and reports the outcome. [action]
/// may return a message that replaces [done] (a partial success).
Future<void> _run(
  BuildContext context,
  WidgetRef ref,
  Future<Object?> Function() action, {
  required String done,
}) async {
  final messenger = ScaffoldMessenger.of(context);
  String message;
  try {
    final result = await action();
    message = result is String ? result : done;
  } on ApiException catch (e) {
    message = e.statusCode == 429
        ? 'Too many changes at once. Try again in a minute.'
        : 'That did not work. Please try again.';
  }
  messenger.showSnackBar(SnackBar(content: Text(message)));
  // A WidgetRef is dead once its widget is gone (the user navigated away
  // mid-request); the next visit fetches fresh anyway.
  if (context.mounted) ref.invalidate(gardenProvider);
}

Future<void> _addPlant(BuildContext context, WidgetRef ref) async {
  final name = await showDialog<String>(
    context: context,
    builder: (context) => const _AddPlantDialog(),
  );
  if (name == null || name.isEmpty || !context.mounted) return;
  await _run(
    context,
    ref,
    () => ref
        .read(gardenApiProvider)
        .createPlant(commonName: name, plantedDate: DateTime.now()),
    done: 'Added $name.',
  );
}

Future<void> _addTask(
  BuildContext context,
  WidgetRef ref,
  GardenPlant plant,
) async {
  final draft = await showDialog<_TaskDraft>(
    context: context,
    builder: (context) => _AddTaskDialog(plant: plant),
  );
  if (draft == null || !context.mounted) return;
  await _run(
    context,
    ref,
    () => ref
        .read(gardenApiProvider)
        .createTask(
          plantId: plant.id,
          taskType: draft.taskType,
          title: draft.title,
          scheduledDate: draft.when,
          recurrenceDays: draft.repeatDays,
        ),
    done: 'Scheduled.',
  );
}

class _AddPlantDialog extends StatefulWidget {
  const _AddPlantDialog();

  @override
  State<_AddPlantDialog> createState() => _AddPlantDialogState();
}

class _AddPlantDialogState extends State<_AddPlantDialog> {
  final _name = TextEditingController();

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add a plant'),
      content: TextField(
        key: const Key('garden-plant-name'),
        controller: _name,
        autofocus: true,
        maxLength: 200,
        decoration: const InputDecoration(labelText: 'Name'),
        textCapitalization: TextCapitalization.sentences,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_name.text.trim()),
          child: const Text('Add'),
        ),
      ],
    );
  }
}

class _TaskDraft {
  const _TaskDraft({
    required this.taskType,
    required this.title,
    required this.when,
    this.repeatDays,
  });

  final String taskType;
  final String title;
  final DateTime when;
  final int? repeatDays;
}

/// Repeat choices, in days. `null` = once.
const List<int?> _repeatChoices = [null, 3, 7, 14, 30];

class _AddTaskDialog extends StatefulWidget {
  const _AddTaskDialog({required this.plant});

  final GardenPlant plant;

  @override
  State<_AddTaskDialog> createState() => _AddTaskDialogState();
}

class _AddTaskDialogState extends State<_AddTaskDialog> {
  String _type = houseplantTaskTypes.keys.first;
  int? _repeat = 7;
  late DateTime _date = DateUtils.dateOnly(
    DateTime.now(),
  ).add(const Duration(days: 1));

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Schedule care for ${widget.plant.commonName}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Task'),
            items: [
              for (final e in houseplantTaskTypes.entries)
                DropdownMenuItem(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) => setState(() => _type = v ?? _type),
          ),
          const SizedBox(height: AppSpacing.md),
          DropdownButtonFormField<int?>(
            initialValue: _repeat,
            decoration: const InputDecoration(labelText: 'Repeat'),
            items: [
              for (final days in _repeatChoices)
                DropdownMenuItem(
                  value: days,
                  child: Text(days == null ? 'Once' : 'Every $days days'),
                ),
            ],
            onChanged: (v) => setState(() => _repeat = v),
          ),
          const SizedBox(height: AppSpacing.md),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('First due'),
            subtitle: Text(DateFormat.yMMMd().format(_date)),
            trailing: const Icon(LucideIcons.calendar),
            onTap: () async {
              final now = DateUtils.dateOnly(DateTime.now());
              final picked = await showDatePicker(
                context: context,
                initialDate: _date,
                firstDate: now,
                lastDate: now.add(const Duration(days: 365)),
              );
              if (picked != null) setState(() => _date = picked);
            },
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(
            _TaskDraft(
              taskType: _type,
              title: '${houseplantTaskTypes[_type]} ${widget.plant.commonName}',
              // 9 am local on the chosen day: a reminder at midnight would
              // arrive while the owner sleeps.
              when: _date.add(const Duration(hours: 9)),
              repeatDays: _repeat,
            ),
          ),
          child: const Text('Schedule'),
        ),
      ],
    );
  }
}
