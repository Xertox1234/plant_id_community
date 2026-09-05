import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../widgets/author_identity.dart';
import '../widgets/forum_avatar_cluster.dart';

/// The authenticated user's DM inbox (todo 339): one row per conversation,
/// most recent activity first, unread rows emphasised with a count chip.
/// Tapping a row opens the thread with that member — or, for a group
/// (todo 350), the group thread by id.
class ForumConversationsScreen extends ConsumerWidget {
  const ForumConversationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final conversationsAsync = ref.watch(conversationsFeedProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Messages'),
        actions: [
          IconButton(
            tooltip: 'New group',
            icon: const Icon(Icons.group_add_outlined),
            onPressed: () => context.pushNamed('forumNewGroup'),
          ),
        ],
      ),
      body: SafeArea(
        child: conversationsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _ErrorRetry(
            message: 'Could not load your messages.',
            onRetry: () => ref.invalidate(conversationsFeedProvider),
          ),
          data: (paged) => RefreshIndicator(
            onRefresh: () async {
              // invalidate + await the future is `ref.refresh` spelled out
              // (that helper is @useResult, and the value isn't needed here).
              ref.invalidate(conversationsFeedProvider);
              try {
                await ref.read(conversationsFeedProvider.future);
              } catch (_) {
                // The provider now holds the error and the `error` branch
                // above renders Retry — a rejected future must not also
                // escape RefreshIndicator as an unhandled async error.
              }
            },
            child: _ConversationsList(
              paged: paged,
              onOpen: (c) => c.isGroup
                  ? context.pushNamed(
                      'forumGroupConversation',
                      pathParameters: {'id': '${c.id}'},
                    )
                  : context.pushNamed(
                      'forumConversation',
                      pathParameters: {
                        'username':
                            c.otherParticipant?.username ??
                            ForumAuthor.deletedUsername,
                      },
                    ),
              onLoadMore: () =>
                  ref.read(conversationsFeedProvider.notifier).loadMore(),
            ),
          ),
        ),
      ),
    );
  }
}

class _ConversationsList extends StatelessWidget {
  const _ConversationsList({
    required this.paged,
    required this.onOpen,
    required this.onLoadMore,
  });

  final PagedList<ForumConversation> paged;
  final void Function(ForumConversation) onOpen;
  final Future<void> Function() onLoadMore;

  @override
  Widget build(BuildContext context) {
    if (paged.items.isEmpty) {
      // A scrollable so the RefreshIndicator above still works when empty.
      return ListView(
        children: const [
          SizedBox(height: AppSpacing.xl3),
          Center(child: Text('No messages yet.')),
        ],
      );
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
        final conversation = paged.items[index];
        return _ConversationTile(
          conversation: conversation,
          onTap: () => onOpen(conversation),
        );
      },
    );
  }
}

/// The inbox preview line: own last message → "You: …"; in a group, another
/// member's → "Ada: …" so the reader knows who spoke last; a direct thread
/// needs no name (the row is already titled with the other member).
String conversationPreview(ForumConversation conversation) {
  final last = conversation.lastMessage;
  if (last == null) return 'No messages yet.';
  if (last.isMine) return 'You: ${last.body}';
  final sender = last.sender;
  if (conversation.isGroup && sender != null) {
    return '${sender.name}: ${last.body}';
  }
  return last.body;
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({required this.conversation, required this.onTap});

  final ForumConversation conversation;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isGroup = conversation.isGroup;
    // A direct row always carries the far side (a deleted member is the
    // `[deleted]` sentinel, never null); the fallback only guards a
    // malformed payload.
    final other =
        conversation.otherParticipant ?? ForumAuthor.fromJson(const {});
    final name = isGroup ? (conversation.title ?? 'Group') : other.name;
    final unread = conversation.hasUnread;
    final preview = conversationPreview(conversation);
    final time = forumRelativeTime(conversation.lastMessageAt);
    // Unread rows read bold in both the name and preview; read rows keep the
    // preview in the quieter onSurfaceVariant.
    final emphasis = unread ? FontWeight.w700 : null;

    return Card(
      color: unread
          ? theme.colorScheme.primaryContainer.withValues(alpha: 0.25)
          : null,
      child: ListTile(
        onTap: onTap,
        leading: isGroup
            ? AuthorAvatarCluster(authors: conversation.participants)
            : AuthorAvatar(author: other, radius: 20),
        title: Text(
          name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: theme.textTheme.titleSmall?.copyWith(fontWeight: emphasis),
        ),
        subtitle: Text(
          preview,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: theme.textTheme.bodySmall?.copyWith(
            fontWeight: emphasis,
            color: unread
                ? theme.colorScheme.onSurface
                : theme.colorScheme.onSurfaceVariant,
          ),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (time.isNotEmpty)
              Text(
                time,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            if (unread) ...[
              const SizedBox(height: AppSpacing.xs),
              Badge(label: Text('${conversation.unreadCount}')),
            ],
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
