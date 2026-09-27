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

  /// Every `fetchPosts` call as `(tag, offset)`.
  final calls = <(String?, int)>[];
  Object? postsError;

  @override
  Future<BlogPostPage> fetchPosts({String? tag, int offset = 0}) async {
    calls.add((tag, offset));
    if (postsError != null) throw postsError!;
    final i = calls.length - 1;
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
  String mediaUrl(String url) =>
      resolveBlogMediaUrl(url, 'https://api.example.com/api/v1');
}

BlogPostSummary summary(int id, {String? title}) => BlogPostSummary(
  id: id,
  slug: 'post-$id',
  title: title ?? 'Post $id',
  excerpt: 'Excerpt $id',
);
