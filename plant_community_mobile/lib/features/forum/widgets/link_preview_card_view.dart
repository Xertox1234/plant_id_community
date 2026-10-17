import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import 'forum_body_renderer.dart' show ForumBodyRenderer;

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
///
/// The ONE link card widget (todo 654): the reader ([ForumBodyRenderer]) and
/// the composer's preview both draw it, so an author sees the card readers
/// will. The composer passes no [onOpenLink], so a tap there does nothing.
class LinkPreviewCardView extends StatelessWidget {
  const LinkPreviewCardView({super.key, required this.card, this.onOpenLink});
  final LinkPreviewBlock card;
  final void Function(String href)? onOpenLink;

  @override
  Widget build(BuildContext context) {
    final display = linkPreviewDisplay(card);
    if (display == null) return const SizedBox.shrink();
    final theme = Theme.of(context);
    final LinkPreviewDisplay(:title, :detail, :label, :imageUrl) = display;
    final source = card.siteName.isNotEmpty ? card.siteName : card.domain;
    final url = display.href;
    final onOpenLink = this.onOpenLink;
    final onTap = onOpenLink == null ? null : () => onOpenLink(url);
    void showAddress() => showForumLinkAddressSheet(context, url);
    return Semantics(
      label: label,
      button: onTap != null,
      onTap: onTap,
      onLongPress: showAddress,
      customSemanticsActions: {
        const CustomSemanticsAction(label: 'Show full address'): showAddress,
        const CustomSemanticsAction(label: 'Copy link'): () =>
            copyForumLink(context, url),
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
              if (imageUrl.isNotEmpty)
                AspectRatio(
                  aspectRatio: 1.91,
                  child: CachedNetworkImage(
                    imageUrl: imageUrl,
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
                    if (detail.isNotEmpty)
                      Text(
                        detail,
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

/// Copy [url] and say so.
Future<void> copyForumLink(BuildContext context, String url) async {
  final messenger = ScaffoldMessenger.maybeOf(context);
  await Clipboard.setData(ClipboardData(text: url));
  messenger?.showSnackBar(const SnackBar(content: Text('Link copied')));
}

/// The long-press sheet of a link card: the full address, selectable, and
/// "Copy link".
Future<void> showForumLinkAddressSheet(BuildContext context, String url) {
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
                copyForumLink(context, url);
              },
            ),
          ],
        ),
      );
    },
  );
}
