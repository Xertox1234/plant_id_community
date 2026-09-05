import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_html_text.dart';

/// Renders a parsed forum body (list of [ForumBodyBlock]) with block parity to
/// the web `StreamFieldRenderer`: heading, paragraph (HTML), quote, post
/// quote, code, image, plus graceful fallbacks for deleted images and
/// unknown block types.
class ForumBodyRenderer extends StatelessWidget {
  const ForumBodyRenderer(
    this.blocks, {
    super.key,
    this.onOpenLink,
    this.currentTopicId,
  });

  final List<ForumBodyBlock> blocks;
  final void Function(String href)? onOpenLink;

  /// The topic this body is being read in, when the surface knows it (the
  /// thread, its edit-history sheet). A `post_quote` of a post in the SAME
  /// topic then drops its "in topic" link — pushing the route the viewer is
  /// already on would stack a duplicate thread screen.
  final int? currentTopicId;

  @override
  Widget build(BuildContext context) {
    if (blocks.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < blocks.length; i++) ...[
          if (i > 0) const SizedBox(height: AppSpacing.sm),
          _block(context, blocks[i]),
        ],
      ],
    );
  }

  Widget _block(BuildContext context, ForumBodyBlock block) {
    final theme = Theme.of(context);
    return switch (block) {
      HeadingBlock(:final text) => Text(
        text,
        style: theme.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w700,
        ),
      ),
      ParagraphBlock(:final html) => ForumHtmlText(
        html,
        onOpenLink: onOpenLink,
      ),
      QuoteBlock(:final text) => _Quote(text: text),
      PostQuoteBlock quote => _PostQuote(
        quote: quote,
        currentTopicId: currentTopicId,
      ),
      CodeBlock(:final code, :final language) => _Code(
        code: code,
        language: language,
      ),
      ForumImageBlock(:final url, :final alt) => _Image(url: url, alt: alt),
      EmbedBlock(
        :final url,
        :final providerName,
        :final title,
        :final thumbnailUrl,
      ) =>
        _EmbedCard(
          url: url,
          providerName: providerName,
          title: title,
          thumbnailUrl: thumbnailUrl,
          onOpenLink: onOpenLink,
        ),
      DeletedImageBlock() => _Placeholder(
        icon: Icons.broken_image_outlined,
        label: 'Image unavailable',
      ),
      UnknownBlock(:final type) => _Placeholder(
        icon: Icons.help_outline,
        label: 'Unsupported content ($type)',
      ),
    };
  }
}

class _Quote extends StatelessWidget {
  const _Quote({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.only(left: AppSpacing.md),
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: theme.colorScheme.primary, width: 3),
        ),
      ),
      child: Text(
        text,
        style: theme.textTheme.bodyMedium?.copyWith(
          fontStyle: FontStyle.italic,
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

/// A quote OF A SPECIFIC POST (todo 342): the excerpt, then who wrote it
/// and an "in topic" link to the quoted post. The text is plain by
/// contract (the server never sanitizes it; consumers escape at render)
/// and `Text` is exactly that — never a markup renderer. When the quoted
/// post is gone (`available: false`) the excerpt still renders, under a
/// muted notice instead of an attribution. An available quote whose
/// envelope nonetheless lacks the author or topic (defensive — the contract
/// sends both) renders the excerpt with whatever attribution it has and
/// never the "gone" notice.
///
/// The link navigates from here, not through a per-screen callback: every
/// surface that renders a body (thread, edit history, …) gets the same deep
/// link with no plumbing, and `forumTopic` already takes a `postId` to
/// scroll to — the same route a notification tap uses. It is dropped when
/// the quoted post lives in [currentTopicId] — the viewer is already there.
///
/// Stateful only for the blocked/muted reveal: a quote of an author the
/// viewer blocked or muted renders COLLAPSED (never hidden — the reply
/// around it still reads as a reply) until "Show anyway", the same local,
/// no-refetch reveal a blocked post gets in `PostCard`.
class _PostQuote extends StatefulWidget {
  const _PostQuote({required this.quote, this.currentTopicId});
  final PostQuoteBlock quote;
  final int? currentTopicId;

  @override
  State<_PostQuote> createState() => _PostQuoteState();
}

class _PostQuoteState extends State<_PostQuote> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    final quote = widget.quote;
    final author = quote.author;
    final collapsed = (quote.isBlocked || quote.isMuted) && !_revealed;
    return Semantics(
      container: true,
      label: 'Quote from ${author?.name ?? 'a member'}',
      child: _QuoteRule(
        child: collapsed
            ? _CollapsedQuoteNotice(
                blocked: quote.isBlocked,
                onReveal: () => setState(() => _revealed = true),
              )
            : _PostQuoteBody(
                quote: quote,
                currentTopicId: widget.currentTopicId,
              ),
      ),
    );
  }
}

/// The left primary rule every quote shape shares.
class _QuoteRule extends StatelessWidget {
  const _QuoteRule({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: AppSpacing.md),
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(
            color: Theme.of(context).colorScheme.primary,
            width: 3,
          ),
        ),
      ),
      child: child,
    );
  }
}

/// One-line notice for a quote of a blocked/muted author — the same icon,
/// wording shape and "Show anyway" reveal as `PostCard`'s blocked
/// placeholder. Blocked wins when both flags are set (the stronger
/// relation). The excerpt is NOT in the tree until revealed.
class _CollapsedQuoteNotice extends StatelessWidget {
  const _CollapsedQuoteNotice({required this.blocked, required this.onReveal});
  final bool blocked;
  final VoidCallback onReveal;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurfaceVariant;
    return Row(
      children: [
        Icon(blocked ? Icons.block : Icons.volume_off, size: 16, color: muted),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            blocked
                ? 'Quote from a member you blocked.'
                : 'Quote from a member you muted.',
            style: theme.textTheme.bodySmall?.copyWith(color: muted),
          ),
        ),
        TextButton(onPressed: onReveal, child: const Text('Show anyway')),
      ],
    );
  }
}

class _PostQuoteBody extends StatelessWidget {
  const _PostQuoteBody({required this.quote, this.currentTopicId});
  final PostQuoteBlock quote;
  final int? currentTopicId;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.colorScheme.onSurfaceVariant;
    final author = quote.author;
    final topicId = quote.topicId;
    final postId = quote.postId;
    final linked = topicId != null && topicId != currentTopicId;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          quote.text,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontStyle: FontStyle.italic,
            color: muted,
          ),
        ),
        if (!quote.available) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Quoted post is no longer available',
            style: theme.textTheme.bodySmall?.copyWith(color: muted),
          ),
        ] else if (author != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              AuthorAvatar(author: author, radius: 10),
              const SizedBox(width: AppSpacing.xs),
              Flexible(
                child: Text(
                  author.name,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (linked)
                TextButton(
                  onPressed: () => context.pushNamed(
                    'forumTopic',
                    pathParameters: {'id': '$topicId'},
                    queryParameters: postId == null
                        ? const <String, String>{}
                        : {'postId': '$postId'},
                  ),
                  style: TextButton.styleFrom(
                    minimumSize: const Size(48, 48),
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                    ),
                    textStyle: theme.textTheme.bodySmall,
                  ),
                  child: const Text('in topic'),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _Code extends StatelessWidget {
  const _Code({required this.code, required this.language});
  final String code;
  final String language;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (language.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Text(
                language,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Text(
              code,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

class _Image extends StatelessWidget {
  const _Image({required this.url, required this.alt});
  final String url;
  final String alt;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: alt.isNotEmpty ? alt : null,
      image: true,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
        child: CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.cover,
          placeholder: (context, _) => const SizedBox(
            height: 120,
            child: Center(child: CircularProgressIndicator()),
          ),
          errorWidget: (context, _, _) => const _Placeholder(
            icon: Icons.broken_image_outlined,
            label: 'Image unavailable',
          ),
        ),
      ),
    );
  }
}

/// A video embed as a thumbnail card (todo 344): provider, title and the
/// link — never an inline player or provider HTML. Tapping hands the URL to
/// the same [onOpenLink] the paragraph links use (the thread screen shows
/// it in a SnackBar; a real launcher is todo 341 parity work). A blank
/// envelope (no url, no title) renders the unavailable placeholder, like a
/// deleted image, rather than an empty card.
class _EmbedCard extends StatelessWidget {
  const _EmbedCard({
    required this.url,
    required this.providerName,
    required this.title,
    required this.thumbnailUrl,
    this.onOpenLink,
  });
  final String url;
  final String providerName;
  final String title;
  final String thumbnailUrl;
  final void Function(String href)? onOpenLink;

  @override
  Widget build(BuildContext context) {
    if (url.isEmpty && title.isEmpty) {
      return const _Placeholder(
        icon: Icons.videocam_off_outlined,
        label: 'Video unavailable',
      );
    }
    final theme = Theme.of(context);
    final label = title.isNotEmpty ? title : url;
    final fallbackIcon = Icon(
      Icons.play_circle_outline,
      size: 32,
      color: theme.colorScheme.onSurfaceVariant,
    );
    return Semantics(
      label: providerName.isNotEmpty
          ? '$providerName video: $label'
          : 'Video: $label',
      button: onOpenLink != null,
      // The composed label already says everything the two Text children
      // say; without this a screen reader announces the title twice.
      excludeSemantics: true,
      child: Material(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppSpacing.rXs),
          onTap: onOpenLink == null || url.isEmpty
              ? null
              : () => onOpenLink!(url),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Row(
              children: [
                if (thumbnailUrl.isNotEmpty)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(AppSpacing.rXs),
                    child: SizedBox(
                      width: 96,
                      height: 54,
                      child: CachedNetworkImage(
                        imageUrl: thumbnailUrl,
                        fit: BoxFit.cover,
                        placeholder: (context, _) => ColoredBox(
                          color: theme.colorScheme.surfaceContainerHigh,
                        ),
                        errorWidget: (context, _, _) => fallbackIcon,
                      ),
                    ),
                  )
                else
                  fallbackIcon,
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodyMedium,
                      ),
                      Text(
                        providerName.isNotEmpty
                            ? 'Watch on $providerName'
                            : url,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: AppSpacing.xs),
          Flexible(
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
