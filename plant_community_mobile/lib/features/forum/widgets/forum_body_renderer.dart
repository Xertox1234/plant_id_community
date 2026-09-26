import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_html_text.dart';

/// Renders a parsed forum body (list of [ForumBodyBlock]) with block parity to
/// the web `StreamFieldRenderer`: heading, paragraph (HTML), quote, post
/// quote, code, image, video embed, link card, plus graceful fallbacks for
/// deleted images and unknown block types.
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
      LinkPreviewBlock card => _LinkPreviewCard(
        card: card,
        onOpenLink: onOpenLink,
      ),
      DeletedImageBlock() => _Placeholder(
        icon: LucideIcons.imageOff,
        label: 'Image unavailable',
      ),
      UnknownBlock(:final type) => _Placeholder(
        icon: LucideIcons.circleHelp,
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
        Icon(
          blocked ? LucideIcons.ban : LucideIcons.volumeX,
          size: 16,
          color: muted,
        ),
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
              // GeistMono, not the platform 'monospace': the app bundles the
              // design system's mono face and the web sets `font-mono` here.
              style: AppTypography.bodySm.copyWith(fontFamily: 'GeistMono'),
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
            icon: LucideIcons.imageOff,
            label: 'Image unavailable',
          ),
        ),
      ),
    );
  }
}

/// A video embed as a thumbnail card (todo 344): provider, title and the
/// link — never an inline player or provider HTML. Tapping hands the URL to
/// the same [onOpenLink] the paragraph links use (the thread screen opens it
/// in the in-app browser, todo 424). A blank
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
        icon: LucideIcons.videoOff,
        label: 'Video unavailable',
      );
    }
    final theme = Theme.of(context);
    final label = title.isNotEmpty ? title : url;
    final fallbackIcon = Icon(
      LucideIcons.circlePlay,
      size: 32,
      color: theme.colorScheme.onSurfaceVariant,
    );
    final onOpenLink = this.onOpenLink;
    final onTap = onOpenLink == null || url.isEmpty
        ? null
        : () => onOpenLink(url);
    return Semantics(
      label: providerName.isNotEmpty
          ? '$providerName video: $label'
          : 'Video: $label',
      button: onTap != null,
      // excludeSemantics drops the InkWell's own tap action, so the node
      // must carry it or a screen reader's double-tap does nothing.
      onTap: onTap,
      // The composed label already says everything the two Text children
      // say; without this a screen reader announces the title twice.
      excludeSemantics: true,
      child: Material(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppSpacing.rXs),
          onTap: onTap,
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

/// A link posted on its own, as a card (todo 428): image, site, title,
/// description and the SHORTENED address ([linkPreviewShortAddress]) — never
/// the full URL on screen or in the spoken label. Tapping hands the URL to
/// [onOpenLink], like a paragraph link (the thread opens it in the in-app
/// browser, todo 424). The full URL is reachable two ways (owner decision
/// 2026-09-24): a long-press opens a sheet showing it with "Copy link", and
/// a screen reader gets "Show full address" and "Copy link" as custom
/// actions, which VoiceOver offers without any gesture. The owner's brief
/// said a Tooltip; a tooltip overlay cannot hold a tappable "Copy link", so
/// the long-press opens a sheet instead. A card with no usable link (a
/// `null` envelope) renders nothing, as the web does.
class _LinkPreviewCard extends StatelessWidget {
  const _LinkPreviewCard({required this.card, this.onOpenLink});
  final LinkPreviewBlock card;
  final void Function(String href)? onOpenLink;

  @override
  Widget build(BuildContext context) {
    final address = linkPreviewShortAddress(card.url);
    if (address == null) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final title = [
      card.title,
      card.siteName,
      card.domain,
    ].firstWhere((text) => text.isNotEmpty, orElse: () => address);
    final source = card.siteName.isNotEmpty ? card.siteName : card.domain;
    final url = card.url;
    final onOpenLink = this.onOpenLink;
    final onTap = onOpenLink == null ? null : () => onOpenLink(url);
    void showAddress() => _showLinkAddressSheet(context, url);
    return Semantics(
      label: title == address ? 'Link: $address' : 'Link: $title, $address',
      button: onTap != null,
      onTap: onTap,
      onLongPress: showAddress,
      customSemanticsActions: {
        const CustomSemanticsAction(label: 'Show full address'): showAddress,
        const CustomSemanticsAction(label: 'Copy link'): () =>
            _copyLink(context, url),
      },
      // One node: the label already says what the Text children say, and
      // without this the InkWell adds a focusable child carrying its own
      // tap and long-press but no label — an unlabeled button.
      excludeSemantics: true,
      child: Material(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          onLongPress: showAddress,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (card.imageUrl.isNotEmpty)
                AspectRatio(
                  aspectRatio: 1.91,
                  child: CachedNetworkImage(
                    imageUrl: card.imageUrl,
                    fit: BoxFit.cover,
                    placeholder: (context, _) => ColoredBox(
                      color: theme.colorScheme.surfaceContainerHigh,
                    ),
                    errorWidget: (context, _, _) => const SizedBox.shrink(),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (source.isNotEmpty)
                      Text(
                        source.toUpperCase(),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (card.description.isNotEmpty)
                      Text(
                        card.description,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    if (title != address)
                      Text(
                        address,
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
    );
  }
}

Future<void> _copyLink(BuildContext context, String url) async {
  final messenger = ScaffoldMessenger.maybeOf(context);
  await Clipboard.setData(ClipboardData(text: url));
  messenger?.showSnackBar(const SnackBar(content: Text('Link copied')));
}

/// The long-press sheet of a link card: the full address, selectable, and
/// "Copy link".
Future<void> _showLinkAddressSheet(BuildContext context, String url) {
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);
      return Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Full address', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            SelectableText(url, style: theme.textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.sm),
            FilledButton.tonalIcon(
              icon: const Icon(LucideIcons.copy, size: 18),
              label: const Text('Copy link'),
              onPressed: () {
                Navigator.of(sheetContext).pop();
                _copyLink(context, url);
              },
            ),
          ],
        ),
      );
    },
  );
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
