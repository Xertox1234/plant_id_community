import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../services/api_service.dart';
import '../models/blog_post.dart';

/// HTTP contract for the Wagtail blog API (`/api/v2/blog-posts/`, todo 385).
///
/// An interface so tests override the provider with a fake, the same
/// convention as `ForumApi`.
abstract class BlogApi {
  /// One page of published posts, newest first. [tag] filters by tag name
  /// (case-insensitive on the server).
  Future<BlogPostPage> fetchPosts({String? tag, int offset = 0});

  /// The full post for [slug], or throws [ApiException] with status 404.
  Future<BlogPost> fetchPost(String slug);

  /// Resolve a media URL from a payload against the API origin.
  String mediaUrl(String url);

  /// What a rich-text internal link (`<a linktype="page" id="N">`) points
  /// at, from `/api/v2/pages/N/` (todo 460, owner decision 2026-10-10).
  Future<BlogPageRef> fetchPage(int id);

  /// The file URL of a rich-text inline image (`<embed embedtype="image"
  /// id="N">`), from `/api/v2/images/N/`, or null when it has none.
  Future<String?> fetchImageUrl(int id);
}

/// A Wagtail page as an internal link resolves it.
class BlogPageRef {
  const BlogPageRef({
    required this.id,
    this.type = '',
    this.slug = '',
    this.title = '',
    this.htmlUrl = '',
  });

  factory BlogPageRef.fromJson(Map<String, dynamic> json) {
    final meta = json['meta'] is Map<String, dynamic>
        ? json['meta'] as Map<String, dynamic>
        : const <String, dynamic>{};
    String str(Object? v) => v is String ? v : '';
    return BlogPageRef(
      id: json['id'] is int ? json['id'] as int : 0,
      type: str(meta['type']),
      slug: str(meta['slug']),
      title: str(json['title']),
      htmlUrl: str(meta['html_url']),
    );
  }

  final int id;

  /// `app_label.ModelName`, e.g. `blog.BlogPostPage`.
  final String type;
  final String slug;
  final String title;

  /// The page's public URL, empty when Wagtail has no site to route it.
  final String htmlUrl;

  bool get isBlogPost => type == blogPostPageType && slug.isNotEmpty;
}

/// The Wagtail page type the app opens in its own post screen.
const String blogPostPageType = 'blog.BlogPostPage';

/// Posts per page. Wagtail's API v2 caps `limit` at 20 by default
/// (`WAGTAILAPI_LIMIT_MAX`), so asking for more returns a 400.
const int blogPageSize = 20;

class HttpBlogApi implements BlogApi {
  HttpBlogApi(this._api);

  final ApiService _api;

  /// The blog is Wagtail API **v2**, not the `/api/v1` the app's base URL
  /// points at. Dio uses an absolute URL as-is, so build it from the origin.
  String _v2(String path) => '${Uri.parse(_api.baseUrl).origin}/api/v2$path';

  @override
  Future<BlogPostPage> fetchPosts({String? tag, int offset = 0}) async {
    final resp = await _api.get(
      _v2('/blog-posts/'),
      queryParameters: {
        'limit': blogPageSize,
        'offset': offset,
        'order': '-first_published_at',
        if (tag != null && tag.isNotEmpty) 'tag': tag,
      },
    );
    return BlogPostPage.fromJson(resp.data as Map<String, dynamic>);
  }

  /// Two requests, as on the web (`fetchBlogPost` in
  /// `web/src/services/blogService.ts`): the LIST route resolves the slug
  /// but its light serializer has no body, and the DETAIL route that has
  /// the body is id-addressed.
  @override
  Future<BlogPost> fetchPost(String slug) async {
    final listing = await _api.get(
      _v2('/blog-posts/'),
      queryParameters: {'type': 'blog.BlogPostPage', 'slug': slug, 'limit': 1},
    );
    final page = BlogPostPage.fromJson(listing.data as Map<String, dynamic>);
    if (page.items.isEmpty) {
      throw ApiException('Post not found', statusCode: 404);
    }
    final detail = await _api.get(
      _v2('/blog-posts/${page.items.first.id}/'),
      queryParameters: {'fields': '*'},
    );
    return BlogPost.fromJson(detail.data as Map<String, dynamic>);
  }

  @override
  String mediaUrl(String url) => resolveBlogMediaUrl(url, _api.baseUrl);

  @override
  Future<BlogPageRef> fetchPage(int id) async {
    final resp = await _api.get(_v2('/pages/$id/'));
    return BlogPageRef.fromJson(resp.data as Map<String, dynamic>);
  }

  @override
  Future<String?> fetchImageUrl(int id) async {
    final resp = await _api.get(_v2('/images/$id/'));
    final meta = (resp.data as Map<String, dynamic>)['meta'];
    final url = meta is Map<String, dynamic> ? meta['download_url'] : null;
    return url is String && url.isNotEmpty ? mediaUrl(url) : null;
  }
}

final blogApiProvider = Provider<BlogApi>(
  (ref) => HttpBlogApi(ref.watch(apiServiceProvider)),
);
