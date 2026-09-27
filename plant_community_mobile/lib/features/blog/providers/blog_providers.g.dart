// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'blog_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Published posts, newest first, offset-paginated with [loadMore]. [tag]
/// narrows to one tag (the care guides pass `care-guide`); null = all posts.

@ProviderFor(BlogPosts)
final blogPostsProvider = BlogPostsFamily._();

/// Published posts, newest first, offset-paginated with [loadMore]. [tag]
/// narrows to one tag (the care guides pass `care-guide`); null = all posts.
final class BlogPostsProvider
    extends $AsyncNotifierProvider<BlogPosts, BlogFeed> {
  /// Published posts, newest first, offset-paginated with [loadMore]. [tag]
  /// narrows to one tag (the care guides pass `care-guide`); null = all posts.
  BlogPostsProvider._({
    required BlogPostsFamily super.from,
    required String? super.argument,
  }) : super(
         retry: blogRetry,
         name: r'blogPostsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$blogPostsHash();

  @override
  String toString() {
    return r'blogPostsProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  BlogPosts create() => BlogPosts();

  @override
  bool operator ==(Object other) {
    return other is BlogPostsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$blogPostsHash() => r'c9257902b6a7f9c23f37fdebcf02e6be70c41922';

/// Published posts, newest first, offset-paginated with [loadMore]. [tag]
/// narrows to one tag (the care guides pass `care-guide`); null = all posts.

final class BlogPostsFamily extends $Family
    with
        $ClassFamilyOverride<
          BlogPosts,
          AsyncValue<BlogFeed>,
          BlogFeed,
          FutureOr<BlogFeed>,
          String?
        > {
  BlogPostsFamily._()
    : super(
        retry: blogRetry,
        name: r'blogPostsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Published posts, newest first, offset-paginated with [loadMore]. [tag]
  /// narrows to one tag (the care guides pass `care-guide`); null = all posts.

  BlogPostsProvider call(String? tag) =>
      BlogPostsProvider._(argument: tag, from: this);

  @override
  String toString() => r'blogPostsProvider';
}

/// Published posts, newest first, offset-paginated with [loadMore]. [tag]
/// narrows to one tag (the care guides pass `care-guide`); null = all posts.

abstract class _$BlogPosts extends $AsyncNotifier<BlogFeed> {
  late final _$args = ref.$arg as String?;
  String? get tag => _$args;

  FutureOr<BlogFeed> build(String? tag);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<BlogFeed>, BlogFeed>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<BlogFeed>, BlogFeed>,
              AsyncValue<BlogFeed>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}

/// One post by slug.

@ProviderFor(blogPost)
final blogPostProvider = BlogPostFamily._();

/// One post by slug.

final class BlogPostProvider
    extends
        $FunctionalProvider<AsyncValue<BlogPost>, BlogPost, FutureOr<BlogPost>>
    with $FutureModifier<BlogPost>, $FutureProvider<BlogPost> {
  /// One post by slug.
  BlogPostProvider._({
    required BlogPostFamily super.from,
    required String super.argument,
  }) : super(
         retry: blogRetry,
         name: r'blogPostProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$blogPostHash();

  @override
  String toString() {
    return r'blogPostProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<BlogPost> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<BlogPost> create(Ref ref) {
    final argument = this.argument as String;
    return blogPost(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is BlogPostProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$blogPostHash() => r'daa3be7a2fbe98a0d82b9906114b3d8930f0b85e';

/// One post by slug.

final class BlogPostFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<BlogPost>, String> {
  BlogPostFamily._()
    : super(
        retry: blogRetry,
        name: r'blogPostProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// One post by slug.

  BlogPostProvider call(String slug) =>
      BlogPostProvider._(argument: slug, from: this);

  @override
  String toString() => r'blogPostProvider';
}
