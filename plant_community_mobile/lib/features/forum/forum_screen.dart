import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../shared/widgets/clay_button.dart';

/// Community forum hub (stub). Shows a few sample posts; live posting is not
/// yet implemented.
class ForumScreen extends StatelessWidget {
  const ForumScreen({super.key});

  static const _posts = [
    _Post(
      author: 'Sarah G.',
      authorInitial: 'S',
      tag: 'Help',
      title: 'Why are my Monstera leaves turning yellow?',
      upvotes: 12,
      replies: 4,
    ),
    _Post(
      author: 'Mark B.',
      authorInitial: 'M',
      tag: 'Share',
      title: 'My succulent collection after 2 years 🌵',
      upvotes: 48,
      replies: 11,
    ),
    _Post(
      author: 'Leaf Lover',
      authorInitial: 'L',
      tag: 'ID',
      title: 'Can anyone identify this fern I found?',
      upvotes: 7,
      replies: 2,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    return Scaffold(
      appBar: AppBar(title: const Text('Community'), centerTitle: true),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: ext.padScreen),
          child: Column(
            children: [
              Expanded(
                child: ListView.separated(
                  padding: EdgeInsets.only(
                    top: ext.padScreen,
                    bottom: ext.gapY,
                  ),
                  itemCount: _posts.length,
                  separatorBuilder: (_, _) => SizedBox(height: ext.gapY),
                  itemBuilder: (context, i) =>
                      _PostCard(post: _posts[i], ext: ext),
                ),
              ),
              SizedBox(height: ext.gapY),
              ClayButton(
                label: '+ New Post',
                fullWidth: true,
                onPressed: () {},
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Live posting coming soon',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: ext.ink3),
                textAlign: TextAlign.center,
              ),
              SizedBox(height: ext.padScreen),
            ],
          ),
        ),
      ),
    );
  }
}

class _Post {
  const _Post({
    required this.author,
    required this.authorInitial,
    required this.tag,
    required this.title,
    required this.upvotes,
    required this.replies,
  });
  final String author;
  final String authorInitial;
  final String tag;
  final String title;
  final int upvotes;
  final int replies;
}

class _PostCard extends StatelessWidget {
  const _PostCard({required this.post, required this.ext});
  final _Post post;
  final GreenThumbExtension ext;

  Color _tagBg(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return switch (post.tag) {
      'Help' => ext.berry.withValues(alpha: 0.12),
      'Share' => cs.primary.withValues(alpha: 0.12),
      _ => ext.sky.withValues(alpha: 0.12),
    };
  }

  Color _tagFg(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return switch (post.tag) {
      'Help' => ext.berry,
      'Share' => cs.primary,
      _ => ext.sky,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(ext.padCard),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor: Theme.of(
                    context,
                  ).colorScheme.primaryContainer,
                  child: Text(
                    post.authorInitial,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  post.author,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: ext.ink2),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: _tagBg(context),
                    borderRadius: BorderRadius.circular(AppSpacing.rXs),
                  ),
                  child: Text(
                    post.tag,
                    style: TextStyle(
                      color: _tagFg(context),
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(post.title, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            Row(
              children: [
                Icon(Icons.arrow_upward, size: 14, color: ext.ink3),
                const SizedBox(width: 2),
                Text(
                  '${post.upvotes}',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: ext.ink3),
                ),
                const SizedBox(width: AppSpacing.sm),
                Icon(Icons.chat_bubble_outline, size: 14, color: ext.ink3),
                const SizedBox(width: 2),
                Text(
                  '${post.replies}',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: ext.ink3),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
