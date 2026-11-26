// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'forum_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Who the forum's per-member data is for: null for a guest, else the
/// signed-in member's Firebase uid (a Firebase user still waiting on its JWT
/// is not signed in). A token refresh keeps the same viewer.
///
/// The per-member feeds are families keyed on it, so a new viewer always
/// reads a fresh element: Riverpod carries a provider's last value through a
/// rebuild and into a failed one, which would leave the previous member's
/// forums on screen when the new viewer's fetch fails.

@ProviderFor(forumViewer)
final forumViewerProvider = ForumViewerProvider._();

/// Who the forum's per-member data is for: null for a guest, else the
/// signed-in member's Firebase uid (a Firebase user still waiting on its JWT
/// is not signed in). A token refresh keeps the same viewer.
///
/// The per-member feeds are families keyed on it, so a new viewer always
/// reads a fresh element: Riverpod carries a provider's last value through a
/// rebuild and into a failed one, which would leave the previous member's
/// forums on screen when the new viewer's fetch fails.

final class ForumViewerProvider
    extends $FunctionalProvider<String?, String?, String?>
    with $Provider<String?> {
  /// Who the forum's per-member data is for: null for a guest, else the
  /// signed-in member's Firebase uid (a Firebase user still waiting on its JWT
  /// is not signed in). A token refresh keeps the same viewer.
  ///
  /// The per-member feeds are families keyed on it, so a new viewer always
  /// reads a fresh element: Riverpod carries a provider's last value through a
  /// rebuild and into a failed one, which would leave the previous member's
  /// forums on screen when the new viewer's fetch fails.
  ForumViewerProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'forumViewerProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$forumViewerHash();

  @$internal
  @override
  $ProviderElement<String?> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  String? create(Ref ref) {
    return forumViewer(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(String? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<String?>(value),
    );
  }
}

String _$forumViewerHash() => r'3e7badebc6b84c6e633b3f67c0cbf06060b7eb0f';

/// The forum index for [viewer]: categories, each with its forums and links,
/// in the server's order (`GET /forum/categories/`). Read it through
/// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
/// family) to refetch.
///
/// Signed in, it first waits for the member's unlock tokens to load, so the
/// first request after a cold start already carries them. A forum a sent
/// token did not open (still `is_locked`) drops that token: the dead-token
/// rule (spec §7.4).

@ProviderFor(Categories)
final categoriesProvider = CategoriesFamily._();

/// The forum index for [viewer]: categories, each with its forums and links,
/// in the server's order (`GET /forum/categories/`). Read it through
/// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
/// family) to refetch.
///
/// Signed in, it first waits for the member's unlock tokens to load, so the
/// first request after a cold start already carries them. A forum a sent
/// token did not open (still `is_locked`) drops that token: the dead-token
/// rule (spec §7.4).
final class CategoriesProvider
    extends $AsyncNotifierProvider<Categories, List<ForumCategory>> {
  /// The forum index for [viewer]: categories, each with its forums and links,
  /// in the server's order (`GET /forum/categories/`). Read it through
  /// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
  /// family) to refetch.
  ///
  /// Signed in, it first waits for the member's unlock tokens to load, so the
  /// first request after a cold start already carries them. A forum a sent
  /// token did not open (still `is_locked`) drops that token: the dead-token
  /// rule (spec §7.4).
  CategoriesProvider._({
    required CategoriesFamily super.from,
    required String? super.argument,
  }) : super(
         retry: forumRetry,
         name: r'categoriesProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$categoriesHash();

  @override
  String toString() {
    return r'categoriesProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  Categories create() => Categories();

  @override
  bool operator ==(Object other) {
    return other is CategoriesProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$categoriesHash() => r'97ec82925470dac2c43628948fece472b2757866';

/// The forum index for [viewer]: categories, each with its forums and links,
/// in the server's order (`GET /forum/categories/`). Read it through
/// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
/// family) to refetch.
///
/// Signed in, it first waits for the member's unlock tokens to load, so the
/// first request after a cold start already carries them. A forum a sent
/// token did not open (still `is_locked`) drops that token: the dead-token
/// rule (spec §7.4).

final class CategoriesFamily extends $Family
    with
        $ClassFamilyOverride<
          Categories,
          AsyncValue<List<ForumCategory>>,
          List<ForumCategory>,
          FutureOr<List<ForumCategory>>,
          String?
        > {
  CategoriesFamily._()
    : super(
        retry: forumRetry,
        name: r'categoriesProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The forum index for [viewer]: categories, each with its forums and links,
  /// in the server's order (`GET /forum/categories/`). Read it through
  /// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
  /// family) to refetch.
  ///
  /// Signed in, it first waits for the member's unlock tokens to load, so the
  /// first request after a cold start already carries them. A forum a sent
  /// token did not open (still `is_locked`) drops that token: the dead-token
  /// rule (spec §7.4).

  CategoriesProvider call(String? viewer) =>
      CategoriesProvider._(argument: viewer, from: this);

  @override
  String toString() => r'categoriesProvider';
}

/// The forum index for [viewer]: categories, each with its forums and links,
/// in the server's order (`GET /forum/categories/`). Read it through
/// [viewerCategoriesProvider]; invalidate `categoriesProvider` (the whole
/// family) to refetch.
///
/// Signed in, it first waits for the member's unlock tokens to load, so the
/// first request after a cold start already carries them. A forum a sent
/// token did not open (still `is_locked`) drops that token: the dead-token
/// rule (spec §7.4).

abstract class _$Categories extends $AsyncNotifier<List<ForumCategory>> {
  late final _$args = ref.$arg as String?;
  String? get viewer => _$args;

  FutureOr<List<ForumCategory>> build(String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<List<ForumCategory>>, List<ForumCategory>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<List<ForumCategory>>, List<ForumCategory>>,
              AsyncValue<List<ForumCategory>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// The forum index for the current viewer. Synchronous on purpose: it hands
/// over the viewer's own element's state as is, so a new viewer starts from
/// loading, never from the previous viewer's list (see [forumViewerProvider]).

@ProviderFor(viewerCategories)
final viewerCategoriesProvider = ViewerCategoriesProvider._();

/// The forum index for the current viewer. Synchronous on purpose: it hands
/// over the viewer's own element's state as is, so a new viewer starts from
/// loading, never from the previous viewer's list (see [forumViewerProvider]).

final class ViewerCategoriesProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<ForumCategory>>,
          AsyncValue<List<ForumCategory>>,
          AsyncValue<List<ForumCategory>>
        >
    with $Provider<AsyncValue<List<ForumCategory>>> {
  /// The forum index for the current viewer. Synchronous on purpose: it hands
  /// over the viewer's own element's state as is, so a new viewer starts from
  /// loading, never from the previous viewer's list (see [forumViewerProvider]).
  ViewerCategoriesProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'viewerCategoriesProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$viewerCategoriesHash();

  @$internal
  @override
  $ProviderElement<AsyncValue<List<ForumCategory>>> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  AsyncValue<List<ForumCategory>> create(Ref ref) {
    return viewerCategories(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AsyncValue<List<ForumCategory>> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AsyncValue<List<ForumCategory>>>(
        value,
      ),
    );
  }
}

String _$viewerCategoriesHash() => r'54126342d28b90687f97b9474f2517a67b004a85';

/// Every forum a member can post in, in feed order: the flat list the topic
/// screen's header and the search filter read. Derived from
/// [viewerCategoriesProvider] (no request of its own); forums still locked
/// for the viewer are left out.
///
/// Not `whenData`: that turns a failure Riverpod is still retrying into a
/// bare loading state, and the error must stay visible.

@ProviderFor(boards)
final boardsProvider = BoardsProvider._();

/// Every forum a member can post in, in feed order: the flat list the topic
/// screen's header and the search filter read. Derived from
/// [viewerCategoriesProvider] (no request of its own); forums still locked
/// for the viewer are left out.
///
/// Not `whenData`: that turns a failure Riverpod is still retrying into a
/// bare loading state, and the error must stay visible.

final class BoardsProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<ForumBoard>>,
          AsyncValue<List<ForumBoard>>,
          AsyncValue<List<ForumBoard>>
        >
    with $Provider<AsyncValue<List<ForumBoard>>> {
  /// Every forum a member can post in, in feed order: the flat list the topic
  /// screen's header and the search filter read. Derived from
  /// [viewerCategoriesProvider] (no request of its own); forums still locked
  /// for the viewer are left out.
  ///
  /// Not `whenData`: that turns a failure Riverpod is still retrying into a
  /// bare loading state, and the error must stay visible.
  BoardsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'boardsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$boardsHash();

  @$internal
  @override
  $ProviderElement<AsyncValue<List<ForumBoard>>> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  AsyncValue<List<ForumBoard>> create(Ref ref) {
    return boards(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AsyncValue<List<ForumBoard>> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AsyncValue<List<ForumBoard>>>(value),
    );
  }
}

String _$boardsHash() => r'2d4b1a28a8f788fffe696a21b012ad82c6369460';

/// A forum's top contributors: the members with the most posts in it
/// (`GET /forum/boards/{slug}/contributors/`). Keyed on [viewer] because the
/// server leaves out members the viewer has blocked. A 4xx (a locked forum,
/// or a server that predates the endpoint) fails at once; the section that
/// reads it is then simply absent.

@ProviderFor(boardContributors)
final boardContributorsProvider = BoardContributorsFamily._();

/// A forum's top contributors: the members with the most posts in it
/// (`GET /forum/boards/{slug}/contributors/`). Keyed on [viewer] because the
/// server leaves out members the viewer has blocked. A 4xx (a locked forum,
/// or a server that predates the endpoint) fails at once; the section that
/// reads it is then simply absent.

final class BoardContributorsProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<ForumContributor>>,
          List<ForumContributor>,
          FutureOr<List<ForumContributor>>
        >
    with
        $FutureModifier<List<ForumContributor>>,
        $FutureProvider<List<ForumContributor>> {
  /// A forum's top contributors: the members with the most posts in it
  /// (`GET /forum/boards/{slug}/contributors/`). Keyed on [viewer] because the
  /// server leaves out members the viewer has blocked. A 4xx (a locked forum,
  /// or a server that predates the endpoint) fails at once; the section that
  /// reads it is then simply absent.
  BoardContributorsProvider._({
    required BoardContributorsFamily super.from,
    required (String, String?) super.argument,
  }) : super(
         retry: forumRetry,
         name: r'boardContributorsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$boardContributorsHash();

  @override
  String toString() {
    return r'boardContributorsProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  $FutureProviderElement<List<ForumContributor>> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<List<ForumContributor>> create(Ref ref) {
    final argument = this.argument as (String, String?);
    return boardContributors(ref, argument.$1, argument.$2);
  }

  @override
  bool operator ==(Object other) {
    return other is BoardContributorsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$boardContributorsHash() => r'098492c7d41a9f89323f876e81ff5f9e8dfc7089';

/// A forum's top contributors: the members with the most posts in it
/// (`GET /forum/boards/{slug}/contributors/`). Keyed on [viewer] because the
/// server leaves out members the viewer has blocked. A 4xx (a locked forum,
/// or a server that predates the endpoint) fails at once; the section that
/// reads it is then simply absent.

final class BoardContributorsFamily extends $Family
    with
        $FunctionalFamilyOverride<
          FutureOr<List<ForumContributor>>,
          (String, String?)
        > {
  BoardContributorsFamily._()
    : super(
        retry: forumRetry,
        name: r'boardContributorsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A forum's top contributors: the members with the most posts in it
  /// (`GET /forum/boards/{slug}/contributors/`). Keyed on [viewer] because the
  /// server leaves out members the viewer has blocked. A 4xx (a locked forum,
  /// or a server that predates the endpoint) fails at once; the section that
  /// reads it is then simply absent.

  BoardContributorsProvider call(String boardSlug, String? viewer) =>
      BoardContributorsProvider._(argument: (boardSlug, viewer), from: this);

  @override
  String toString() => r'boardContributorsProvider';
}

/// The sort and tag filter chosen on a board's topic list. Lives as long as
/// that list is on screen, so leaving the forum clears it.

@ProviderFor(BoardTopicsFilterState)
final boardTopicsFilterStateProvider = BoardTopicsFilterStateFamily._();

/// The sort and tag filter chosen on a board's topic list. Lives as long as
/// that list is on screen, so leaving the forum clears it.
final class BoardTopicsFilterStateProvider
    extends $NotifierProvider<BoardTopicsFilterState, BoardTopicsFilter> {
  /// The sort and tag filter chosen on a board's topic list. Lives as long as
  /// that list is on screen, so leaving the forum clears it.
  BoardTopicsFilterStateProvider._({
    required BoardTopicsFilterStateFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'boardTopicsFilterStateProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$boardTopicsFilterStateHash();

  @override
  String toString() {
    return r'boardTopicsFilterStateProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  BoardTopicsFilterState create() => BoardTopicsFilterState();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(BoardTopicsFilter value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<BoardTopicsFilter>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is BoardTopicsFilterStateProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$boardTopicsFilterStateHash() =>
    r'2f1d79a033323fed6b3b125625ad1ef2ecac2238';

/// The sort and tag filter chosen on a board's topic list. Lives as long as
/// that list is on screen, so leaving the forum clears it.

final class BoardTopicsFilterStateFamily extends $Family
    with
        $ClassFamilyOverride<
          BoardTopicsFilterState,
          BoardTopicsFilter,
          BoardTopicsFilter,
          BoardTopicsFilter,
          String
        > {
  BoardTopicsFilterStateFamily._()
    : super(
        retry: null,
        name: r'boardTopicsFilterStateProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The sort and tag filter chosen on a board's topic list. Lives as long as
  /// that list is on screen, so leaving the forum clears it.

  BoardTopicsFilterStateProvider call(String boardSlug) =>
      BoardTopicsFilterStateProvider._(argument: boardSlug, from: this);

  @override
  String toString() => r'boardTopicsFilterStateProvider';
}

/// The sort and tag filter chosen on a board's topic list. Lives as long as
/// that list is on screen, so leaving the forum clears it.

abstract class _$BoardTopicsFilterState extends $Notifier<BoardTopicsFilter> {
  late final _$args = ref.$arg as String;
  String get boardSlug => _$args;

  BoardTopicsFilter build(String boardSlug);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<BoardTopicsFilter, BoardTopicsFilter>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<BoardTopicsFilter, BoardTopicsFilter>,
              BoardTopicsFilter,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// Topics in a board, cursor-paginated with [loadMore], in the order and
/// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
/// answers 403 `forum_locked`, which [forumRetry] does not re-request.

@ProviderFor(BoardTopics)
final boardTopicsProvider = BoardTopicsFamily._();

/// Topics in a board, cursor-paginated with [loadMore], in the order and
/// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
/// answers 403 `forum_locked`, which [forumRetry] does not re-request.
final class BoardTopicsProvider
    extends $AsyncNotifierProvider<BoardTopics, PagedList<ForumTopicListItem>> {
  /// Topics in a board, cursor-paginated with [loadMore], in the order and
  /// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
  /// answers 403 `forum_locked`, which [forumRetry] does not re-request.
  BoardTopicsProvider._({
    required BoardTopicsFamily super.from,
    required (String, String?) super.argument,
  }) : super(
         retry: forumRetry,
         name: r'boardTopicsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$boardTopicsHash();

  @override
  String toString() {
    return r'boardTopicsProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  BoardTopics create() => BoardTopics();

  @override
  bool operator ==(Object other) {
    return other is BoardTopicsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$boardTopicsHash() => r'0cacb800ca4245340c87747d8d7fffc77e5767f2';

/// Topics in a board, cursor-paginated with [loadMore], in the order and
/// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
/// answers 403 `forum_locked`, which [forumRetry] does not re-request.

final class BoardTopicsFamily extends $Family
    with
        $ClassFamilyOverride<
          BoardTopics,
          AsyncValue<PagedList<ForumTopicListItem>>,
          PagedList<ForumTopicListItem>,
          FutureOr<PagedList<ForumTopicListItem>>,
          (String, String?)
        > {
  BoardTopicsFamily._()
    : super(
        retry: forumRetry,
        name: r'boardTopicsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Topics in a board, cursor-paginated with [loadMore], in the order and
  /// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
  /// answers 403 `forum_locked`, which [forumRetry] does not re-request.

  BoardTopicsProvider call(String boardSlug, String? viewer) =>
      BoardTopicsProvider._(argument: (boardSlug, viewer), from: this);

  @override
  String toString() => r'boardTopicsProvider';
}

/// Topics in a board, cursor-paginated with [loadMore], in the order and
/// under the tag filter of [boardTopicsFilterStateProvider]. A locked forum
/// answers 403 `forum_locked`, which [forumRetry] does not re-request.

abstract class _$BoardTopics
    extends $AsyncNotifier<PagedList<ForumTopicListItem>> {
  late final _$args = ref.$arg as (String, String?);
  String get boardSlug => _$args.$1;
  String? get viewer => _$args.$2;

  FutureOr<PagedList<ForumTopicListItem>> build(
    String boardSlug,
    String? viewer,
  );
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<PagedList<ForumTopicListItem>>,
              PagedList<ForumTopicListItem>
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<PagedList<ForumTopicListItem>>,
                PagedList<ForumTopicListItem>
              >,
              AsyncValue<PagedList<ForumTopicListItem>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args.$1, _$args.$2));
  }
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).

@ProviderFor(TopicDetail)
final topicDetailProvider = TopicDetailFamily._();

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).
final class TopicDetailProvider
    extends $AsyncNotifierProvider<TopicDetail, ForumTopicDetail> {
  /// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
  /// bookmark toggle and the accepted-answer mark/clear (todo 341).
  TopicDetailProvider._({
    required TopicDetailFamily super.from,
    required (int, String?) super.argument,
  }) : super(
         retry: null,
         name: r'topicDetailProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$topicDetailHash();

  @override
  String toString() {
    return r'topicDetailProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  TopicDetail create() => TopicDetail();

  @override
  bool operator ==(Object other) {
    return other is TopicDetailProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$topicDetailHash() => r'9afe980503042fe56605ec468b084120d3cab6e0';

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).

final class TopicDetailFamily extends $Family
    with
        $ClassFamilyOverride<
          TopicDetail,
          AsyncValue<ForumTopicDetail>,
          ForumTopicDetail,
          FutureOr<ForumTopicDetail>,
          (int, String?)
        > {
  TopicDetailFamily._()
    : super(
        retry: null,
        name: r'topicDetailProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
  /// bookmark toggle and the accepted-answer mark/clear (todo 341).

  TopicDetailProvider call(int topicId, String? viewer) =>
      TopicDetailProvider._(argument: (topicId, viewer), from: this);

  @override
  String toString() => r'topicDetailProvider';
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).

abstract class _$TopicDetail extends $AsyncNotifier<ForumTopicDetail> {
  late final _$args = ref.$arg as (int, String?);
  int get topicId => _$args.$1;
  String? get viewer => _$args.$2;

  FutureOr<ForumTopicDetail> build(int topicId, String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<ForumTopicDetail>, ForumTopicDetail>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<ForumTopicDetail>, ForumTopicDetail>,
              AsyncValue<ForumTopicDetail>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args.$1, _$args.$2));
  }
}

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.

@ProviderFor(ForumUserProfile)
final forumUserProfileProvider = ForumUserProfileFamily._();

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.
final class ForumUserProfileProvider
    extends $AsyncNotifierProvider<ForumUserProfile, ForumProfile> {
  /// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
  /// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.
  ForumUserProfileProvider._({
    required ForumUserProfileFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'forumUserProfileProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$forumUserProfileHash();

  @override
  String toString() {
    return r'forumUserProfileProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  ForumUserProfile create() => ForumUserProfile();

  @override
  bool operator ==(Object other) {
    return other is ForumUserProfileProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$forumUserProfileHash() => r'f65c6faa3309bb3c71d096b986cac701c6cfad78';

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.

final class ForumUserProfileFamily extends $Family
    with
        $ClassFamilyOverride<
          ForumUserProfile,
          AsyncValue<ForumProfile>,
          ForumProfile,
          FutureOr<ForumProfile>,
          String
        > {
  ForumUserProfileFamily._()
    : super(
        retry: null,
        name: r'forumUserProfileProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
  /// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.

  ForumUserProfileProvider call(String username) =>
      ForumUserProfileProvider._(argument: username, from: this);

  @override
  String toString() => r'forumUserProfileProvider';
}

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341) and mute/unmute.

abstract class _$ForumUserProfile extends $AsyncNotifier<ForumProfile> {
  late final _$args = ref.$arg as String;
  String get username => _$args;

  FutureOr<ForumProfile> build(String username);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<AsyncValue<ForumProfile>, ForumProfile>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<ForumProfile>, ForumProfile>,
              AsyncValue<ForumProfile>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// The most recent mute/unmute the viewer performed, from a thread or a
/// profile. Every mounted thread and profile splices it locally, for the
/// reasons [AuthorBlockChanges] gives. Its own provider, so a block and a
/// mute made on one profile both reach a paused thread underneath.

@ProviderFor(AuthorMuteChanges)
final authorMuteChangesProvider = AuthorMuteChangesProvider._();

/// The most recent mute/unmute the viewer performed, from a thread or a
/// profile. Every mounted thread and profile splices it locally, for the
/// reasons [AuthorBlockChanges] gives. Its own provider, so a block and a
/// mute made on one profile both reach a paused thread underneath.
final class AuthorMuteChangesProvider
    extends $NotifierProvider<AuthorMuteChanges, AuthorMuteChange?> {
  /// The most recent mute/unmute the viewer performed, from a thread or a
  /// profile. Every mounted thread and profile splices it locally, for the
  /// reasons [AuthorBlockChanges] gives. Its own provider, so a block and a
  /// mute made on one profile both reach a paused thread underneath.
  AuthorMuteChangesProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'authorMuteChangesProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$authorMuteChangesHash();

  @$internal
  @override
  AuthorMuteChanges create() => AuthorMuteChanges();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AuthorMuteChange? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AuthorMuteChange?>(value),
    );
  }
}

String _$authorMuteChangesHash() => r'f8df4e5873fec438a38c8128ddc8fb79db1e35dd';

/// The most recent mute/unmute the viewer performed, from a thread or a
/// profile. Every mounted thread and profile splices it locally, for the
/// reasons [AuthorBlockChanges] gives. Its own provider, so a block and a
/// mute made on one profile both reach a paused thread underneath.

abstract class _$AuthorMuteChanges extends $Notifier<AuthorMuteChange?> {
  AuthorMuteChange? build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<AuthorMuteChange?, AuthorMuteChange?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AuthorMuteChange?, AuthorMuteChange?>,
              AuthorMuteChange?,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}

/// The most recent block/unblock the viewer performed (todo 341). A block
/// happens on the PROFILE screen but changes what every loaded post by that
/// author should render in a thread mounted underneath — and the profile
/// has no topic id to splice. Invalidating the paged thread would collapse
/// its loaded pages to page 1, so instead each [TopicPosts] listens here
/// and splices `isBlocked` locally. `keepAlive` so an emit is never lost
/// between the profile's call and a thread's listener; listeners are not
/// fired on subscribe, so a newly-built thread never replays a stale event.

@ProviderFor(AuthorBlockChanges)
final authorBlockChangesProvider = AuthorBlockChangesProvider._();

/// The most recent block/unblock the viewer performed (todo 341). A block
/// happens on the PROFILE screen but changes what every loaded post by that
/// author should render in a thread mounted underneath — and the profile
/// has no topic id to splice. Invalidating the paged thread would collapse
/// its loaded pages to page 1, so instead each [TopicPosts] listens here
/// and splices `isBlocked` locally. `keepAlive` so an emit is never lost
/// between the profile's call and a thread's listener; listeners are not
/// fired on subscribe, so a newly-built thread never replays a stale event.
final class AuthorBlockChangesProvider
    extends $NotifierProvider<AuthorBlockChanges, AuthorBlockChange?> {
  /// The most recent block/unblock the viewer performed (todo 341). A block
  /// happens on the PROFILE screen but changes what every loaded post by that
  /// author should render in a thread mounted underneath — and the profile
  /// has no topic id to splice. Invalidating the paged thread would collapse
  /// its loaded pages to page 1, so instead each [TopicPosts] listens here
  /// and splices `isBlocked` locally. `keepAlive` so an emit is never lost
  /// between the profile's call and a thread's listener; listeners are not
  /// fired on subscribe, so a newly-built thread never replays a stale event.
  AuthorBlockChangesProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'authorBlockChangesProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$authorBlockChangesHash();

  @$internal
  @override
  AuthorBlockChanges create() => AuthorBlockChanges();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AuthorBlockChange? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AuthorBlockChange?>(value),
    );
  }
}

String _$authorBlockChangesHash() =>
    r'1a78699ddb5622c8bda709105fd0284648c50c4c';

/// The most recent block/unblock the viewer performed (todo 341). A block
/// happens on the PROFILE screen but changes what every loaded post by that
/// author should render in a thread mounted underneath — and the profile
/// has no topic id to splice. Invalidating the paged thread would collapse
/// its loaded pages to page 1, so instead each [TopicPosts] listens here
/// and splices `isBlocked` locally. `keepAlive` so an emit is never lost
/// between the profile's call and a thread's listener; listeners are not
/// fired on subscribe, so a newly-built thread never replays a stale event.

abstract class _$AuthorBlockChanges extends $Notifier<AuthorBlockChange?> {
  AuthorBlockChange? build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<AuthorBlockChange?, AuthorBlockChange?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AuthorBlockChange?, AuthorBlockChange?>,
              AuthorBlockChange?,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.

@ProviderFor(TopicPosts)
final topicPostsProvider = TopicPostsFamily._();

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.
final class TopicPostsProvider
    extends $AsyncNotifierProvider<TopicPosts, PagedList<ForumPost>> {
  /// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
  /// reaction toggle that updates the affected post in place.
  TopicPostsProvider._({
    required TopicPostsFamily super.from,
    required (int, String?) super.argument,
  }) : super(
         retry: null,
         name: r'topicPostsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$topicPostsHash();

  @override
  String toString() {
    return r'topicPostsProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  TopicPosts create() => TopicPosts();

  @override
  bool operator ==(Object other) {
    return other is TopicPostsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$topicPostsHash() => r'6c8f4a989c88a63ab5088421687ae82e045fa829';

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.

final class TopicPostsFamily extends $Family
    with
        $ClassFamilyOverride<
          TopicPosts,
          AsyncValue<PagedList<ForumPost>>,
          PagedList<ForumPost>,
          FutureOr<PagedList<ForumPost>>,
          (int, String?)
        > {
  TopicPostsFamily._()
    : super(
        retry: null,
        name: r'topicPostsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
  /// reaction toggle that updates the affected post in place.

  TopicPostsProvider call(int topicId, String? viewer) =>
      TopicPostsProvider._(argument: (topicId, viewer), from: this);

  @override
  String toString() => r'topicPostsProvider';
}

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.

abstract class _$TopicPosts extends $AsyncNotifier<PagedList<ForumPost>> {
  late final _$args = ref.$arg as (int, String?);
  int get topicId => _$args.$1;
  String? get viewer => _$args.$2;

  FutureOr<PagedList<ForumPost>> build(int topicId, String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<AsyncValue<PagedList<ForumPost>>, PagedList<ForumPost>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<PagedList<ForumPost>>,
                PagedList<ForumPost>
              >,
              AsyncValue<PagedList<ForumPost>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args.$1, _$args.$2));
  }
}

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
///
/// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
/// clears the mirror on disk (audit F24), and a new viewer must not keep the
/// last one's titles in memory either.

@ProviderFor(RecentTopics)
final recentTopicsProvider = RecentTopicsFamily._();

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
///
/// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
/// clears the mirror on disk (audit F24), and a new viewer must not keep the
/// last one's titles in memory either.
final class RecentTopicsProvider
    extends $AsyncNotifierProvider<RecentTopics, List<ForumTopicStub>> {
  /// Recent topics from the offline delta-sync mirror. On open it runs a delta
  /// sync (consuming `/sync/` upserts + tombstones); if the network is
  /// unavailable it falls back to the cached mirror so the list works offline.
  ///
  /// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
  /// clears the mirror on disk (audit F24), and a new viewer must not keep the
  /// last one's titles in memory either.
  RecentTopicsProvider._({
    required RecentTopicsFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'recentTopicsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$recentTopicsHash();

  @override
  String toString() {
    return r'recentTopicsProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  RecentTopics create() => RecentTopics();

  @override
  bool operator ==(Object other) {
    return other is RecentTopicsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$recentTopicsHash() => r'd2914daa45d35e50829da05d4acfbbe58430ea72';

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
///
/// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
/// clears the mirror on disk (audit F24), and a new viewer must not keep the
/// last one's titles in memory either.

final class RecentTopicsFamily extends $Family
    with
        $ClassFamilyOverride<
          RecentTopics,
          AsyncValue<List<ForumTopicStub>>,
          List<ForumTopicStub>,
          FutureOr<List<ForumTopicStub>>,
          String?
        > {
  RecentTopicsFamily._()
    : super(
        retry: null,
        name: r'recentTopicsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Recent topics from the offline delta-sync mirror. On open it runs a delta
  /// sync (consuming `/sync/` upserts + tombstones); if the network is
  /// unavailable it falls back to the cached mirror so the list works offline.
  ///
  /// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
  /// clears the mirror on disk (audit F24), and a new viewer must not keep the
  /// last one's titles in memory either.

  RecentTopicsProvider call(String? viewer) =>
      RecentTopicsProvider._(argument: viewer, from: this);

  @override
  String toString() => r'recentTopicsProvider';
}

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
///
/// Keyed on [viewer] (see [forumViewerProvider]): every end of a session
/// clears the mirror on disk (audit F24), and a new viewer must not keep the
/// last one's titles in memory either.

abstract class _$RecentTopics extends $AsyncNotifier<List<ForumTopicStub>> {
  late final _$args = ref.$arg as String?;
  String? get viewer => _$args;

  FutureOr<List<ForumTopicStub>> build(String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<AsyncValue<List<ForumTopicStub>>, List<ForumTopicStub>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<List<ForumTopicStub>>,
                List<ForumTopicStub>
              >,
              AsyncValue<List<ForumTopicStub>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// The home activity feed — the [kHomeRecentTopicsLimit] most recent topics
/// with solved/unread state, pictures and recent repliers. Distinct from
/// [RecentTopics], the offline mirror.
///
/// Keyed on [viewer] (see [forumViewerProvider]): the feed honours the
/// member's forum unlocks, so a new viewer must start from loading, never
/// from the previous one's titles.

@ProviderFor(homeRecentTopics)
final homeRecentTopicsProvider = HomeRecentTopicsFamily._();

/// The home activity feed — the [kHomeRecentTopicsLimit] most recent topics
/// with solved/unread state, pictures and recent repliers. Distinct from
/// [RecentTopics], the offline mirror.
///
/// Keyed on [viewer] (see [forumViewerProvider]): the feed honours the
/// member's forum unlocks, so a new viewer must start from loading, never
/// from the previous one's titles.

final class HomeRecentTopicsProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<ForumRecentTopic>>,
          List<ForumRecentTopic>,
          FutureOr<List<ForumRecentTopic>>
        >
    with
        $FutureModifier<List<ForumRecentTopic>>,
        $FutureProvider<List<ForumRecentTopic>> {
  /// The home activity feed — the [kHomeRecentTopicsLimit] most recent topics
  /// with solved/unread state, pictures and recent repliers. Distinct from
  /// [RecentTopics], the offline mirror.
  ///
  /// Keyed on [viewer] (see [forumViewerProvider]): the feed honours the
  /// member's forum unlocks, so a new viewer must start from loading, never
  /// from the previous one's titles.
  HomeRecentTopicsProvider._({
    required HomeRecentTopicsFamily super.from,
    required String? super.argument,
  }) : super(
         retry: forumRetry,
         name: r'homeRecentTopicsProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$homeRecentTopicsHash();

  @override
  String toString() {
    return r'homeRecentTopicsProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<List<ForumRecentTopic>> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<List<ForumRecentTopic>> create(Ref ref) {
    final argument = this.argument as String?;
    return homeRecentTopics(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is HomeRecentTopicsProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$homeRecentTopicsHash() => r'8106bd0ddcb2a60cee8950013c163ac27d4f524f';

/// The home activity feed — the [kHomeRecentTopicsLimit] most recent topics
/// with solved/unread state, pictures and recent repliers. Distinct from
/// [RecentTopics], the offline mirror.
///
/// Keyed on [viewer] (see [forumViewerProvider]): the feed honours the
/// member's forum unlocks, so a new viewer must start from loading, never
/// from the previous one's titles.

final class HomeRecentTopicsFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<List<ForumRecentTopic>>, String?> {
  HomeRecentTopicsFamily._()
    : super(
        retry: forumRetry,
        name: r'homeRecentTopicsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The home activity feed — the [kHomeRecentTopicsLimit] most recent topics
  /// with solved/unread state, pictures and recent repliers. Distinct from
  /// [RecentTopics], the offline mirror.
  ///
  /// Keyed on [viewer] (see [forumViewerProvider]): the feed honours the
  /// member's forum unlocks, so a new viewer must start from loading, never
  /// from the previous one's titles.

  HomeRecentTopicsProvider call(String? viewer) =>
      HomeRecentTopicsProvider._(argument: viewer, from: this);

  @override
  String toString() => r'homeRecentTopicsProvider';
}

/// A topic's latest-replies peek. Kept alive while the forum home is mounted
/// ([forumHomeScopeProvider]), so a re-expanded card does not refetch; the
/// home invalidates it on pull-to-refresh and when the viewer changes.

@ProviderFor(latestReplies)
final latestRepliesProvider = LatestRepliesFamily._();

/// A topic's latest-replies peek. Kept alive while the forum home is mounted
/// ([forumHomeScopeProvider]), so a re-expanded card does not refetch; the
/// home invalidates it on pull-to-refresh and when the viewer changes.

final class LatestRepliesProvider
    extends
        $FunctionalProvider<
          AsyncValue<ForumLatestReplies>,
          ForumLatestReplies,
          FutureOr<ForumLatestReplies>
        >
    with
        $FutureModifier<ForumLatestReplies>,
        $FutureProvider<ForumLatestReplies> {
  /// A topic's latest-replies peek. Kept alive while the forum home is mounted
  /// ([forumHomeScopeProvider]), so a re-expanded card does not refetch; the
  /// home invalidates it on pull-to-refresh and when the viewer changes.
  LatestRepliesProvider._({
    required LatestRepliesFamily super.from,
    required int super.argument,
  }) : super(
         retry: forumRetry,
         name: r'latestRepliesProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$latestRepliesHash();

  @override
  String toString() {
    return r'latestRepliesProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<ForumLatestReplies> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<ForumLatestReplies> create(Ref ref) {
    final argument = this.argument as int;
    return latestReplies(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is LatestRepliesProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$latestRepliesHash() => r'daa94c9dce11233d1792f525c00fd27217c9f0f3';

/// A topic's latest-replies peek. Kept alive while the forum home is mounted
/// ([forumHomeScopeProvider]), so a re-expanded card does not refetch; the
/// home invalidates it on pull-to-refresh and when the viewer changes.

final class LatestRepliesFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<ForumLatestReplies>, int> {
  LatestRepliesFamily._()
    : super(
        retry: forumRetry,
        name: r'latestRepliesProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A topic's latest-replies peek. Kept alive while the forum home is mounted
  /// ([forumHomeScopeProvider]), so a re-expanded card does not refetch; the
  /// home invalidates it on pull-to-refresh and when the viewer changes.

  LatestRepliesProvider call(int topicId) =>
      LatestRepliesProvider._(argument: topicId, from: this);

  @override
  String toString() => r'latestRepliesProvider';
}

/// The forum home's lifetime, for the data that should outlive a widget on
/// the home but not the home itself (spec §6.4: a peek lives "while the
/// screen is alive"). `ForumScreen` watches it; when the screen goes, it is
/// disposed and releases every peek it held. Read with no home mounted, it
/// is disposed at once and a peek is an ordinary autoDispose read.

@ProviderFor(forumHomeScope)
final forumHomeScopeProvider = ForumHomeScopeProvider._();

/// The forum home's lifetime, for the data that should outlive a widget on
/// the home but not the home itself (spec §6.4: a peek lives "while the
/// screen is alive"). `ForumScreen` watches it; when the screen goes, it is
/// disposed and releases every peek it held. Read with no home mounted, it
/// is disposed at once and a peek is an ordinary autoDispose read.

final class ForumHomeScopeProvider
    extends $FunctionalProvider<ForumHomeScope, ForumHomeScope, ForumHomeScope>
    with $Provider<ForumHomeScope> {
  /// The forum home's lifetime, for the data that should outlive a widget on
  /// the home but not the home itself (spec §6.4: a peek lives "while the
  /// screen is alive"). `ForumScreen` watches it; when the screen goes, it is
  /// disposed and releases every peek it held. Read with no home mounted, it
  /// is disposed at once and a peek is an ordinary autoDispose read.
  ForumHomeScopeProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'forumHomeScopeProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$forumHomeScopeHash();

  @$internal
  @override
  $ProviderElement<ForumHomeScope> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  ForumHomeScope create(Ref ref) {
    return forumHomeScope(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ForumHomeScope value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ForumHomeScope>(value),
    );
  }
}

String _$forumHomeScopeHash() => r'39365d0df5f918f71a59f94428f4d564ac638d14';

/// Community counters for the home "Who's online" card.

@ProviderFor(communityStats)
final communityStatsProvider = CommunityStatsProvider._();

/// Community counters for the home "Who's online" card.

final class CommunityStatsProvider
    extends
        $FunctionalProvider<
          AsyncValue<ForumCommunityStats>,
          ForumCommunityStats,
          FutureOr<ForumCommunityStats>
        >
    with
        $FutureModifier<ForumCommunityStats>,
        $FutureProvider<ForumCommunityStats> {
  /// Community counters for the home "Who's online" card.
  CommunityStatsProvider._()
    : super(
        from: null,
        argument: null,
        retry: forumRetry,
        name: r'communityStatsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$communityStatsHash();

  @$internal
  @override
  $FutureProviderElement<ForumCommunityStats> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<ForumCommunityStats> create(Ref ref) {
    return communityStats(ref);
  }
}

String _$communityStatsHash() => r'6ebf247ba745cd1575862dcea97826fa7890c252';

/// The activity card currently expanded on the forum home (one at a time).

@ProviderFor(ExpandedActivityTopic)
final expandedActivityTopicProvider = ExpandedActivityTopicProvider._();

/// The activity card currently expanded on the forum home (one at a time).
final class ExpandedActivityTopicProvider
    extends $NotifierProvider<ExpandedActivityTopic, int?> {
  /// The activity card currently expanded on the forum home (one at a time).
  ExpandedActivityTopicProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'expandedActivityTopicProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$expandedActivityTopicHash();

  @$internal
  @override
  ExpandedActivityTopic create() => ExpandedActivityTopic();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(int? value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<int?>(value),
    );
  }
}

String _$expandedActivityTopicHash() =>
    r'018c0b87a148325e87b8eddbc556da9093405f01';

/// The activity card currently expanded on the forum home (one at a time).

abstract class _$ExpandedActivityTopic extends $Notifier<int?> {
  int? build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<int?, int?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<int?, int?>,
              int?,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}

/// The user's notifications (cursor-paginated, newest first).
///
/// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
/// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
/// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
/// offstage through a session expiry into another account reads a fresh
/// element, never the last member's rows (audit F89).

@ProviderFor(NotificationsFeed)
final notificationsFeedProvider = NotificationsFeedFamily._();

/// The user's notifications (cursor-paginated, newest first).
///
/// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
/// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
/// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
/// offstage through a session expiry into another account reads a fresh
/// element, never the last member's rows (audit F89).
final class NotificationsFeedProvider
    extends
        $AsyncNotifierProvider<
          NotificationsFeed,
          PagedList<ForumNotification>
        > {
  /// The user's notifications (cursor-paginated, newest first).
  ///
  /// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
  /// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
  /// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
  /// offstage through a session expiry into another account reads a fresh
  /// element, never the last member's rows (audit F89).
  NotificationsFeedProvider._({
    required NotificationsFeedFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'notificationsFeedProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$notificationsFeedHash();

  @override
  String toString() {
    return r'notificationsFeedProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  NotificationsFeed create() => NotificationsFeed();

  @override
  bool operator ==(Object other) {
    return other is NotificationsFeedProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$notificationsFeedHash() => r'bfb7adf4006afc418dbaced315861b0729e91ee9';

/// The user's notifications (cursor-paginated, newest first).
///
/// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
/// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
/// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
/// offstage through a session expiry into another account reads a fresh
/// element, never the last member's rows (audit F89).

final class NotificationsFeedFamily extends $Family
    with
        $ClassFamilyOverride<
          NotificationsFeed,
          AsyncValue<PagedList<ForumNotification>>,
          PagedList<ForumNotification>,
          FutureOr<PagedList<ForumNotification>>,
          String?
        > {
  NotificationsFeedFamily._()
    : super(
        retry: null,
        name: r'notificationsFeedProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The user's notifications (cursor-paginated, newest first).
  ///
  /// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
  /// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
  /// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
  /// offstage through a session expiry into another account reads a fresh
  /// element, never the last member's rows (audit F89).

  NotificationsFeedProvider call(String? viewer) =>
      NotificationsFeedProvider._(argument: viewer, from: this);

  @override
  String toString() => r'notificationsFeedProvider';
}

/// The user's notifications (cursor-paginated, newest first).
///
/// The member's own feeds ([NotificationsFeed], [ConversationsFeed],
/// [BookmarksFeed], the DM threads and the two unread counts) are keyed on
/// [viewer] (see [forumViewerProvider]), so a screen the forum branch keeps
/// offstage through a session expiry into another account reads a fresh
/// element, never the last member's rows (audit F89).

abstract class _$NotificationsFeed
    extends $AsyncNotifier<PagedList<ForumNotification>> {
  late final _$args = ref.$arg as String?;
  String? get viewer => _$args;

  FutureOr<PagedList<ForumNotification>> build(String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<PagedList<ForumNotification>>,
              PagedList<ForumNotification>
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<PagedList<ForumNotification>>,
                PagedList<ForumNotification>
              >,
              AsyncValue<PagedList<ForumNotification>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// Unread notification count, for the bell badge.

@ProviderFor(unreadNotificationCount)
final unreadNotificationCountProvider = UnreadNotificationCountFamily._();

/// Unread notification count, for the bell badge.

final class UnreadNotificationCountProvider
    extends $FunctionalProvider<AsyncValue<int>, int, FutureOr<int>>
    with $FutureModifier<int>, $FutureProvider<int> {
  /// Unread notification count, for the bell badge.
  UnreadNotificationCountProvider._({
    required UnreadNotificationCountFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'unreadNotificationCountProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$unreadNotificationCountHash();

  @override
  String toString() {
    return r'unreadNotificationCountProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<int> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<int> create(Ref ref) {
    final argument = this.argument as String?;
    return unreadNotificationCount(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is UnreadNotificationCountProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$unreadNotificationCountHash() =>
    r'b7d76a47979f45777fd0b8efc9bcf08d275b5876';

/// Unread notification count, for the bell badge.

final class UnreadNotificationCountFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<int>, String?> {
  UnreadNotificationCountFamily._()
    : super(
        retry: null,
        name: r'unreadNotificationCountProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Unread notification count, for the bell badge.

  UnreadNotificationCountProvider call(String? viewer) =>
      UnreadNotificationCountProvider._(argument: viewer, from: this);

  @override
  String toString() => r'unreadNotificationCountProvider';
}

/// The user's DM inbox (cursor-paginated, most recent activity first).
/// Keyed on [viewer], like [NotificationsFeed].

@ProviderFor(ConversationsFeed)
final conversationsFeedProvider = ConversationsFeedFamily._();

/// The user's DM inbox (cursor-paginated, most recent activity first).
/// Keyed on [viewer], like [NotificationsFeed].
final class ConversationsFeedProvider
    extends
        $AsyncNotifierProvider<
          ConversationsFeed,
          PagedList<ForumConversation>
        > {
  /// The user's DM inbox (cursor-paginated, most recent activity first).
  /// Keyed on [viewer], like [NotificationsFeed].
  ConversationsFeedProvider._({
    required ConversationsFeedFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'conversationsFeedProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$conversationsFeedHash();

  @override
  String toString() {
    return r'conversationsFeedProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  ConversationsFeed create() => ConversationsFeed();

  @override
  bool operator ==(Object other) {
    return other is ConversationsFeedProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$conversationsFeedHash() => r'eded9389a1b8ecd5f555cc350902c56cb2abce89';

/// The user's DM inbox (cursor-paginated, most recent activity first).
/// Keyed on [viewer], like [NotificationsFeed].

final class ConversationsFeedFamily extends $Family
    with
        $ClassFamilyOverride<
          ConversationsFeed,
          AsyncValue<PagedList<ForumConversation>>,
          PagedList<ForumConversation>,
          FutureOr<PagedList<ForumConversation>>,
          String?
        > {
  ConversationsFeedFamily._()
    : super(
        retry: null,
        name: r'conversationsFeedProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The user's DM inbox (cursor-paginated, most recent activity first).
  /// Keyed on [viewer], like [NotificationsFeed].

  ConversationsFeedProvider call(String? viewer) =>
      ConversationsFeedProvider._(argument: viewer, from: this);

  @override
  String toString() => r'conversationsFeedProvider';
}

/// The user's DM inbox (cursor-paginated, most recent activity first).
/// Keyed on [viewer], like [NotificationsFeed].

abstract class _$ConversationsFeed
    extends $AsyncNotifier<PagedList<ForumConversation>> {
  late final _$args = ref.$arg as String?;
  String? get viewer => _$args;

  FutureOr<PagedList<ForumConversation>> build(String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<PagedList<ForumConversation>>,
              PagedList<ForumConversation>
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<PagedList<ForumConversation>>,
                PagedList<ForumConversation>
              >,
              AsyncValue<PagedList<ForumConversation>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// Conversations with unread messages, for the inbox badge.

@ProviderFor(unreadConversationCount)
final unreadConversationCountProvider = UnreadConversationCountFamily._();

/// Conversations with unread messages, for the inbox badge.

final class UnreadConversationCountProvider
    extends $FunctionalProvider<AsyncValue<int>, int, FutureOr<int>>
    with $FutureModifier<int>, $FutureProvider<int> {
  /// Conversations with unread messages, for the inbox badge.
  UnreadConversationCountProvider._({
    required UnreadConversationCountFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'unreadConversationCountProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$unreadConversationCountHash();

  @override
  String toString() {
    return r'unreadConversationCountProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<int> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<int> create(Ref ref) {
    final argument = this.argument as String?;
    return unreadConversationCount(ref, argument);
  }

  @override
  bool operator ==(Object other) {
    return other is UnreadConversationCountProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$unreadConversationCountHash() =>
    r'2241bee965e4c2cbfefc7c5619bfd56e24242368';

/// Conversations with unread messages, for the inbox badge.

final class UnreadConversationCountFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<int>, String?> {
  UnreadConversationCountFamily._()
    : super(
        retry: null,
        name: r'unreadConversationCountProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Conversations with unread messages, for the inbox badge.

  UnreadConversationCountProvider call(String? viewer) =>
      UnreadConversationCountProvider._(argument: viewer, from: this);

  @override
  String toString() => r'unreadConversationCountProvider';
}

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341). Keyed on [viewer], like
/// [NotificationsFeed].

@ProviderFor(BookmarksFeed)
final bookmarksFeedProvider = BookmarksFeedFamily._();

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341). Keyed on [viewer], like
/// [NotificationsFeed].
final class BookmarksFeedProvider
    extends
        $AsyncNotifierProvider<BookmarksFeed, PagedList<ForumTopicListItem>> {
  /// The viewer's bookmarked topics (cursor-paginated, most recently
  /// bookmarked first — todo 341). Keyed on [viewer], like
  /// [NotificationsFeed].
  BookmarksFeedProvider._({
    required BookmarksFeedFamily super.from,
    required String? super.argument,
  }) : super(
         retry: null,
         name: r'bookmarksFeedProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$bookmarksFeedHash();

  @override
  String toString() {
    return r'bookmarksFeedProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  BookmarksFeed create() => BookmarksFeed();

  @override
  bool operator ==(Object other) {
    return other is BookmarksFeedProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$bookmarksFeedHash() => r'e4496a6ed6123cfd7e133947c3d004860801ea5c';

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341). Keyed on [viewer], like
/// [NotificationsFeed].

final class BookmarksFeedFamily extends $Family
    with
        $ClassFamilyOverride<
          BookmarksFeed,
          AsyncValue<PagedList<ForumTopicListItem>>,
          PagedList<ForumTopicListItem>,
          FutureOr<PagedList<ForumTopicListItem>>,
          String?
        > {
  BookmarksFeedFamily._()
    : super(
        retry: null,
        name: r'bookmarksFeedProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The viewer's bookmarked topics (cursor-paginated, most recently
  /// bookmarked first — todo 341). Keyed on [viewer], like
  /// [NotificationsFeed].

  BookmarksFeedProvider call(String? viewer) =>
      BookmarksFeedProvider._(argument: viewer, from: this);

  @override
  String toString() => r'bookmarksFeedProvider';
}

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341). Keyed on [viewer], like
/// [NotificationsFeed].

abstract class _$BookmarksFeed
    extends $AsyncNotifier<PagedList<ForumTopicListItem>> {
  late final _$args = ref.$arg as String?;
  String? get viewer => _$args;

  FutureOr<PagedList<ForumTopicListItem>> build(String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<PagedList<ForumTopicListItem>>,
              PagedList<ForumTopicListItem>
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<PagedList<ForumTopicListItem>>,
                PagedList<ForumTopicListItem>
              >,
              AsyncValue<PagedList<ForumTopicListItem>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}

/// A 1:1 DM thread with [username] (todo 339): resolves the conversation
/// (absent until first send), pages older messages, and sends.
///
/// Every page from the API is newest-first; it is reversed on the way in so
/// [ConversationThreadState.messages] reads oldest → newest like a chat.

@ProviderFor(ConversationThread)
final conversationThreadProvider = ConversationThreadFamily._();

/// A 1:1 DM thread with [username] (todo 339): resolves the conversation
/// (absent until first send), pages older messages, and sends.
///
/// Every page from the API is newest-first; it is reversed on the way in so
/// [ConversationThreadState.messages] reads oldest → newest like a chat.
final class ConversationThreadProvider
    extends
        $AsyncNotifierProvider<ConversationThread, ConversationThreadState> {
  /// A 1:1 DM thread with [username] (todo 339): resolves the conversation
  /// (absent until first send), pages older messages, and sends.
  ///
  /// Every page from the API is newest-first; it is reversed on the way in so
  /// [ConversationThreadState.messages] reads oldest → newest like a chat.
  ConversationThreadProvider._({
    required ConversationThreadFamily super.from,
    required (String, String?) super.argument,
  }) : super(
         retry: null,
         name: r'conversationThreadProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$conversationThreadHash();

  @override
  String toString() {
    return r'conversationThreadProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  ConversationThread create() => ConversationThread();

  @override
  bool operator ==(Object other) {
    return other is ConversationThreadProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$conversationThreadHash() =>
    r'febd86c665573a5dd809de3ba16cb1155e92e118';

/// A 1:1 DM thread with [username] (todo 339): resolves the conversation
/// (absent until first send), pages older messages, and sends.
///
/// Every page from the API is newest-first; it is reversed on the way in so
/// [ConversationThreadState.messages] reads oldest → newest like a chat.

final class ConversationThreadFamily extends $Family
    with
        $ClassFamilyOverride<
          ConversationThread,
          AsyncValue<ConversationThreadState>,
          ConversationThreadState,
          FutureOr<ConversationThreadState>,
          (String, String?)
        > {
  ConversationThreadFamily._()
    : super(
        retry: null,
        name: r'conversationThreadProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A 1:1 DM thread with [username] (todo 339): resolves the conversation
  /// (absent until first send), pages older messages, and sends.
  ///
  /// Every page from the API is newest-first; it is reversed on the way in so
  /// [ConversationThreadState.messages] reads oldest → newest like a chat.

  ConversationThreadProvider call(String username, String? viewer) =>
      ConversationThreadProvider._(argument: (username, viewer), from: this);

  @override
  String toString() => r'conversationThreadProvider';
}

/// A 1:1 DM thread with [username] (todo 339): resolves the conversation
/// (absent until first send), pages older messages, and sends.
///
/// Every page from the API is newest-first; it is reversed on the way in so
/// [ConversationThreadState.messages] reads oldest → newest like a chat.

abstract class _$ConversationThread
    extends $AsyncNotifier<ConversationThreadState> {
  late final _$args = ref.$arg as (String, String?);
  String get username => _$args.$1;
  String? get viewer => _$args.$2;

  FutureOr<ConversationThreadState> build(String username, String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<ConversationThreadState>,
              ConversationThreadState
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<ConversationThreadState>,
                ConversationThreadState
              >,
              AsyncValue<ConversationThreadState>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args.$1, _$args.$2));
  }
}

/// A group DM thread by conversation id (todo 350). Same state shape and
/// paging as [ConversationThread]; sends through the by-id endpoint and
/// manages the roster. The contract has no conversation-detail endpoint, so
/// the inbox row is taken from the mounted inbox when it holds it (row tap,
/// or a just-created group spliced in) and otherwise from inbox page 1; a
/// row not found there leaves [ConversationThreadState.conversation] null —
/// messages and sending still work by id, only the title/roster degrade.

@ProviderFor(GroupConversationThread)
final groupConversationThreadProvider = GroupConversationThreadFamily._();

/// A group DM thread by conversation id (todo 350). Same state shape and
/// paging as [ConversationThread]; sends through the by-id endpoint and
/// manages the roster. The contract has no conversation-detail endpoint, so
/// the inbox row is taken from the mounted inbox when it holds it (row tap,
/// or a just-created group spliced in) and otherwise from inbox page 1; a
/// row not found there leaves [ConversationThreadState.conversation] null —
/// messages and sending still work by id, only the title/roster degrade.
final class GroupConversationThreadProvider
    extends
        $AsyncNotifierProvider<
          GroupConversationThread,
          ConversationThreadState
        > {
  /// A group DM thread by conversation id (todo 350). Same state shape and
  /// paging as [ConversationThread]; sends through the by-id endpoint and
  /// manages the roster. The contract has no conversation-detail endpoint, so
  /// the inbox row is taken from the mounted inbox when it holds it (row tap,
  /// or a just-created group spliced in) and otherwise from inbox page 1; a
  /// row not found there leaves [ConversationThreadState.conversation] null —
  /// messages and sending still work by id, only the title/roster degrade.
  GroupConversationThreadProvider._({
    required GroupConversationThreadFamily super.from,
    required (int, String?) super.argument,
  }) : super(
         retry: null,
         name: r'groupConversationThreadProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$groupConversationThreadHash();

  @override
  String toString() {
    return r'groupConversationThreadProvider'
        ''
        '$argument';
  }

  @$internal
  @override
  GroupConversationThread create() => GroupConversationThread();

  @override
  bool operator ==(Object other) {
    return other is GroupConversationThreadProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$groupConversationThreadHash() =>
    r'c429cb185dbe33e19972c0166f9af406ef8144a3';

/// A group DM thread by conversation id (todo 350). Same state shape and
/// paging as [ConversationThread]; sends through the by-id endpoint and
/// manages the roster. The contract has no conversation-detail endpoint, so
/// the inbox row is taken from the mounted inbox when it holds it (row tap,
/// or a just-created group spliced in) and otherwise from inbox page 1; a
/// row not found there leaves [ConversationThreadState.conversation] null —
/// messages and sending still work by id, only the title/roster degrade.

final class GroupConversationThreadFamily extends $Family
    with
        $ClassFamilyOverride<
          GroupConversationThread,
          AsyncValue<ConversationThreadState>,
          ConversationThreadState,
          FutureOr<ConversationThreadState>,
          (int, String?)
        > {
  GroupConversationThreadFamily._()
    : super(
        retry: null,
        name: r'groupConversationThreadProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A group DM thread by conversation id (todo 350). Same state shape and
  /// paging as [ConversationThread]; sends through the by-id endpoint and
  /// manages the roster. The contract has no conversation-detail endpoint, so
  /// the inbox row is taken from the mounted inbox when it holds it (row tap,
  /// or a just-created group spliced in) and otherwise from inbox page 1; a
  /// row not found there leaves [ConversationThreadState.conversation] null —
  /// messages and sending still work by id, only the title/roster degrade.

  GroupConversationThreadProvider call(int conversationId, String? viewer) =>
      GroupConversationThreadProvider._(
        argument: (conversationId, viewer),
        from: this,
      );

  @override
  String toString() => r'groupConversationThreadProvider';
}

/// A group DM thread by conversation id (todo 350). Same state shape and
/// paging as [ConversationThread]; sends through the by-id endpoint and
/// manages the roster. The contract has no conversation-detail endpoint, so
/// the inbox row is taken from the mounted inbox when it holds it (row tap,
/// or a just-created group spliced in) and otherwise from inbox page 1; a
/// row not found there leaves [ConversationThreadState.conversation] null —
/// messages and sending still work by id, only the title/roster degrade.

abstract class _$GroupConversationThread
    extends $AsyncNotifier<ConversationThreadState> {
  late final _$args = ref.$arg as (int, String?);
  int get conversationId => _$args.$1;
  String? get viewer => _$args.$2;

  FutureOr<ConversationThreadState> build(int conversationId, String? viewer);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref
            as $Ref<
              AsyncValue<ConversationThreadState>,
              ConversationThreadState
            >;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<ConversationThreadState>,
                ConversationThreadState
              >,
              AsyncValue<ConversationThreadState>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args.$1, _$args.$2));
  }
}

/// The viewer's all-time stats + earned badges for the forum home (todo 341
/// wave 4). Auth-only — mount it only for a signed-in member.

@ProviderFor(meStats)
final meStatsProvider = MeStatsProvider._();

/// The viewer's all-time stats + earned badges for the forum home (todo 341
/// wave 4). Auth-only — mount it only for a signed-in member.

final class MeStatsProvider
    extends
        $FunctionalProvider<
          AsyncValue<ForumMyStats>,
          ForumMyStats,
          FutureOr<ForumMyStats>
        >
    with $FutureModifier<ForumMyStats>, $FutureProvider<ForumMyStats> {
  /// The viewer's all-time stats + earned badges for the forum home (todo 341
  /// wave 4). Auth-only — mount it only for a signed-in member.
  MeStatsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'meStatsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$meStatsHash();

  @$internal
  @override
  $FutureProviderElement<ForumMyStats> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<ForumMyStats> create(Ref ref) {
    return meStats(ref);
  }
}

String _$meStatsHash() => r'ccf2903f184b3d41fd565130f4e835b888fcfce6';

/// Highest-trust members with their online flag, for the forum home's
/// experts strip (todo 341 wave 4).

@ProviderFor(experts)
final expertsProvider = ExpertsProvider._();

/// Highest-trust members with their online flag, for the forum home's
/// experts strip (todo 341 wave 4).

final class ExpertsProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<ForumExpert>>,
          List<ForumExpert>,
          FutureOr<List<ForumExpert>>
        >
    with
        $FutureModifier<List<ForumExpert>>,
        $FutureProvider<List<ForumExpert>> {
  /// Highest-trust members with their online flag, for the forum home's
  /// experts strip (todo 341 wave 4).
  ExpertsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'expertsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$expertsHash();

  @$internal
  @override
  $FutureProviderElement<List<ForumExpert>> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<List<ForumExpert>> create(Ref ref) {
    return experts(ref);
  }
}

String _$expertsHash() => r'624fd2152794f14d1ede133c8ea76ce3a9869a2f';

/// The composer's @mention autocomplete (todo 341 wave 4): a debounced,
/// cancel-on-supersede username lookup. Every [lookup] cancels the pending
/// timer AND bumps a generation so a response already in flight for an
/// older prefix discards itself instead of overwriting a newer one — the
/// web's `searchToken` discipline. A failed lookup shows nothing; it never
/// blocks typing. autoDispose: the timer dies with the composer.

@ProviderFor(MentionSearch)
final mentionSearchProvider = MentionSearchProvider._();

/// The composer's @mention autocomplete (todo 341 wave 4): a debounced,
/// cancel-on-supersede username lookup. Every [lookup] cancels the pending
/// timer AND bumps a generation so a response already in flight for an
/// older prefix discards itself instead of overwriting a newer one — the
/// web's `searchToken` discipline. A failed lookup shows nothing; it never
/// blocks typing. autoDispose: the timer dies with the composer.
final class MentionSearchProvider
    extends $NotifierProvider<MentionSearch, MentionSearchState> {
  /// The composer's @mention autocomplete (todo 341 wave 4): a debounced,
  /// cancel-on-supersede username lookup. Every [lookup] cancels the pending
  /// timer AND bumps a generation so a response already in flight for an
  /// older prefix discards itself instead of overwriting a newer one — the
  /// web's `searchToken` discipline. A failed lookup shows nothing; it never
  /// blocks typing. autoDispose: the timer dies with the composer.
  MentionSearchProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'mentionSearchProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$mentionSearchHash();

  @$internal
  @override
  MentionSearch create() => MentionSearch();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(MentionSearchState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<MentionSearchState>(value),
    );
  }
}

String _$mentionSearchHash() => r'a41d3049ebc3d3834bd5ab5d4e253e4ad78192b5';

/// The composer's @mention autocomplete (todo 341 wave 4): a debounced,
/// cancel-on-supersede username lookup. Every [lookup] cancels the pending
/// timer AND bumps a generation so a response already in flight for an
/// older prefix discards itself instead of overwriting a newer one — the
/// web's `searchToken` discipline. A failed lookup shows nothing; it never
/// blocks typing. autoDispose: the timer dies with the composer.

abstract class _$MentionSearch extends $Notifier<MentionSearchState> {
  MentionSearchState build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<MentionSearchState, MentionSearchState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<MentionSearchState, MentionSearchState>,
              MentionSearchState,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}

/// Full-text forum search. Offset-paginated (see [ForumSearchPage]) — a
/// "load more" fetches the next `page` and appends to both sections, since
/// the two `*_has_more` flags share one page cursor.

@ProviderFor(ForumSearch)
final forumSearchProvider = ForumSearchProvider._();

/// Full-text forum search. Offset-paginated (see [ForumSearchPage]) — a
/// "load more" fetches the next `page` and appends to both sections, since
/// the two `*_has_more` flags share one page cursor.
final class ForumSearchProvider
    extends $NotifierProvider<ForumSearch, ForumSearchResult> {
  /// Full-text forum search. Offset-paginated (see [ForumSearchPage]) — a
  /// "load more" fetches the next `page` and appends to both sections, since
  /// the two `*_has_more` flags share one page cursor.
  ForumSearchProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'forumSearchProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$forumSearchHash();

  @$internal
  @override
  ForumSearch create() => ForumSearch();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ForumSearchResult value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ForumSearchResult>(value),
    );
  }
}

String _$forumSearchHash() => r'abf4cffe6695a7ddc636a79d111de98c4a551498';

/// Full-text forum search. Offset-paginated (see [ForumSearchPage]) — a
/// "load more" fetches the next `page` and appends to both sections, since
/// the two `*_has_more` flags share one page cursor.

abstract class _$ForumSearch extends $Notifier<ForumSearchResult> {
  ForumSearchResult build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<ForumSearchResult, ForumSearchResult>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<ForumSearchResult, ForumSearchResult>,
              ForumSearchResult,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}
