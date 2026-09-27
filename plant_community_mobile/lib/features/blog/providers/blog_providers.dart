import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../services/api_service.dart';
import '../models/blog_post.dart';
import '../services/blog_api.dart';

part 'blog_providers.g.dart';

/// Riverpod 3 retries a failed provider up to 10 times with backoff (about
/// 40 s in all), showing a spinner the whole time. A 4xx will not change on
/// retry: a deleted post would spin for 40 s before saying it is gone. So
/// client errors fail at once; network and server errors keep the default.
Duration? blogRetry(int retryCount, Object error) {
  if (error is ApiException) {
    final status = error.statusCode ?? 0;
    if (status >= 400 && status < 500) return null;
  }
  return ProviderContainer.defaultRetry(retryCount, error);
}

/// Published posts, newest first, offset-paginated with [loadMore]. [tag]
/// narrows to one tag (the care guides pass `care-guide`); null = all posts.
@Riverpod(retry: blogRetry)
class BlogPosts extends _$BlogPosts {
  @override
  Future<BlogFeed> build(String? tag) async {
    final page = await ref.watch(blogApiProvider).fetchPosts(tag: tag);
    return BlogFeed(
      items: page.items,
      totalCount: page.totalCount,
      nextOffset: page.rowCount,
      exhausted: page.rowCount < blogPageSize,
    );
  }

  /// Fetch and append the next page. Rethrows on failure with the loading
  /// flag reset so the caller can surface an error and the user can retry.
  Future<void> loadMore() async {
    final current = state.asData?.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(current.copyWith(isLoadingMore: true));
    try {
      final page = await ref
          .read(blogApiProvider)
          .fetchPosts(tag: tag, offset: current.nextOffset);
      final latest = state.asData?.value ?? current;
      // Offset paging can repeat a row when a post is published between
      // pages; keep the first copy.
      final seen = latest.items.map((p) => p.id).toSet();
      state = AsyncData(
        BlogFeed(
          items: [...latest.items, ...page.items.where((p) => seen.add(p.id))],
          totalCount: page.totalCount,
          nextOffset: latest.nextOffset + page.rowCount,
          // A short page means the end even if total_count disagrees.
          exhausted: page.rowCount < blogPageSize,
        ),
      );
    } catch (_) {
      final latest = state.asData?.value ?? current;
      state = AsyncData(latest.copyWith(isLoadingMore: false));
      rethrow;
    }
  }
}

/// One post by slug.
@Riverpod(retry: blogRetry)
Future<BlogPost> blogPost(Ref ref, String slug) {
  return ref.watch(blogApiProvider).fetchPost(slug);
}

class BlogFeed {
  const BlogFeed({
    required this.items,
    required this.totalCount,
    required this.nextOffset,
    this.isLoadingMore = false,
    this.exhausted = false,
  });

  final List<BlogPostSummary> items;
  final int totalCount;

  /// The server offset of the next page: the sum of rows the server
  /// returned, which is always a multiple of [blogPageSize] until the end.
  final int nextOffset;
  final bool isLoadingMore;
  final bool exhausted;

  bool get hasMore => !exhausted && nextOffset < totalCount;

  BlogFeed copyWith({bool? isLoadingMore}) => BlogFeed(
    items: items,
    totalCount: totalCount,
    nextOffset: nextOffset,
    isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    exhausted: exhausted,
  );
}
