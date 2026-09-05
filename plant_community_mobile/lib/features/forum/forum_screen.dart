import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants/app_spacing.dart';
import '../../services/auth_service.dart';
import 'models/models.dart';
import 'providers/forum_providers.dart';

/// Community forum home: the boards a member can browse, plus a "Recent
/// activity" list backed by the offline delta-sync mirror.
class ForumScreen extends ConsumerWidget {
  const ForumScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final boardsAsync = ref.watch(boardsProvider);
    final recentAsync = ref.watch(recentTopicsProvider);
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Community'),
        centerTitle: true,
        actions: [
          IconButton(
            tooltip: 'Search',
            onPressed: () => context.pushNamed('forumSearch'),
            icon: const Icon(Icons.search),
          ),
          if (isAuthenticated) ...[
            IconButton(
              tooltip: 'Bookmarks',
              onPressed: () => context.pushNamed('forumBookmarks'),
              icon: const Icon(Icons.bookmark_border),
            ),
            const _MessagesInboxButton(),
            const _NotificationsBellButton(),
          ],
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(boardsProvider);
            ref.invalidate(recentTopicsProvider);
          },
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              const _SectionHeader('Boards'),
              boardsAsync.when(
                loading: () => const _SectionLoader(),
                error: (error, _) => _SectionError(
                  message: 'Could not load boards.',
                  onRetry: () => ref.invalidate(boardsProvider),
                ),
                data: (boards) => boards.isEmpty
                    ? const _EmptyLine('No boards yet.')
                    : Column(
                        children: [
                          for (final board in boards)
                            _BoardTile(
                              board: board,
                              onTap: () => context.pushNamed(
                                'forumBoard',
                                pathParameters: {'slug': board.slug},
                                extra: board.title,
                              ),
                            ),
                        ],
                      ),
              ),
              const SizedBox(height: AppSpacing.lg),
              const _SectionHeader('Recent activity'),
              recentAsync.when(
                loading: () => const _SectionLoader(),
                error: (error, _) => _SectionError(
                  message: 'Could not load recent topics.',
                  onRetry: () => ref.invalidate(recentTopicsProvider),
                ),
                data: (topics) => topics.isEmpty
                    ? const _EmptyLine('Nothing here yet.')
                    : Column(
                        children: [
                          for (final stub in topics.take(10))
                            _RecentTile(
                              stub: stub,
                              onTap: () => context.pushNamed(
                                'forumTopic',
                                pathParameters: {'id': '${stub.id}'},
                                extra: stub.title,
                              ),
                            ),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Inbox icon with an unread-conversation badge, opening the DM inbox
/// (todo 339). Sits beside the bell so the two private feeds read as a pair.
class _MessagesInboxButton extends ConsumerWidget {
  const _MessagesInboxButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadAsync = ref.watch(unreadConversationCountProvider);
    final unread = unreadAsync.asData?.value ?? 0;
    return IconButton(
      tooltip: 'Messages',
      onPressed: () => context.pushNamed('forumMessages'),
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text('$unread'),
        child: const Icon(Icons.mail_outline),
      ),
    );
  }
}

/// Bell icon with an unread-count badge, opening the notifications screen.
class _NotificationsBellButton extends ConsumerWidget {
  const _NotificationsBellButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadAsync = ref.watch(unreadNotificationCountProvider);
    final unread = unreadAsync.asData?.value ?? 0;
    return IconButton(
      tooltip: 'Notifications',
      onPressed: () => context.pushNamed('forumNotifications'),
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text('$unread'),
        child: const Icon(Icons.notifications_outlined),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.title);
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _BoardTile extends StatelessWidget {
  const _BoardTile({required this.board, required this.onTap});
  final ForumBoard board;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        onTap: onTap,
        title: Text(
          board.title,
          style: theme.textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        subtitle: board.description.isNotEmpty
            ? Text(
                board.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              )
            : null,
        trailing: Text(
          '${board.topicCount} topics',
          style: theme.textTheme.labelSmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _RecentTile extends StatelessWidget {
  const _RecentTile({required this.stub, required this.onTap});
  final ForumTopicStub stub;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        dense: true,
        onTap: onTap,
        leading: const Icon(Icons.forum_outlined),
        title: Text(stub.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
    );
  }
}

class _SectionLoader extends StatelessWidget {
  const _SectionLoader();
  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.symmetric(vertical: AppSpacing.md),
    child: Center(child: CircularProgressIndicator()),
  );
}

class _SectionError extends StatelessWidget {
  const _SectionError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          Expanded(child: Text(message)),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}

class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Text(
        text,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
