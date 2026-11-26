import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../shared/widgets/canopy_surfaces.dart';
import '../models/models.dart';

/// Asks for the poll's closing date, then its time. `null` when either
/// picker is dismissed.
Future<DateTime?> pickForumPollCloseTime(BuildContext context) async {
  final now = DateTime.now();
  final date = await showDatePicker(
    context: context,
    initialDate: now.add(const Duration(days: 7)),
    firstDate: now,
    lastDate: now.add(const Duration(days: 365)),
    helpText: 'Poll closes on',
  );
  if (date == null || !context.mounted) return null;
  final time = await showTimePicker(
    context: context,
    initialTime: TimeOfDay.fromDateTime(now),
    helpText: 'Poll closes at',
  );
  if (time == null) return null;
  return DateTime(date.year, date.month, date.day, time.hour, time.minute);
}

/// The poll form inside the new-topic composer: a question, two to ten
/// options, how many a voter may pick and when it closes. The web twin is
/// the "Add a poll" section of `NewThreadPage.tsx`.
///
/// Owns the text fields and reports every change as a [ForumPollDraft];
/// the composer decides whether it may be posted. The composer hands the
/// draft back as [initial]: the form is one row of a lazy list, so scrolling
/// it far off screen disposes this state and it must come back as it was.
class PollDraftForm extends StatefulWidget {
  const PollDraftForm({
    super.key,
    required this.initial,
    required this.onChanged,
    required this.onRemove,
    this.pickCloseTime = pickForumPollCloseTime,
    this.enabled = true,
  });

  final ForumPollDraft initial;
  final ValueChanged<ForumPollDraft> onChanged;
  final VoidCallback onRemove;
  final Future<DateTime?> Function(BuildContext context) pickCloseTime;

  /// False locks every control, as while the composer's submit is in flight
  /// (audit F116).
  final bool enabled;

  @override
  State<PollDraftForm> createState() => _PollDraftFormState();
}

class _PollDraftFormState extends State<PollDraftForm> {
  late final _question = TextEditingController(text: widget.initial.question);
  late final List<TextEditingController> _options = [
    for (final option in widget.initial.options)
      TextEditingController(text: option),
  ];
  late DateTime? _closesAt = widget.initial.closesAt;
  late int _maxChoices = widget.initial.maxChoices;

  ForumPollDraft get _draft => ForumPollDraft(
    question: _question.text,
    options: [for (final option in _options) option.text],
    closesAt: _closesAt,
    maxChoices: _maxChoices,
  );

  void _changed() {
    setState(() {});
    widget.onChanged(_draft);
  }

  void _addOption() {
    _options.add(TextEditingController());
    _changed();
  }

  Future<void> _pickClose() async {
    final picked = await widget.pickCloseTime(context);
    if (picked == null || !mounted) return;
    _closesAt = picked;
    _changed();
  }

  @override
  void dispose() {
    _question.dispose();
    for (final option in _options) {
      option.dispose();
    }
    super.dispose();
  }

  static String _choiceLabel(int count) =>
      count == 1 ? '1 option' : 'Up to $count options';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final draft = _draft;
    final filled = draft.filledOptions.length;
    final muted = theme.textTheme.bodyMedium?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );
    final closesAt = _closesAt;

    return CanopyCard(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.xs,
        AppSpacing.md,
        AppSpacing.xs,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text('Poll', style: theme.textTheme.titleMedium)),
              IconButton(
                tooltip: 'Remove poll',
                icon: const Icon(LucideIcons.x, size: 20),
                onPressed: widget.enabled ? widget.onRemove : null,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          TextField(
            controller: _question,
            enabled: widget.enabled,
            decoration: const InputDecoration(
              labelText: 'Question',
              border: OutlineInputBorder(),
            ),
            textCapitalization: TextCapitalization.sentences,
            textInputAction: TextInputAction.next,
            inputFormatters: [
              LengthLimitingTextInputFormatter(
                ForumPollDraft.questionMaxLength,
              ),
            ],
            onChanged: (_) => _changed(),
          ),
          for (var i = 0; i < _options.length; i++) ...[
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _options[i],
              enabled: widget.enabled,
              decoration: InputDecoration(
                labelText: 'Option ${i + 1}',
                border: const OutlineInputBorder(),
              ),
              textCapitalization: TextCapitalization.sentences,
              textInputAction: TextInputAction.next,
              inputFormatters: [
                LengthLimitingTextInputFormatter(
                  ForumPollDraft.optionMaxLength,
                ),
              ],
              onChanged: (_) => _changed(),
            ),
          ],
          if (_options.length < ForumPollDraft.maxOptions) ...[
            const SizedBox(height: AppSpacing.sm),
            OutlinedButton.icon(
              onPressed: widget.enabled ? _addOption : null,
              icon: const Icon(LucideIcons.plus),
              label: const Text('Add option'),
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          const Divider(height: 1),
          PopupMenuButton<int>(
            tooltip: 'How many options a voter can pick',
            enabled: widget.enabled,
            onSelected: (count) {
              _maxChoices = count;
              _changed();
            },
            itemBuilder: (_) => [
              for (var count = 1; count <= (filled < 1 ? 1 : filled); count++)
                PopupMenuItem(value: count, child: Text(_choiceLabel(count))),
            ],
            child: _SettingRow(
              label: 'Voters can pick',
              value: Text(
                _choiceLabel(draft.effectiveMaxChoices),
                style: muted,
              ),
            ),
          ),
          const Divider(height: 1),
          InkWell(
            onTap: widget.enabled ? _pickClose : null,
            child: _SettingRow(
              label: 'Closes',
              value: closesAt == null
                  ? Text('Never', style: muted)
                  : Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          DateFormat('d MMM, h:mm a').format(closesAt),
                          style: muted,
                        ),
                        IconButton(
                          tooltip: 'Clear closing time',
                          icon: const Icon(LucideIcons.x, size: 18),
                          onPressed: widget.enabled
                              ? () {
                                  _closesAt = null;
                                  _changed();
                                }
                              : null,
                        ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

/// One tappable setting line: its name on the left, its value on the right.
class _SettingRow extends StatelessWidget {
  const _SettingRow({required this.label, required this.value});

  final String label;
  final Widget value;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 48),
      child: Row(
        children: [
          Expanded(
            child: Text(label, style: Theme.of(context).textTheme.bodyMedium),
          ),
          value,
        ],
      ),
    );
  }
}
