import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../../forum/widgets/forum_html_text.dart';
import '../models/blog_post.dart';
import '../services/blog_api.dart';

/// Blog rich text: [ForumHtmlText] with the blog's internal links and inline
/// images wired in.
///
/// The API sends Wagtail's stored rich-text format, not the expanded HTML
/// (todo 460 decision): expanding it on the server would change the web's
/// payload too, and the web already renders the stored format. So the
/// renderer resolves the two references itself, at the moment they matter:
/// a page link at tap time ([onOpenPage], owner decision 2026-10-10), an
/// inline image when it is first built ([BlogInlineImage]).
class BlogRichText extends StatelessWidget {
  const BlogRichText(
    this.html, {
    super.key,
    required this.onOpenLink,
    this.onOpenPage,
  });

  final String html;
  final void Function(String href) onOpenLink;
  final void Function(int pageId)? onOpenPage;

  @override
  Widget build(BuildContext context) => ForumHtmlText(
    html,
    onOpenLink: onOpenLink,
    onOpenPage: onOpenPage,
    inlineImageBuilder: (id, alt) => BlogInlineImage(imageId: id, alt: alt),
  );
}

/// A rich-text inline image, looked up by id once and cached
/// ([blogInlineImageUrlProvider]). Takes no room while loading or when the
/// image cannot be resolved, so a missing image never leaves a hole.
class BlogInlineImage extends ConsumerWidget {
  const BlogInlineImage({super.key, required this.imageId, this.alt = ''});

  final int imageId;
  final String alt;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final url = ref.watch(blogInlineImageUrlProvider(imageId)).value;
    if (url == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.fitWidth,
          imageBuilder: (context, provider) => Semantics(
            image: true,
            label: alt.isNotEmpty ? alt : null,
            excludeSemantics: alt.isEmpty,
            child: Image(image: provider, fit: BoxFit.fitWidth),
          ),
          placeholder: (context, _) => const SizedBox.shrink(),
          errorWidget: (context, _, _) => const SizedBox.shrink(),
        ),
      ),
    );
  }
}

/// Renders one blog StreamField block (todo 385).
///
/// Rich text goes through [BlogRichText], which walks the DOM into styled
/// spans and never renders raw markup: tags outside its allowlist contribute
/// their text only.
class BlogBlockView extends StatelessWidget {
  const BlogBlockView({
    super.key,
    required this.block,
    required this.mediaUrl,
    required this.onOpenLink,
    this.onOpenPage,
  });

  final BlogBlock block;

  /// Resolves a payload image URL against the API origin.
  final String Function(String url) mediaUrl;
  final void Function(String href) onOpenLink;

  /// Opens a Wagtail internal link by page id.
  final void Function(int pageId)? onOpenPage;

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
      BlogParagraphBlock(:final html) => BlogRichText(
        html,
        onOpenLink: onOpenLink,
        onOpenPage: onOpenPage,
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
            BlogRichText(html, onOpenLink: onOpenLink, onOpenPage: onOpenPage),
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
        onOpenPage: onOpenPage,
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
                BlogRichText(
                  cta.descriptionHtml,
                  onOpenLink: onOpenLink,
                  onOpenPage: onOpenPage,
                ),
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
    this.onOpenPage,
  });

  final BlogPlantSpotlightBlock block;
  final String Function(String url) mediaUrl;
  final void Function(String href) onOpenLink;
  final void Function(int pageId)? onOpenPage;

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
            // The 2:1 frame wraps the image and its placeholder only: a photo
            // that fails to load takes no room, where it used to leave an
            // empty 2:1 box (todo 460).
            CachedNetworkImage(
              imageUrl: mediaUrl(image.url),
              fit: BoxFit.cover,
              imageBuilder: (context, provider) => AspectRatio(
                aspectRatio: 2,
                child: Semantics(
                  image: true,
                  label: image.alt.isNotEmpty ? image.alt : block.plantName,
                  child: Image(image: provider, fit: BoxFit.cover),
                ),
              ),
              placeholder: (context, _) => AspectRatio(
                aspectRatio: 2,
                child: ColoredBox(
                  color: theme.colorScheme.surfaceContainerHigh,
                ),
              ),
              errorWidget: (context, _, _) => const SizedBox.shrink(),
            ),
            // The stock-photo credit travels WITH the image: Unsplash and
            // Pexels require it wherever the photo is shown (todo 376).
            if (block.imageCredit.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                child: _SpotlightCredit(block: block, onOpenLink: onOpenLink),
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
                  BlogRichText(
                    block.descriptionHtml,
                    onOpenLink: onOpenLink,
                    onOpenPage: onOpenPage,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// "Photo by Jane Doe on Unsplash", with each link a full-size tap target
/// (todo 460). For an Unsplash credit the API splits it (todo 442), so the
/// photographer and Unsplash are two links, as Unsplash's guidelines ask and
/// as the web does (todo 438). Any other credit is one link, or plain text
/// with no URL.
class _SpotlightCredit extends StatelessWidget {
  const _SpotlightCredit({required this.block, required this.onOpenLink});

  final BlogPlantSpotlightBlock block;
  final void Function(String href) onOpenLink;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall;
    final creditUrl = block.imageCreditUrl;
    Widget link(String text, String href) => Semantics(
      link: true,
      child: InkWell(
        onTap: () => onOpenLink(href),
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            minHeight: kMinInteractiveDimension,
          ),
          child: Align(
            alignment: Alignment.centerLeft,
            widthFactor: 1,
            child: Text(
              text,
              style: style?.copyWith(decoration: TextDecoration.underline),
            ),
          ),
        ),
      ),
    );
    Widget plain(String text) => ConstrainedBox(
      constraints: const BoxConstraints(minHeight: kMinInteractiveDimension),
      child: Align(
        alignment: Alignment.centerLeft,
        widthFactor: 1,
        child: Text(text, style: style),
      ),
    );

    final lead = block.creditLead;
    if (lead.isNotEmpty && block.unsplashHref.isNotEmpty) {
      return Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          creditUrl.isNotEmpty ? link(lead, creditUrl) : plain(lead),
          plain(' on '),
          link('Unsplash', block.unsplashHref),
        ],
      );
    }
    return creditUrl.isNotEmpty
        ? link(block.imageCredit, creditUrl)
        : plain(block.imageCredit);
  }
}
