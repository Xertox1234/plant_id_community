import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';

/// The authenticated user's notifications: cursor-paginated, newest first.
/// Tapping a row marks it read and opens its topic. Mirrors the web bell's
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
            onOpen: (n) => _openNotification(context, ref, n),
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

  Future<void> _openNotification(
    BuildContext context,
    WidgetRef ref,
    ForumNotification notification,
  ) async {
    if (!notification.isRead) {
      // Best-effort: a failed mark-read must not block opening the topic —
      // mirrors the web bell (NotificationBell.tsx), which fires this
      // unawaited and swallows the error, leaving the row unread for the
      // next poll rather than stalling the tap's primary action.
      try {
        await ref
            .read(notificationsFeedProvider.notifier)
            .markRead(id: notification.id);
      } catch (_) {
        // Ignored — see comment above.
      }
    }
    final topic = notification.topic;
    if (topic == null || !context.mounted) return;
    final postId = notification.postId;
    context.pushNamed(
      'forumTopic',
      pathParameters: {'id': '${topic.id}'},
      queryParameters: postId == null ? {} : {'postId': '$postId'},
      extra: topic.title,
    );
  }
}

class _NotificationsList extends StatelessWidget {
  const _NotificationsList({
    required this.paged,
    required this.onOpen,
    required this.onLoadMore,
  });

  final PagedList<ForumNotification> paged;
  final void Function(ForumNotification) onOpen;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) {
      return const Center(child: Text('No notifications yet.'));
    }
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: paged.items.length + (paged.hasMore ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (index >= paged.items.length) {
          return _LoadMoreButton(
            isLoading: paged.isLoadingMore,
            onLoadMore: onLoadMore,
          );
        }
        final notification = paged.items[index];
        return _NotificationTile(
          notification: notification,
          onTap: () => onOpen(notification),
        );
      },
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.notification, required this.onTap});

  final ForumNotification notification;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      color: notification.isRead
          ? null
          : theme.colorScheme.primaryContainer.withValues(alpha: 0.25),
      child: ListTile(
        onTap: onTap,
        leading: Icon(
          _iconFor(notification.verb),
          color: theme.colorScheme.primary,
        ),
        title: Text(_labelFor(notification)),
        subtitle: forumRelativeTime(notification.createdAt).isNotEmpty
            ? Text(forumRelativeTime(notification.createdAt))
            : null,
        trailing: notification.isRead
            ? null
            : Icon(Icons.circle, size: 10, color: theme.colorScheme.primary),
      ),
    );
  }
}

/// Copy per `NotificationVerb` (`reply` | `mention` | `quote` | `solution`
/// — `wagtail_forum/models/notifications.py`). An unrecognized verb falls
/// back to a generic line rather than throwing, so an older-client/newer-
/// backend skew degrades gracefully.
String _labelFor(ForumNotification notification) {
  final actorName = notification.actor.name;
  final topicTitle = notification.topic?.title;
  switch (notification.verb) {
    case 'mention':
      return topicTitle != null
          ? '$actorName mentioned you in "$topicTitle"'
          : '$actorName mentioned you';
    case 'quote':
      // Opens like a reply: `post_id` is the QUOTING post (todo 342).
      return topicTitle != null
          ? '$actorName quoted your post in "$topicTitle"'
          : '$actorName quoted your post';
    case 'solution':
      return topicTitle != null
          ? '$actorName marked your reply as the answer in "$topicTitle"'
          : '$actorName marked your reply as the answer';
    case 'reply':
      return topicTitle != null
          ? '$actorName replied to "$topicTitle"'
          : '$actorName replied to your topic';
    default:
      return topicTitle != null
          ? '$actorName — activity in "$topicTitle"'
          : '$actorName — new forum activity';
  }
}

IconData _iconFor(String verb) {
  switch (verb) {
    case 'mention':
      return Icons.alternate_email;
    case 'quote':
      return Icons.format_quote_outlined;
    case 'solution':
      return Icons.check_circle_outline;
    case 'reply':
      return Icons.reply;
    default:
      return Icons.notifications_none;
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
