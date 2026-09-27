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
}

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
}

final blogApiProvider = Provider<BlogApi>(
  (ref) => HttpBlogApi(ref.watch(apiServiceProvider)),
);
