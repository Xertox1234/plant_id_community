import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../../forum/widgets/forum_html_text.dart';
import '../models/blog_post.dart';

/// Renders one blog StreamField block (todo 385).
///
/// Rich text goes through [ForumHtmlText], which walks the DOM into styled
/// spans and never renders raw markup: tags outside its small allowlist
/// contribute their text only. The blog's server-side allowlist is wider
/// than the forum's (headings, images), so a blog paragraph may lose
/// formatting here, never content.
class BlogBlockView extends StatelessWidget {
  const BlogBlockView({
    super.key,
    required this.block,
    required this.mediaUrl,
    required this.onOpenLink,
  });

  final BlogBlock block;

  /// Resolves a payload image URL against the API origin.
  final String Function(String url) mediaUrl;
  final void Function(String href) onOpenLink;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return switch (block) {
      BlogHeadingBlock(:final text) => Padding(
        padding: const EdgeInsets.only(top: AppSpacing.sm),
        child: Semantics(
          header: true,
          child: Text(text, style: theme.textTheme.titleLarge),
        ),
      ),
      BlogParagraphBlock(:final html) => ForumHtmlText(
        html,
        onOpenLink: onOpenLink,
      ),
      BlogQuoteBlock(:final html, :final attribution) => Container(
        padding: const EdgeInsets.only(left: AppSpacing.md),
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(color: theme.colorScheme.primary, width: 3),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ForumHtmlText(html, onOpenLink: onOpenLink),
            if (attribution.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              // The attribution is plain text on the server (a CharBlock);
              // Text never interprets it as markup.
              Text('— $attribution', style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
      BlogCodeBlock(:final code) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(8),
        ),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Text(
            code,
            style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
          ),
        ),
      ),
      final BlogPlantSpotlightBlock spotlight => _PlantSpotlight(
        block: spotlight,
        mediaUrl: mediaUrl,
        onOpenLink: onOpenLink,
      ),
      final BlogCallToActionBlock cta => Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (cta.title.isNotEmpty)
                Text(cta.title, style: theme.textTheme.titleMedium),
              if (cta.descriptionHtml.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.xs),
                ForumHtmlText(cta.descriptionHtml, onOpenLink: onOpenLink),
              ],
              if (cta.buttonText.isNotEmpty && cta.buttonUrl.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                FilledButton(
                  onPressed: () => onOpenLink(cta.buttonUrl),
                  child: Text(cta.buttonText),
                ),
              ],
            ],
          ),
        ),
      ),
    };
  }
}

class _PlantSpotlight extends StatelessWidget {
  const _PlantSpotlight({
    required this.block,
    required this.mediaUrl,
    required this.onOpenLink,
  });

  final BlogPlantSpotlightBlock block;
  final String Function(String url) mediaUrl;
  final void Function(String href) onOpenLink;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final image = block.image;
    final difficulty = block.careDifficulty;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (image != null) ...[
            AspectRatio(
              aspectRatio: 2,
              child: CachedNetworkImage(
                imageUrl: mediaUrl(image.url),
                fit: BoxFit.cover,
                imageBuilder: (context, provider) => Semantics(
                  image: true,
                  label: image.alt.isNotEmpty ? image.alt : block.plantName,
                  child: Image(image: provider, fit: BoxFit.cover),
                ),
                placeholder: (context, _) =>
                    ColoredBox(color: theme.colorScheme.surfaceContainerHigh),
                errorWidget: (context, _, _) => const SizedBox.shrink(),
              ),
            ),
            // The stock-photo credit travels WITH the image: Unsplash and
            // Pexels require it wherever the photo is shown (todo 376).
            if (block.imageCredit.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  AppSpacing.xs,
                  AppSpacing.md,
                  0,
                ),
                child: block.imageCreditUrl.isNotEmpty
                    ? InkWell(
                        onTap: () => onOpenLink(block.imageCreditUrl),
                        child: Text(
                          block.imageCredit,
                          style: theme.textTheme.bodySmall?.copyWith(
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      )
                    : Text(block.imageCredit, style: theme.textTheme.bodySmall),
              ),
          ],
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(block.plantName, style: theme.textTheme.titleMedium),
                if (block.scientificName.isNotEmpty)
                  Text(
                    block.scientificName,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                if (difficulty.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Care difficulty: '
                    '${difficulty[0].toUpperCase()}${difficulty.substring(1)}',
                    style: theme.textTheme.labelMedium,
                  ),
                ],
                if (block.descriptionHtml.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  ForumHtmlText(block.descriptionHtml, onOpenLink: onOpenLink),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
