/// Blog posts from the Wagtail API v2 (`/api/v2/blog-posts/`, todo 385).
///
/// Two payload shapes, like the web (`web/src/types/blog.ts`):
///
/// * the LIST route sends `BlogPostPageListSerializer` — no `introduction`,
///   no `content_blocks`, an `excerpt` instead;
/// * the DETAIL route (`/api/v2/blog-posts/<id>/`) sends
///   `BlogPostPageSerializer` with the StreamField body.
///
/// Parsing is tolerant: a missing or wrong-typed field degrades to empty
/// rather than throwing, so one odd post never blanks the whole list.
library;

/// A Wagtail image rendition: `{url, full_url?, width, height, alt}`.
class BlogImage {
  const BlogImage({required this.url, this.alt = '', this.width, this.height});

  /// Relative (`/media/…`) or absolute. Resolve with [resolveBlogMediaUrl]
  /// before loading.
  final String url;
  final String alt;
  final int? width;
  final int? height;

  static BlogImage? fromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    // `full_url` is request-derived (todo 308) and absolute; `url` may be
    // relative. Prefer the absolute one, the resolver handles either.
    final url = _str(json['full_url']).isNotEmpty
        ? _str(json['full_url'])
        : _str(json['url']);
    if (url.isEmpty) return null;
    return BlogImage(
      url: url,
      alt: _str(json['alt']),
      width: json['width'] is int ? json['width'] as int : null,
      height: json['height'] is int ? json['height'] as int : null,
    );
  }
}

/// A post as the LIST route sends it.
class BlogPostSummary {
  const BlogPostSummary({
    required this.id,
    required this.slug,
    required this.title,
    this.excerpt = '',
    this.authorName = '',
    this.publishDate,
    this.readingTime,
    this.tags = const [],
    this.thumbnail,
  });

  final int id;
  final String slug;
  final String title;
  final String excerpt;
  final String authorName;
  final DateTime? publishDate;

  /// Minutes, as the server computes it; null when unknown.
  final int? readingTime;
  final List<String> tags;
  final BlogImage? thumbnail;

  factory BlogPostSummary.fromJson(Map<String, dynamic> json) {
    return BlogPostSummary(
      id: json['id'] is int ? json['id'] as int : 0,
      slug: _str(json['slug']),
      title: _str(json['title']),
      excerpt: _str(json['excerpt']),
      authorName: _authorName(json['author']),
      publishDate: DateTime.tryParse(_str(json['publish_date'])),
      readingTime: json['reading_time'] is int
          ? json['reading_time'] as int
          : null,
      tags: _tags(json['tags']),
      thumbnail:
          BlogImage.fromJson(json['featured_image_thumb']) ??
          BlogImage.fromJson(json['featured_image']),
    );
  }
}

/// One page of the offset-paginated list: `{meta: {total_count}, items}`.
class BlogPostPage {
  const BlogPostPage({required this.items, required this.totalCount});

  final List<BlogPostSummary> items;
  final int totalCount;

  factory BlogPostPage.fromJson(Map<String, dynamic> json) {
    final meta = json['meta'];
    final items = (json['items'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(BlogPostSummary.fromJson)
        // A row without a slug cannot be opened; drop it rather than render
        // a card that goes nowhere.
        .where((p) => p.slug.isNotEmpty)
        .toList(growable: false);
    return BlogPostPage(
      items: items,
      totalCount: meta is Map<String, dynamic> && meta['total_count'] is int
          ? meta['total_count'] as int
          : items.length,
    );
  }
}

/// A post as the DETAIL route sends it.
class BlogPost {
  const BlogPost({
    required this.id,
    required this.slug,
    required this.title,
    this.introduction = '',
    this.authorName = '',
    this.publishDate,
    this.readingTime,
    this.tags = const [],
    this.featuredImage,
    this.blocks = const [],
  });

  final int id;
  final String slug;
  final String title;

  /// Rich-text HTML (a Wagtail `RichTextField`).
  final String introduction;
  final String authorName;
  final DateTime? publishDate;
  final int? readingTime;
  final List<String> tags;
  final BlogImage? featuredImage;
  final List<BlogBlock> blocks;

  factory BlogPost.fromJson(Map<String, dynamic> json) {
    return BlogPost(
      id: json['id'] is int ? json['id'] as int : 0,
      slug: _str(json['slug']),
      title: _str(json['title']),
      introduction: _str(json['introduction']),
      authorName: _authorName(json['author']),
      publishDate: DateTime.tryParse(_str(json['publish_date'])),
      readingTime: json['reading_time'] is int
          ? json['reading_time'] as int
          : null,
      tags: _tags(json['tags']),
      featuredImage: BlogImage.fromJson(json['featured_image']),
      blocks: (json['content_blocks'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(BlogBlock.fromJson)
          .whereType<BlogBlock>()
          .toList(growable: false),
    );
  }
}

/// One `content_blocks` entry. The block set is `BlogStreamBlocks` in
/// `backend/apps/blog/models.py`; an unknown type parses to null and is
/// skipped, so a block added on the server never breaks the app.
sealed class BlogBlock {
  const BlogBlock();

  static BlogBlock? fromJson(Map<String, dynamic> json) {
    final value = json['value'];
    switch (json['type']) {
      case 'heading':
        final text = _str(value);
        return text.isEmpty ? null : BlogHeadingBlock(text);
      case 'paragraph':
        final html = _str(value);
        return html.isEmpty ? null : BlogParagraphBlock(html);
      case 'quote':
        // Older rows stored a bare string; the StructBlock sends a map.
        if (value is String) {
          return value.isEmpty ? null : BlogQuoteBlock(html: value);
        }
        if (value is! Map<String, dynamic>) return null;
        final html = _str(value['quote_text']);
        if (html.isEmpty) return null;
        return BlogQuoteBlock(
          html: html,
          attribution: _str(value['attribution']),
        );
      case 'code':
        if (value is! Map<String, dynamic>) return null;
        final code = _str(value['code']);
        if (code.isEmpty) return null;
        return BlogCodeBlock(code: code, language: _str(value['language']));
      case 'plant_spotlight':
        if (value is! Map<String, dynamic>) return null;
        final name = _str(value['plant_name']);
        if (name.isEmpty) return null;
        return BlogPlantSpotlightBlock(
          plantName: name,
          scientificName: _str(value['scientific_name']),
          descriptionHtml: _str(value['description']),
          careDifficulty: _str(value['care_difficulty']),
          image: BlogImage.fromJson(value['image']),
          imageCredit: _str(value['image_credit']).trim(),
          imageCreditUrl: _str(value['image_credit_url']),
        );
      case 'call_to_action':
        if (value is! Map<String, dynamic>) return null;
        final title = _str(value['cta_title']);
        final buttonText = _str(value['button_text']);
        if (title.isEmpty && buttonText.isEmpty) return null;
        return BlogCallToActionBlock(
          title: title,
          descriptionHtml: _str(value['cta_description']),
          buttonText: buttonText,
          buttonUrl: _str(value['button_url']),
        );
      default:
        return null;
    }
  }
}

class BlogHeadingBlock extends BlogBlock {
  const BlogHeadingBlock(this.text);
  final String text;
}

class BlogParagraphBlock extends BlogBlock {
  const BlogParagraphBlock(this.html);
  final String html;
}

class BlogQuoteBlock extends BlogBlock {
  const BlogQuoteBlock({required this.html, this.attribution = ''});
  final String html;
  final String attribution;
}

class BlogCodeBlock extends BlogBlock {
  const BlogCodeBlock({required this.code, this.language = ''});
  final String code;
  final String language;
}

class BlogPlantSpotlightBlock extends BlogBlock {
  const BlogPlantSpotlightBlock({
    required this.plantName,
    this.scientificName = '',
    this.descriptionHtml = '',
    this.careDifficulty = '',
    this.image,
    this.imageCredit = '',
    this.imageCreditUrl = '',
  });

  final String plantName;
  final String scientificName;
  final String descriptionHtml;
  final String careDifficulty;
  final BlogImage? image;

  /// Stock-photo credit. Unsplash and Pexels require it wherever the image
  /// is shown (todo 376), so the renderer must show it with the image.
  final String imageCredit;
  final String imageCreditUrl;
}

class BlogCallToActionBlock extends BlogBlock {
  const BlogCallToActionBlock({
    required this.title,
    this.descriptionHtml = '',
    this.buttonText = '',
    this.buttonUrl = '',
  });

  final String title;
  final String descriptionHtml;
  final String buttonText;
  final String buttonUrl;
}

/// Resolve a media URL from the API against the API's origin.
///
/// Mirrors `mediaUrl` in `web/src/services/blogService.ts`: a relative path
/// goes onto the API origin, and so does ANY `/media/` path, even an
/// absolute one, because an absolute `/media/` URL is Django's local storage
/// on the API host and the host it names has been wrong before (todo 308).
/// An R2/CDN URL has no `/media/` segment and passes through unchanged.
///
/// [apiBaseUrl] is `ApiService.baseUrl` (`https://host/api/v1`); only its
/// scheme, host and port are used.
String resolveBlogMediaUrl(String url, String apiBaseUrl) {
  final base = Uri.tryParse(apiBaseUrl);
  if (base == null || !base.hasAuthority) return url;
  final origin = base.origin;
  if (url.startsWith('/')) return '$origin$url';
  final parsed = Uri.tryParse(url);
  if (parsed != null &&
      parsed.hasAuthority &&
      parsed.path.startsWith('/media/')) {
    final query = parsed.hasQuery ? '?${parsed.query}' : '';
    return '$origin${parsed.path}$query';
  }
  return url;
}

String _str(Object? value) => value is String ? value : '';

String _authorName(Object? author) {
  if (author is! Map<String, dynamic>) return '';
  final display = _str(author['display_name']).trim();
  return display.isNotEmpty ? display : _str(author['username']);
}

List<String> _tags(Object? tags) {
  if (tags is! List) return const [];
  // The list serializer sends names; tolerate `{name: …}` objects too.
  return tags
      .map((t) => t is String ? t : (t is Map ? _str(t['name']) : ''))
      .where((t) => t.isNotEmpty)
      .toList(growable: false);
}
