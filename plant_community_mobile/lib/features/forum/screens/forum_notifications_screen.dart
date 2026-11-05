import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/canopy_palette.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../shared/widgets/canopy_surfaces.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/author_identity.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';

/// The authenticated user's notifications: cursor-paginated, newest first,
/// split into "New" (unread) and "Earlier" (read). Consecutive rows with the
/// same actor, verb and topic fold into one card ("7 replies"); tapping it
/// marks every row in it read and opens the newest. Mirrors the web bell's
/// wording (`NotificationBell.tsx`) — this is a deliberate third copy home,
/// same rationale as that file's own header comment: the client can't import
/// `backend/apps/forum_host/notification_copy.py`.
class ForumNotificationsScreen extends ConsumerWidget {
  const ForumNotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notificationsAsync = ref.watch(notificationsFeedProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton(
            onPressed: () => _markAllRead(context, ref),
            child: const Text('Mark all read'),
          ),
        ],
      ),
      body: SafeArea(
        child: notificationsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _ErrorRetry(
            message: 'Could not load notifications.',
            onRetry: () => ref.invalidate(notificationsFeedProvider),
          ),
          data: (paged) => _NotificationsList(
            paged: paged,
            onOpen: (group) => _openGroup(context, ref, group),
            onLoadMore: () =>
                ref.read(notificationsFeedProvider.notifier).loadMore(),
          ),
        ),
      ),
    );
  }

  Future<void> _markAllRead(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(notificationsFeedProvider.notifier).markRead();
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not mark all as read.')),
        );
      }
    }
  }

  Future<void> _openGroup(
    BuildContext context,
    WidgetRef ref,
    NotificationGroup group,
  ) async {
    final unreadIds = group.unreadIds;
    if (unreadIds.isNotEmpty) {
      // Best-effort: a failed mark-read must not block opening the topic —
      // mirrors the web bell (NotificationBell.tsx), which fires this
      // unawaited and swallows the error, leaving the row unread for the
      // next poll rather than stalling the tap's primary action.
      try {
        await ref
            .read(notificationsFeedProvider.notifier)
            .markRead(ids: unreadIds);
      } catch (_) {
        // Ignored — see comment above.
      }
    }
    final latest = group.latest;
    final topic = latest.topic;
    if (topic == null || !context.mounted) return;
    final postId = latest.postId;
    context.pushNamed(
      'forumTopic',
      pathParameters: {'id': '${topic.id}'},
      queryParameters: postId == null ? {} : {'postId': '$postId'},
      extra: topic.title,
    );
  }
}

/// A run of consecutive notifications shown as one card. [items] is newest
/// first, so [latest] is the one a tap opens.
@visibleForTesting
class NotificationGroup {
  const NotificationGroup(this.items);

  final List<ForumNotification> items;

  ForumNotification get latest => items.first;
  bool get isUnread => items.any((n) => !n.isRead);
  List<int> get unreadIds => [
    for (final n in items)
      if (!n.isRead) n.id,
  ];
}

/// Folds consecutive notifications that share a verb, actor and topic into
/// one group. Only neighbours fold — a later reply from someone else breaks
/// the run, so the list stays in true newest-first order. A notification
/// with no topic never folds: there is nothing to say it is "the same" one.
@visibleForTesting
List<NotificationGroup> groupNotifications(List<ForumNotification> items) {
  final groups = <List<ForumNotification>>[];
  for (final n in items) {
    final run = groups.isEmpty ? null : groups.last;
    final prev = run?.last;
    final folds =
        prev != null &&
        n.topic != null &&
        prev.topic?.id == n.topic!.id &&
        prev.verb == n.verb &&
        prev.actor.username == n.actor.username;
    if (folds) {
      run!.add(n);
    } else {
      groups.add([n]);
    }
  }
  return [for (final g in groups) NotificationGroup(g)];
}

class _NotificationsList extends StatelessWidget {
  const _NotificationsList({
    required this.paged,
    required this.onOpen,
    required this.onLoadMore,
  });

  final PagedList<ForumNotification> paged;
  final void Function(NotificationGroup) onOpen;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) return const _EmptyState();

    // Partition before grouping so a run never straddles New and Earlier.
    final unread = groupNotifications([
      for (final n in paged.items)
        if (!n.isRead) n,
    ]);
    final read = groupNotifications([
      for (final n in paged.items)
        if (n.isRead) n,
    ]);
    final rows = <Widget>[
      if (unread.isNotEmpty) ...[
        const _SectionLabel('New'),
        for (final g in unread)
          _NotificationCard(group: g, onTap: () => onOpen(g)),
      ],
      if (read.isNotEmpty) ...[
        _SectionLabel('Earlier', first: unread.isEmpty),
        for (final g in read)
          _NotificationCard(group: g, onTap: () => onOpen(g)),
      ],
      if (paged.hasMore)
        _LoadMoreButton(isLoading: paged.isLoadingMore, onLoadMore: onLoadMore),
    ];

    return ListView.separated(
      padding:
          const EdgeInsets.all(AppSpacing.md) +
          MainShell.fabClearanceOf(context),
      itemCount: rows.length,
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, index) => rows[index],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text, {this.first = true});

  final String text;

  /// The first label sits flush; a later one gets breathing room above.
  final bool first;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        top: first ? 0 : AppSpacing.md,
        left: AppSpacing.xs,
      ),
      child: Semantics(
        header: true,
        child: Text(
          text.toUpperCase(),
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            letterSpacing: 0.06 * 11,
            color: context.canopy.ink3,
          ),
        ),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.group, required this.onTap});

  final NotificationGroup group;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ext = context.canopy;
    final latest = group.latest;
    final style = _styleFor(latest.verb);
    final unread = group.isUnread;
    final message = _messageFor(latest);
    final time = forumRelativeTime(latest.createdAt);
    final count = group.items.length;
    final meta = [
      if (time.isNotEmpty) time,
      if (count > 1) '$count ${style.plural}',
    ].join(' · ');

    final baseStyle = theme.textTheme.bodyMedium?.copyWith(
      color: unread ? theme.colorScheme.onSurface : ext.ink2,
      height: 1.35,
    );
    final strong = TextStyle(
      fontWeight: FontWeight.w600,
      color: theme.colorScheme.onSurface,
    );

    return CanopyCard(
      onTap: onTap,
      accentBorder: unread ? theme.colorScheme.secondary : null,
      padding: const EdgeInsets.all(AppSpacing.md),
      semanticLabel: [
        if (unread) 'Unread.',
        message.plain,
        if (meta.isNotEmpty) meta,
      ].join(' '),
      child: ExcludeSemantics(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _ActorAvatar(
              actor: latest.actor,
              badgeIcon: style.icon,
              badgeTone: style.tone,
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(
                      style: baseStyle,
                      children: [
                        TextSpan(text: message.actor, style: strong),
                        TextSpan(text: message.before),
                        if (message.topic != null)
                          TextSpan(text: message.topic, style: strong),
                        if (message.after != null)
                          TextSpan(text: message.after),
                      ],
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (meta.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      meta,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: ext.ink3,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (unread)
              Padding(
                padding: const EdgeInsets.only(
                  left: AppSpacing.sm,
                  top: AppSpacing.xs,
                ),
                child: Container(
                  key: const ValueKey('notification-unread-dot'),
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: ext.berry,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// The actor's avatar with the verb's tile tone as a badge on its corner.
/// With no avatar image the disc is the actor's initial on a tile gradient
/// picked from their username, so a person keeps one colour down the list —
/// the shared [AuthorAvatar] fallback is a small grey initial, too quiet at
/// this size.
class _ActorAvatar extends StatelessWidget {
  const _ActorAvatar({
    required this.actor,
    required this.badgeIcon,
    required this.badgeTone,
  });

  final ForumAuthor actor;
  final IconData badgeIcon;
  final CanopyTileTone badgeTone;

  static const double _size = 46;
  static const double _badge = 22;

  @override
  Widget build(BuildContext context) {
    final avatar = actor.avatar;
    final Widget disc;
    if (avatar != null && avatar.isNotEmpty) {
      disc = AuthorAvatar(author: actor, radius: _size / 2);
    } else {
      // A stable sum of code units, not String.hashCode, which Dart does
      // not promise to keep across runs.
      final tones = CanopyTileTone.values;
      final tone =
          tones[actor.username.codeUnits.fold(0, (a, b) => a + b) %
              tones.length];
      final initial = actor.isDeleted || actor.name.isEmpty
          ? '?'
          : actor.name.characters.first.toUpperCase();
      disc = Container(
        width: _size,
        height: _size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: tone.colors,
          ),
        ),
        child: Text(
          initial,
          style: const TextStyle(
            fontSize: 19,
            fontWeight: FontWeight.w600,
            color: CanopyRamp.abyss,
          ),
        ),
      );
    }

    return SizedBox(
      width: _size + 4,
      height: _size + 4,
      child: Stack(
        children: [
          disc,
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              width: _badge,
              height: _badge,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: badgeTone.colors,
                ),
                // A ring in the card's own colour cuts the badge out of
                // the disc, the way iOS badges sit on an avatar.
                border: Border.all(
                  color: Theme.of(context).colorScheme.surface,
                  width: 2,
                ),
              ),
              child: Icon(badgeIcon, size: 11, color: CanopyRamp.abyss),
            ),
          ),
        ],
      ),
    );
  }
}

/// A notification's sentence, split so the actor and topic can be bold:
/// `actor + before + topic + after`.
typedef _Message = ({
  String actor,
  String before,
  String? topic,
  String? after,
  String plain,
});

/// Copy per `NotificationVerb` (`reply` | `mention` | `quote` | `solution`
/// | `new_topic` — `wagtail_forum/models/notifications.py`). An unrecognized
/// verb falls back to a generic line rather than throwing, so an
/// older-client/newer-backend skew degrades gracefully.
_Message _messageFor(ForumNotification notification) {
  final actor = notification.actor.name;
  final topic = notification.topic?.title;
  final (
    String withTopic,
    String? after,
    String noTopic,
  ) = switch (notification.verb) {
    'mention' => (' mentioned you in ', null, ' mentioned you'),
    // Opens like a reply: `post_id` is the QUOTING post (todo 342).
    'quote' => (' quoted your post in ', null, ' quoted your post'),
    'solution' => (
      ' marked your reply as the answer in ',
      null,
      ' marked your reply as the answer',
    ),
    // A new topic in a forum the member watches (todo 672).
    'new_topic' => (
      ' started ',
      ' in a forum you watch',
      ' started a topic in a forum you watch',
    ),
    'reply' => (' replied to ', null, ' replied to your topic'),
    _ => (' — activity in ', null, ' — new forum activity'),
  };
  if (topic == null) {
    return (
      actor: actor,
      before: noTopic,
      topic: null,
      after: null,
      plain: '$actor$noTopic',
    );
  }
  return (
    actor: actor,
    before: withTopic,
    topic: topic,
    after: after,
    plain: '$actor$withTopic"$topic"${after ?? ''}',
  );
}

/// Each verb's badge colour, icon, and the noun a folded card counts in.
/// Tones follow the board tiles on the forum home: sage for conversation,
/// orchid for you personally, bloom for your words reused, pollen for the
/// gold-star moment.
({IconData icon, CanopyTileTone tone, String plural}) _styleFor(String verb) {
  return switch (verb) {
    'mention' => (
      icon: LucideIcons.atSign,
      tone: CanopyTileTone.orchid,
      plural: 'mentions',
    ),
    'quote' => (
      icon: LucideIcons.quote,
      tone: CanopyTileTone.bloom,
      plural: 'quotes',
    ),
    'solution' => (
      icon: LucideIcons.circleCheck,
      tone: CanopyTileTone.pollen,
      plural: 'answers',
    ),
    'new_topic' => (
      icon: LucideIcons.messageSquarePlus,
      tone: CanopyTileTone.sage,
      plural: 'new topics',
    ),
    'reply' => (
      icon: LucideIcons.reply,
      tone: CanopyTileTone.sage,
      plural: 'replies',
    ),
    _ => (icon: LucideIcons.bell, tone: CanopyTileTone.sage, plural: 'updates'),
  };
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ext = context.canopy;
    return Center(
      child: Padding(
        padding: EdgeInsets.all(ext.padScreen),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CanopyTile(icon: LucideIcons.bellRing),
            SizedBox(height: ext.gapY),
            Text("You're all caught up", style: theme.textTheme.titleMedium),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Replies, mentions and answers to your posts will show up here.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(color: ext.ink3),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoadMoreButton extends StatelessWidget {
  const _LoadMoreButton({required this.isLoading, required this.onLoadMore});
  final bool isLoading;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Center(
        child: isLoading
            ? const CircularProgressIndicator()
            : OutlinedButton(
                onPressed: () async {
                  try {
                    await onLoadMore();
                  } catch (_) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Could not load more.')),
                      );
                    }
                  }
                },
                child: const Text('Load more'),
              ),
      ),
    );
  }
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message),
          const SizedBox(height: AppSpacing.sm),
          OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
