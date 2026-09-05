import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/auth_service.dart';
import '../../../services/user_profile_service.dart';
import '../forum_format.dart';
import '../providers/forum_providers.dart';
import '../widgets/author_identity.dart';

/// A public forum profile: identity + trust + recent activity, read-only.
/// Backed by `GET /forum/users/{username}/` (`AllowAny` server-side, so this
/// screen never requires the viewer to be logged in).
class ForumUserProfileScreen extends ConsumerWidget {
  const ForumUserProfileScreen({super.key, required this.username});

  final String username;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileAsync = ref.watch(forumUserProfileProvider(username));
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    // The "Message" action (todo 339) is hidden on your own profile and for
    // anonymous viewers (the backend 401s a DM send). The current username
    // lives on the account profile, which is only fetched when signed in —
    // while it is still loading, AND if that fetch failed, the action stays
    // hidden: without knowing who "you" are, showing it risks offering to
    // message yourself. Deliberate; the account profile fetch retries on the
    // next visit, and the inbox remains reachable from the forum home.
    final myUsername = isAuthenticated
        ? ref.watch(userProfileServiceProvider).asData?.value?.username
        : null;
    final canMessage =
        myUsername != null &&
        myUsername != username &&
        profileAsync.hasValue &&
        !(profileAsync.asData?.value.author.isDeleted ?? true);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          if (canMessage)
            IconButton(
              tooltip: 'Message',
              icon: const Icon(Icons.mail_outline),
              onPressed: () => context.pushNamed(
                'forumConversation',
                pathParameters: {'username': username},
              ),
            ),
        ],
      ),
      body: SafeArea(
        child: profileAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _ErrorRetry(
            message: 'Could not load this profile.',
            onRetry: () => ref.invalidate(forumUserProfileProvider(username)),
          ),
          data: (profile) => ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              AuthorIdentity(
                author: profile.author,
                avatarRadius: 32,
                nameStyle: Theme.of(context).textTheme.titleLarge,
              ),
              if (profile.author.title.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Text(
                    profile.author.title,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              if (profile.bio.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.sm),
                  child: Text(profile.bio),
                ),
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Text(
                  [
                    '${profile.postCount} posts',
                    if (profile.joinedAt != null)
                      'Joined ${forumRelativeTime(profile.joinedAt)}',
                  ].join(' · '),
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              const _SectionHeader('Recent topics'),
              if (profile.recentTopics.isEmpty)
                const _EmptyLine('No topics yet.')
              else
                for (final t in profile.recentTopics)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(t.title),
                    subtitle: Text(
                      '${t.replyCount} replies · ${forumRelativeTime(t.createdAt)}',
                    ),
                    onTap: () => context.pushNamed(
                      'forumTopic',
                      pathParameters: {'id': '${t.id}'},
                      extra: t.title,
                    ),
                  ),
              const SizedBox(height: AppSpacing.md),
              const _SectionHeader('Recent posts'),
              if (profile.recentPosts.isEmpty)
                const _EmptyLine('No replies yet.')
              else
                for (final p in profile.recentPosts)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(p.topicTitle),
                    subtitle: Text(forumRelativeTime(p.createdAt)),
                    onTap: () => context.pushNamed(
                      'forumTopic',
                      pathParameters: {'id': '${p.topicId}'},
                      extra: p.topicTitle,
                    ),
                  ),
            ],
          ),
        ),
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
