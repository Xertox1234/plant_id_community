import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/green_thumb_extension.dart';
import '../../../../shared/widgets/canopy_accents.dart';
import '../../../../shared/widgets/clay_button.dart';
import '../../forum_format.dart';
import '../../models/models.dart';
import '../../providers/forum_providers.dart';
import '../author_identity.dart';
import '../forum_avatar_cluster.dart';

/// Hard cap on items in an expanded activity card, the solution included
/// (owner decision 2026-11-02, design spec §6.4).
const int kLatestRepliesMax = 3;

/// The body of an expanded activity card: the solution and the newest replies
/// (at most [kLatestRepliesMax] items), "+N more replies", who is in the
/// thread, and an "Open topic" button that works in every state.
///
/// Fetched on first build (first expand) through the keepAlive
/// [latestRepliesProvider], so collapsing and reopening does not refetch.
class ForumLatestRepliesView extends ConsumerWidget {
  const ForumLatestRepliesView({
    super.key,
    required this.topicId,
    required this.onOpen,
  });

  final int topicId;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(latestRepliesProvider(topicId));
    // Riverpod 3 retries a failed build on its own, reporting
    // AsyncLoading(error) meanwhile: show the failure (with Retry) from the
    // first error rather than a skeleton through every automatic retry.
    final value = async.value;
    final Widget state;
    if (value != null) {
      state = value.isEmpty
          ? const _Line(key: ValueKey('empty'), text: 'No replies yet')
          : _Loaded(key: const ValueKey('data'), data: value);
    } else if (async.hasError) {
      state = _Failed(
        key: const ValueKey('error'),
        onRetry: () => ref.invalidate(latestRepliesProvider(topicId)),
      );
    } else {
      state = const _Skeleton(key: ValueKey('loading'));
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Opacity only, so it stays under reduced motion (spec §8.3).
        AnimatedSwitcher(
          duration: Durations.short4,
          layoutBuilder: (current, previous) => Stack(
            alignment: Alignment.topLeft,
            children: [...previous, ?current],
          ),
          child: state,
        ),
        const SizedBox(height: 14),
        ClayButton(label: 'Open topic', fullWidth: true, onPressed: onOpen),
      ],
    );
  }
}

String _name(ForumAuthor a) =>
    a.displayName.trim().isEmpty ? a.username : a.displayName.trim();

String _firstName(ForumAuthor a) => _name(a).split(RegExp(r'\s+')).first;

class _Loaded extends StatelessWidget {
  const _Loaded({super.key, required this.data});

  final ForumLatestReplies data;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final solution = data.solution;
    final room = kLatestRepliesMax - (solution == null ? 0 : 1);
    final replies = data.replies.take(room).toList(growable: false);
    // The server already caps and counts what it left out; anything this cap
    // drops on top (an older server sending more) is still "more".
    final more = data.moreCount + (data.replies.length - replies.length);
    final count = data.participantCount;
    final started = data.startedBy;
    final people = [
      '$count ${count == 1 ? 'person' : 'people'} in this thread',
      if (started != null) 'started by ${_firstName(started)}',
    ].join(' · ');
    final muted = AppTypography.meta.copyWith(color: canopy.ink2);

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (solution != null) _ReplyRow(reply: solution, isSolution: true),
        for (final reply in replies) ...[
          if (solution != null || reply != replies.first)
            const SizedBox(height: 12),
          _ReplyRow(reply: reply),
        ],
        if (more > 0) ...[
          const SizedBox(height: 12),
          Text('+$more more ${more == 1 ? 'reply' : 'replies'}', style: muted),
        ],
        if (count > 0) ...[
          const SizedBox(height: 14),
          Row(
            children: [
              if (data.participants.isNotEmpty) ...[
                AuthorAvatarCluster(
                  authors: data.participants,
                  max: 5,
                  radius: 12,
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Expanded(child: Text(people, style: muted)),
            ],
          ),
        ],
      ],
    );
  }
}

class _ReplyRow extends StatelessWidget {
  const _ReplyRow({required this.reply, this.isSolution = false});

  final ForumLatestReply reply;
  final bool isSolution;

  @override
  Widget build(BuildContext context) {
    final canopy = context.canopy;
    final time = forumRelativeTime(reply.createdAt);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AuthorAvatar(author: reply.author, radius: 14),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // A Wrap: at large text the time and tag drop under the name.
              Wrap(
                spacing: 6,
                runSpacing: 2,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    _name(reply.author),
                    style: AppTypography.meta.copyWith(
                      color: Theme.of(context).colorScheme.onSurface,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (time.isNotEmpty)
                    Text(
                      time,
                      style: AppTypography.label.copyWith(color: canopy.ink3),
                    ),
                  if (isSolution)
                    CanopyChip(label: 'Solution', tone: canopy.leaf),
                ],
              ),
              const SizedBox(height: 3),
              Text(
                reply.excerpt,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.meta.copyWith(color: canopy.ink2),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: AppTypography.meta.copyWith(color: context.canopy.ink2),
  );
}

class _Failed extends StatelessWidget {
  const _Failed({super.key, required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.xs,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text(
          "Couldn't load replies",
          style: AppTypography.meta.copyWith(color: context.canopy.ink2),
        ),
        ClayButton(
          label: 'Retry',
          size: ClayButtonSize.small,
          variant: ClayButtonVariant.ghost,
          onPressed: onRetry,
        ),
      ],
    );
  }
}

/// Two reply-shaped lines in place of the replies while they load.
class _Skeleton extends StatelessWidget {
  const _Skeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final fill = context.canopy.surface3;
    Widget bar(double widthFactor, double height) => FractionallySizedBox(
      alignment: Alignment.centerLeft,
      widthFactor: widthFactor,
      child: SizedBox(
        height: height,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: fill,
            borderRadius: BorderRadius.circular(AppSpacing.rPill),
          ),
        ),
      ),
    );
    Widget line(double width) => Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox.square(
          dimension: 28,
          child: DecoratedBox(
            decoration: BoxDecoration(color: fill, shape: BoxShape.circle),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [bar(0.4, 10), const SizedBox(height: 6), bar(width, 10)],
          ),
        ),
      ],
    );
    return Semantics(
      label: 'Loading replies',
      child: ExcludeSemantics(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [line(0.9), const SizedBox(height: 12), line(0.7)],
        ),
      ),
    );
  }
}
