import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';

/// Full-text forum search: a query field, optional board filter, and two
/// result sections (topics/posts) that page independently via one shared
/// `page` cursor (offset pagination — see [ForumSearchPage]).
class ForumSearchScreen extends ConsumerStatefulWidget {
  const ForumSearchScreen({super.key});

  @override
  ConsumerState<ForumSearchScreen> createState() => _ForumSearchScreenState();
}

class _ForumSearchScreenState extends ConsumerState<ForumSearchScreen> {
  final _queryController = TextEditingController();
  String? _boardFilter;

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  void _submit() {
    ref
        .read(forumSearchProvider.notifier)
        .search(query: _queryController.text, board: _boardFilter);
  }

  @override
  Widget build(BuildContext context) {
    final result = ref.watch(forumSearchProvider);
    final boardsAsync = ref.watch(boardsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                children: [
                  TextField(
                    controller: _queryController,
                    textInputAction: TextInputAction.search,
                    decoration: const InputDecoration(
                      hintText: 'Search topics and posts',
                      prefixIcon: Icon(Icons.search),
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: [
                      Expanded(
                        child: boardsAsync.when(
                          loading: () => const SizedBox.shrink(),
                          error: (error, _) => const SizedBox.shrink(),
                          data: (boards) => DropdownButtonFormField<String?>(
                            initialValue: _boardFilter,
                            decoration: const InputDecoration(
                              labelText: 'Board',
                              border: OutlineInputBorder(),
                              isDense: true,
                            ),
                            items: [
                              const DropdownMenuItem(
                                value: null,
                                child: Text('All boards'),
                              ),
                              for (final board in boards)
                                DropdownMenuItem(
                                  value: board.slug,
                                  child: Text(board.title),
                                ),
                            ],
                            onChanged: (value) =>
                                setState(() => _boardFilter = value),
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      FilledButton(
                        onPressed: _submit,
                        child: const Text('Search'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(child: _ResultsBody(result: result)),
          ],
        ),
      ),
    );
  }
}

class _ResultsBody extends ConsumerWidget {
  const _ResultsBody({required this.result});
  final ForumSearchResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    switch (result.status) {
      case ForumSearchStatus.idle:
        return const Center(child: Text('Search topics and posts.'));
      case ForumSearchStatus.loading:
        return const Center(child: CircularProgressIndicator());
      case ForumSearchStatus.error:
        return _ErrorRetry(
          message: 'Could not search right now.',
          onRetry: () => ref
              .read(forumSearchProvider.notifier)
              .search(query: result.query, board: result.board),
        );
      case ForumSearchStatus.data:
      case ForumSearchStatus.loadingMore:
        break;
    }

    return ListView(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      children: [
        // The semantic section (code review, todo 295) is an ALWAYS-checked
        // sibling, never an alternative to "No results." — search() requests
        // `semantic: true` unconditionally, so semanticStatus is non-null on
        // every real response; gating "No results." on it being null made
        // that branch dead code and left a genuine zero-hit search
        // (semanticStatus: ok, empty semantic list) rendering nothing at all.
        if (result.semanticStatus != null)
          _SemanticSection(
            status: result.semanticStatus!,
            topics: result.semantic ?? const [],
          ),
        if (result.topics.isEmpty && result.posts.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Text('No results.'),
          ),
        if (result.topics.isNotEmpty) ...[
          const _SectionHeader('Topics'),
          for (final topic in result.topics)
            _TopicHitTile(
              topic: topic,
              onTap: () => context.pushNamed(
                'forumTopic',
                pathParameters: {'id': '${topic.id}'},
                extra: topic.title,
              ),
            ),
        ],
        if (result.posts.isNotEmpty) ...[
          const _SectionHeader('Posts'),
          for (final post in result.posts)
            _PostHitTile(
              post: post,
              onTap: () => context.pushNamed(
                'forumTopic',
                pathParameters: {'id': '${post.topicId}'},
                extra: post.topicTitle,
              ),
            ),
        ],
        if (result.hasMore)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Center(
              child: result.status == ForumSearchStatus.loadingMore
                  ? const CircularProgressIndicator()
                  : OutlinedButton(
                      onPressed: () =>
                          ref.read(forumSearchProvider.notifier).loadMore(),
                      child: const Text('Load more'),
                    ),
            ),
          ),
      ],
    );
  }
}

/// Renders the `semantic_status` state — `unavailable`/`premium_required`
/// are states to display, not errors to hide behind (todo 295 AC).
class _SemanticSection extends StatelessWidget {
  const _SemanticSection({required this.status, required this.topics});
  final ForumSemanticStatus status;
  final List<ForumSearchTopicHit> topics;

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case ForumSemanticStatus.unavailable:
        return const _SemanticNote('Related topics are unavailable right now.');
      case ForumSemanticStatus.premiumRequired:
        return const _SemanticNote('Related topics are a premium feature.');
      case ForumSemanticStatus.ok:
        if (topics.isEmpty) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionHeader('Related topics'),
            for (final topic in topics)
              _TopicHitTile(
                topic: topic,
                onTap: () => context.pushNamed(
                  'forumTopic',
                  pathParameters: {'id': '${topic.id}'},
                  extra: topic.title,
                ),
              ),
          ],
        );
    }
  }
}

class _SemanticNote extends StatelessWidget {
  const _SemanticNote(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Text(
        text,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
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
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _TopicHitTile extends StatelessWidget {
  const _TopicHitTile({required this.topic, required this.onTap});
  final ForumSearchTopicHit topic;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onTap,
        leading: const Icon(Icons.forum_outlined),
        title: Text(topic.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          '${topic.replyCount} replies · ${topic.viewCount} views',
        ),
      ),
    );
  }
}

class _PostHitTile extends StatelessWidget {
  const _PostHitTile({required this.post, required this.onTap});
  final ForumSearchPostHit post;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onTap,
        leading: const Icon(Icons.chat_bubble_outline),
        title: Text(
          post.topicTitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          post.excerpt,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
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
