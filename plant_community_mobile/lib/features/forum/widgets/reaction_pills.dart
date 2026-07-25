import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../services/forum_api.dart' show forumReactionTypes;

/// Emoji for each reaction type (display-only mapping, mirrors the web).
const Map<String, String> _reactionEmoji = {
  'like': '👍',
  'love': '❤️',
  'helpful': '💡',
  'thanks': '🙏',
};

/// Renders a post's reactions as pills (only non-zero counts show), plus — when
/// [onReact] is provided (logged in) — an "add reaction" button. Pills the
/// current user has active are highlighted. When [onReact] is null the pills
/// are display-only.
class ReactionPills extends StatelessWidget {
  const ReactionPills({
    super.key,
    required this.counts,
    required this.reacted,
    this.onReact,
  });

  final Map<String, int> counts;
  final List<String> reacted;
  final void Function(String type)? onReact;

  @override
  Widget build(BuildContext context) {
    final active = forumReactionTypes
        .where((type) => (counts[type] ?? 0) > 0)
        .toList();
    if (active.isEmpty && onReact == null) return const SizedBox.shrink();

    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final type in active)
          _Pill(
            type: type,
            count: counts[type] ?? 0,
            isReacted: reacted.contains(type),
            onTap: onReact == null ? null : () => onReact!(type),
          ),
        if (onReact != null) _AddReactionButton(onReact: onReact!),
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.type,
    required this.count,
    required this.isReacted,
    this.onTap,
  });

  final String type;
  final int count;
  final bool isReacted;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final emoji = _reactionEmoji[type] ?? '•';
    return Semantics(
      button: onTap != null,
      selected: isReacted,
      label: '$type $count',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.rPill),
        // Keep the pill compact but guarantee a 48x48 tap target (Material 3).
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
          child: Center(
            widthFactor: 1,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: isReacted
                    ? theme.colorScheme.primaryContainer
                    : theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(AppSpacing.rPill),
                border: isReacted
                    ? Border.all(color: theme.colorScheme.primary)
                    : null,
              ),
              child: Text(
                '$emoji $count',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: isReacted
                      ? theme.colorScheme.onPrimaryContainer
                      : theme.colorScheme.onSurfaceVariant,
                  fontWeight: isReacted ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AddReactionButton extends StatelessWidget {
  const _AddReactionButton({required this.onReact});
  final void Function(String type) onReact;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PopupMenuButton<String>(
      tooltip: 'Add reaction',
      onSelected: onReact,
      itemBuilder: (context) => [
        for (final type in forumReactionTypes)
          PopupMenuItem<String>(
            value: type,
            child: Text('${_reactionEmoji[type] ?? ''}  $type'),
          ),
      ],
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
        child: Center(
          widthFactor: 1,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(AppSpacing.rPill),
            ),
            child: Icon(
              Icons.add_reaction_outlined,
              size: 18,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ),
    );
  }
}
