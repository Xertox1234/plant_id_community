import 'dart:async';

import 'package:plant_community_mobile/features/blog/models/blog_post.dart';
import 'package:plant_community_mobile/features/blog/services/blog_api.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// In-memory [BlogApi]. [pages] is served in order, one per `fetchPosts`
/// call; [posts] maps slug → detail (a missing slug 404s, like the server).
class FakeBlogApi implements BlogApi {
  FakeBlogApi({List<BlogPostPage>? pages, Map<String, BlogPost>? posts})
    : pages = pages ?? [const BlogPostPage(items: [], totalCount: 0)],
      posts = posts ?? {};

  final List<BlogPostPage> pages;
  final Map<String, BlogPost> posts;

  /// Wagtail pages by id, for rich-text internal links; a missing id 404s.
  final pagesById = <int, BlogPageRef>{};

  /// Inline-image file URLs by id; a missing id resolves to null.
  final imageUrls = <int, String>{};
  final imageLookups = <int>[];

  /// Inline-image ids whose lookup throws this error (a 404, a 500).
  final imageErrors = <int, Object>{};

  /// When set, a `fetchPosts` past the first page waits on it.
  Completer<void>? moreGate;

  /// When set, a first-page `fetchPosts` (a load or a refresh) waits on it.
  Completer<void>? listGate;

  /// Every `fetchPosts` call as `(tag, offset)`.
  final calls = <(String?, int)>[];
  Object? postsError;

  @override
  Future<BlogPostPage> fetchPosts({String? tag, int offset = 0}) async {
    calls.add((tag, offset));
    // Picked before any gate, so a held call keeps the page it asked for.
    final i = calls.length - 1;
    if (offset > 0 && moreGate != null) await moreGate!.future;
    if (offset == 0 && listGate != null) await listGate!.future;
    if (postsError != null) throw postsError!;
    return i < pages.length
        ? pages[i]
        : BlogPostPage(items: const [], totalCount: pages.last.totalCount);
  }

  @override
  Future<BlogPost> fetchPost(String slug) async {
    final post = posts[slug];
    if (post == null) throw ApiException('Post not found', statusCode: 404);
    return post;
  }

  @override
  Future<BlogPageRef> fetchPage(int id) async {
    final page = pagesById[id];
    if (page == null) throw ApiException('Page not found', statusCode: 404);
    return page;
  }

  @override
  Future<String?> fetchImageUrl(int id) async {
    imageLookups.add(id);
    final error = imageErrors[id];
    if (error != null) throw error;
    return imageUrls[id];
  }

  @override
  String mediaUrl(String url) =>
      resolveBlogMediaUrl(url, 'https://api.example.com/api/v1');
}

BlogPostSummary summary(int id, {String? title}) => BlogPostSummary(
  id: id,
  slug: 'post-$id',
  title: title ?? 'Post $id',
  excerpt: 'Excerpt $id',
);
