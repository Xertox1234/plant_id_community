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
          // Awaits the reload, so the spinner stays up until it lands
          // (todo 570 #11).
          onRefresh: () => _reload(ref),
          child: garden.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => ListView(
              // Scrollable even when the content is shorter than the
              // screen, or pull-to-refresh never fires (todo 570 #1).
              physics: const AlwaysScrollableScrollPhysics(),
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
      // See the error state: a short list must still pull to refresh.
      physics: const AlwaysScrollableScrollPhysics(),
      padding: EdgeInsets.fromLTRB(
        ext.padScreen,
        ext.padScreen,
        ext.padScreen,
        AppSpacing.xl3 * 2,
      ),
      children: [
        if (data.truncated) ...[
          Text(gardenTruncatedNotice, style: muted),
          SizedBox(height: ext.gapY),
        ],
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
          for (final task in data.tasks)
            _TaskTile(key: ValueKey(task.id), task: task),
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

/// A due task with Skip and Mark done. Both buttons are disabled while
/// either mutation is in flight, so a double tap (or Done then Skip) sends
/// one request, not two (todo 386 review; the server also refuses the
/// loser, but a disabled button never sends it).
class _TaskTile extends ConsumerStatefulWidget {
  const _TaskTile({super.key, required this.task});

  final CareTask task;

  @override
  ConsumerState<_TaskTile> createState() => _TaskTileState();
}

class _TaskTileState extends ConsumerState<_TaskTile> {
  bool _busy = false;

  Future<void> _mutate(
    Future<Object?> Function() action, {
    required String done,
  }) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _run(context, ref, action, done: done);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final task = widget.task;
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
              onPressed: _busy
                  ? null
                  : () => _mutate(
                      () => ref.read(gardenApiProvider).skipTask(task),
                      done: 'Skipped.',
                    ),
            ),
            IconButton(
              tooltip: 'Mark done',
              icon: Icon(LucideIcons.check, color: cs.primary),
              onPressed: _busy
                  ? null
                  : () => _mutate(() async {
                      final logged = await ref
                          .read(gardenApiProvider)
                          .completeTask(task);
                      return logged
                          ? null
                          : 'Done, but the care log was not saved.';
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

/// Shown above the lists when either stopped at [gardenMaxPages] (todo 570,
/// owner decision 2026-10-11: keep the cap, say when it is reached).
const String gardenTruncatedNotice =
    'List truncated: you have more plants or care tasks than the app can '
    'show, so some are missing below.';

/// Reloads the garden and completes when the reload has landed. A failed
/// reload is not rethrown: the screen shows it as its error state.
Future<void> _reload(WidgetRef ref) async {
  final reloaded = ref.refresh(gardenProvider.future);
  try {
    await reloaded;
  } catch (_) {
    // Rendered by the error state.
  }
}

/// Runs a mutation, refreshes the garden, and reports the outcome. [action]
/// may return a message that replaces [done] (a partial success).
///
/// Completes only once the refresh has landed, so a task tile keeps its
/// buttons disabled until the list no longer shows the finished task (todo
/// 570 #9).
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
  } catch (_) {
    // Anything else (a response that does not parse, say) must still be
    // reported, and the list still refreshed, rather than escape the
    // button's handler (todo 570 #5).
    message = 'That did not work. Please try again.';
  }
  messenger.showSnackBar(SnackBar(content: Text(message)));
  // A WidgetRef is dead once its widget is gone (the user navigated away
  // mid-request); the next visit fetches fresh anyway.
  if (context.mounted) await _reload(ref);
}

/// CareTask.title's `max_length` on the server.
const int careTaskTitleMaxLength = 200;

/// The title of a task scheduled from the add-task form: the type label,
/// a space and the plant name, cut to [careTaskTitleMaxLength]. A plant name may be 200 characters
/// itself, and an over-long title is a 400 (todo 570 #4, #7).
@visibleForTesting
String careTaskTitle(String typeLabel, String plantName) {
  final title = '$typeLabel $plantName';
  if (title.length <= careTaskTitleMaxLength) return title;
  return '${title.substring(0, careTaskTitleMaxLength - 1).trimRight()}…';
}

/// When a task first due on [day] is due: 9 am local on that calendar day
/// (a reminder at midnight would arrive while the owner sleeps), or [now]
/// if 9 am that day has already passed. Built from the date's fields rather
/// than midnight plus nine hours, which lands at 8 or 10 am on a
/// daylight-saving change day (todo 570 #10).
@visibleForTesting
DateTime firstDueAt(DateTime day, {required DateTime now}) {
  final nineAm = DateTime(day.year, day.month, day.day, 9);
  return nineAm.isBefore(now) ? now : nineAm;
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
              title: careTaskTitle(
                houseplantTaskTypes[_type] ?? _type,
                widget.plant.commonName,
              ),
              when: firstDueAt(_date, now: DateTime.now()),
              repeatDays: _repeat,
            ),
          ),
          child: const Text('Schedule'),
        ),
      ],
    );
  }
}
