import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../services/forum_api.dart';

/// What the report sheet hands back: a backend reason value plus optional
/// free-text detail.
class ForumReportChoice {
  const ForumReportChoice({required this.reason, this.detail});
  final String reason;
  final String? detail;
}

/// Open the report bottom sheet: pick one of [forumReportReasons],
/// optionally add detail. Resolves `null` on cancel/dismiss, a
/// [ForumReportChoice] on submit — the caller makes the API call, so the
/// sheet itself has no async state. Shared by the DM thread (todo 339) and
/// the post card (todo 341); [title]/[prompt] name the thing being reported.
Future<ForumReportChoice?> showForumReportSheet(
  BuildContext context, {
  required String title,
  required String prompt,
}) {
  return showModalBottomSheet<ForumReportChoice>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _ReportSheet(title: title, prompt: prompt),
  );
}

class _ReportSheet extends StatefulWidget {
  const _ReportSheet({required this.title, required this.prompt});

  final String title;
  final String prompt;

  @override
  State<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends State<_ReportSheet> {
  String? _reason;
  final _detailController = TextEditingController();

  @override
  void dispose() {
    _detailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          MediaQuery.viewInsetsOf(context).bottom + AppSpacing.md,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.title,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                widget.prompt,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final reason in forumReportReasons)
                    ChoiceChip(
                      label: Text(reason.label),
                      selected: _reason == reason.value,
                      onSelected: (_) => setState(() => _reason = reason.value),
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _detailController,
                maxLength: 280,
                maxLines: 3,
                minLines: 1,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Details (optional)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  FilledButton(
                    onPressed: _reason == null
                        ? null
                        : () {
                            final reason = _reason;
                            if (reason == null) return;
                            final detail = _detailController.text.trim();
                            Navigator.of(context).pop(
                              ForumReportChoice(
                                reason: reason,
                                detail: detail.isEmpty ? null : detail,
                              ),
                            );
                          },
                    child: const Text('Report'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
