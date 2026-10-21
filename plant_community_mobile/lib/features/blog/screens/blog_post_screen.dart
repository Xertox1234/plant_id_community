import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../forum/services/forum_link_launcher.dart';
import '../models/blog_post.dart';
import '../providers/blog_providers.dart';
import '../services/blog_api.dart';
import '../widgets/blog_block_view.dart';
import 'blog_format.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';

/// One blog post (todo 385). [initialTitle] is the list row's title, shown
/// in the app bar while the post loads; without one the bar says the blog's
/// name rather than nothing (todo 460).
class BlogPostScreen extends ConsumerWidget {
  const BlogPostScreen({super.key, required this.slug, this.initialTitle});

  final String slug;
  final String? initialTitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final post = ref.watch(blogPostProvider(slug));
    return Scaffold(
      appBar: AppBar(
        title: Text(
          post.asData?.value.title ?? initialTitle ?? blogDisplayName,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: SafeArea(
        child: post.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    error is ApiException && error.statusCode == 404
                        ? 'This post is no longer available.'
                        : 'Could not load this post.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  OutlinedButton(
                    onPressed: () => ref.invalidate(blogPostProvider(slug)),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          ),
          data: (post) => _PostBody(
            post: post,
            mediaUrl: ref.read(blogApiProvider).mediaUrl,
            onOpenLink: (href) => _openLink(context, ref, href),
            onOpenPage: (id) => _openPage(context, ref, id),
          ),
        ),
      ),
    );
  }

  /// A relative `/blog/<slug>` link opens that post in the app. Anything
  /// else goes through the forum's allowlist (absolute http/https only) to
  /// the in-app browser. A refused or failed link gets a short message,
  /// never the raw URL.
  Future<void> _openLink(
    BuildContext context,
    WidgetRef ref,
    String href,
  ) async {
    final slug = internalBlogSlug(href);
    if (slug != null) {
      _openPost(context, slug);
      return;
    }
    await _openExternal(context, ref, href);
  }

  /// A Wagtail internal link (`<a linktype="page" id="N">`) carries only the
  /// page id. Resolve it when tapped (owner decision 2026-10-10, todo 460): a
  /// blog post opens in the app, any other page at its web URL.
  Future<void> _openPage(BuildContext context, WidgetRef ref, int id) async {
    final BlogPageRef page;
    try {
      page = await ref.read(blogApiProvider).fetchPage(id);
    } catch (_) {
      if (context.mounted) _cannotOpen(context);
      return;
    }
    if (!context.mounted) return;
    if (page.isBlogPost) {
      _openPost(context, page.slug, title: page.title);
      return;
    }
    await _openExternal(context, ref, page.htmlUrl);
  }

  /// Push the post at [slug], unless it is this one: a link to itself would
  /// stack a duplicate screen.
  void _openPost(BuildContext context, String slug, {String? title}) {
    if (slug == this.slug) return;
    context.pushNamed(
      'blogPost',
      pathParameters: {'slug': slug},
      extra: title != null && title.isNotEmpty ? title : null,
    );
  }

  Future<void> _openExternal(
    BuildContext context,
    WidgetRef ref,
    String href,
  ) async {
    final uri = openableForumLink(href);
    var opened = false;
    if (uri != null) {
      try {
        opened = await ref.read(forumLinkLauncherProvider)(uri);
      } catch (_) {
        opened = false;
      }
    }
    if (!opened && context.mounted) _cannotOpen(context);
  }

  void _cannotOpen(BuildContext context) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text("Couldn't open this link.")));
  }
}

/// The post slug of a relative `/blog/<slug>` link, or null for anything
/// else. Read from the parsed path, so a unicode slug (Wagtail allows them
/// by default), raw or percent-encoded, matches too (todo 460).
String? internalBlogSlug(String href) {
  final uri = Uri.tryParse(href.trim());
  if (uri == null || uri.hasScheme || uri.hasAuthority) return null;
  if (!uri.path.startsWith('/')) return null;
  final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
  if (segments.length != 2 || segments.first != 'blog') return null;
  return segments.last;
}

class _PostBody extends StatelessWidget {
  const _PostBody({
    required this.post,
    required this.mediaUrl,
    required this.onOpenLink,
    required this.onOpenPage,
  });

  final BlogPost post;
  final String Function(String url) mediaUrl;
  final void Function(String href) onOpenLink;
  final void Function(int pageId) onOpenPage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final image = post.featuredImage;
    final meta = [
      if (post.authorName.isNotEmpty) post.authorName,
      blogMetaLine(post.publishDate, post.readingTime),
    ].where((s) => s.isNotEmpty).join(' · ');

    return ListView(
      padding:
          const EdgeInsets.fromLTRB(
            AppSpacing.md,
            AppSpacing.md,
            AppSpacing.md,
            AppSpacing.xl3,
          ) +
          MainShell.fabClearanceOf(context),
      children: [
        if (image != null) ...[
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(
              aspectRatio: 2,
              child: CachedNetworkImage(
                imageUrl: mediaUrl(image.url),
                fit: BoxFit.cover,
                imageBuilder: (context, provider) => Semantics(
                  image: true,
                  // Alt text is the editor's; with none, the image is
                  // decorative beside the title.
                  label: image.alt.isNotEmpty ? image.alt : null,
                  excludeSemantics: image.alt.isEmpty,
                  child: Image(image: provider, fit: BoxFit.cover),
                ),
                placeholder: (context, _) =>
                    ColoredBox(color: theme.colorScheme.surfaceContainerHigh),
                errorWidget: (context, _, _) =>
                    ColoredBox(color: theme.colorScheme.surfaceContainerHigh),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        Semantics(
          header: true,
          child: Text(post.title, style: theme.textTheme.headlineSmall),
        ),
        if (meta.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(meta, style: theme.textTheme.bodySmall),
        ],
        if (post.introduction.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          BlogRichText(
            post.introduction,
            onOpenLink: onOpenLink,
            onOpenPage: onOpenPage,
          ),
        ],
        for (final block in post.blocks) ...[
          const SizedBox(height: AppSpacing.md),
          BlogBlockView(
            block: block,
            mediaUrl: mediaUrl,
            onOpenLink: onOpenLink,
            onOpenPage: onOpenPage,
          ),
        ],
      ],
    );
  }
}
