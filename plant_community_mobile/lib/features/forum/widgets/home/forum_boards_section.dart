import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_accents.dart';
import '../../models/models.dart';
import '../../utils/board_identity.dart';

/// The forum home's boards: one grouped card, a row per board. The whole row
/// is the tap target (>= 48pt), and its press feedback is a `surface3`
/// highlight rather than a scale (design spec §8.1).
class ForumBoardsSection extends StatelessWidget {
  const ForumBoardsSection({
    super.key,
    required this.boards,
    required this.onTap,
  });

  final List<ForumBoard> boards;
  final void Function(ForumBoard board) onTap;

  @override
  Widget build(BuildContext context) {
    return CanopyGroupedCard(
      rows: [
        for (final board in boards)
          _BoardRow(board: board, onTap: () => onTap(board)),
      ],
    );
  }
}

String _count(int n, String singular) => '$n $singular${n == 1 ? '' : 's'}';

class _BoardRow extends StatelessWidget {
  const _BoardRow({required this.board, required this.onTap});

  final ForumBoard board;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canopy = context.canopy;
    final identity = boardIdentity(board.slug, fallbackLabel: board.title);
    final counts =
        '${_count(board.topicCount, 'topic')} · '
        '${_count(board.postCount, 'post')}';
    return CanopyPressable(
      onTap: onTap,
      style: CanopyPressStyle.highlight,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 12,
        ),
        child: Row(
          children: [
            CanopyAccentTile(
              icon: identity.icon,
              tone: identity.tone.colorOf(canopy),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    board.title,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (board.description.isNotEmpty)
                    Text(
                      board.description,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.bodySm.copyWith(color: canopy.ink2),
                    ),
                  const SizedBox(height: 2),
                  Text(
                    counts,
                    style: AppTypography.mono.copyWith(color: canopy.ink3),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Icon(LucideIcons.chevronRight, size: 18, color: canopy.ink3),
          ],
        ),
      ),
    );
  }
}
