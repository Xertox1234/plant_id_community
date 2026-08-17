// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'forum_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Forum boards (not paginated).

@ProviderFor(Boards)
final boardsProvider = BoardsProvider._();

/// Forum boards (not paginated).
final class BoardsProvider
    extends $AsyncNotifierProvider<Boards, List<ForumBoard>> {
  /// Forum boards (not paginated).
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
  Boards create() => Boards();
}

String _$boardsHash() => r'3d4413bfd0114dee61d95ae0665b4d8131a50afb';

/// Forum boards (not paginated).

abstract class _$Boards extends $AsyncNotifier<List<ForumBoard>> {
  FutureOr<List<ForumBoard>> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<List<ForumBoard>>, List<ForumBoard>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<List<ForumBoard>>, List<ForumBoard>>,
              AsyncValue<List<ForumBoard>>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

/// Topics in a board, cursor-paginated with [loadMore].

@ProviderFor(BoardTopics)
final boardTopicsProvider = BoardTopicsFamily._();

/// Topics in a board, cursor-paginated with [loadMore].
final class BoardTopicsProvider
    extends $AsyncNotifierProvider<BoardTopics, PagedList<ForumTopicListItem>> {
  /// Topics in a board, cursor-paginated with [loadMore].
  BoardTopicsProvider._({
    required BoardTopicsFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
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
        '($argument)';
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

String _$boardTopicsHash() => r'e3ceae0252f9b4dc891e48cf03f7a0a2e9572942';

/// Topics in a board, cursor-paginated with [loadMore].

final class BoardTopicsFamily extends $Family
    with
        $ClassFamilyOverride<
          BoardTopics,
          AsyncValue<PagedList<ForumTopicListItem>>,
          PagedList<ForumTopicListItem>,
          FutureOr<PagedList<ForumTopicListItem>>,
          String
        > {
  BoardTopicsFamily._()
    : super(
        retry: null,
        name: r'boardTopicsProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Topics in a board, cursor-paginated with [loadMore].

  BoardTopicsProvider call(String boardSlug) =>
      BoardTopicsProvider._(argument: boardSlug, from: this);

  @override
  String toString() => r'boardTopicsProvider';
}

/// Topics in a board, cursor-paginated with [loadMore].

abstract class _$BoardTopics
    extends $AsyncNotifier<PagedList<ForumTopicListItem>> {
  late final _$args = ref.$arg as String;
  String get boardSlug => _$args;

  FutureOr<PagedList<ForumTopicListItem>> build(String boardSlug);
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, () => build(_$args));
  }
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293).

@ProviderFor(TopicDetail)
final topicDetailProvider = TopicDetailFamily._();

/// A single topic's detail, plus subscribe/unsubscribe (todo 293).
final class TopicDetailProvider
    extends $AsyncNotifierProvider<TopicDetail, ForumTopicDetail> {
  /// A single topic's detail, plus subscribe/unsubscribe (todo 293).
  TopicDetailProvider._({
    required TopicDetailFamily super.from,
    required int super.argument,
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
        '($argument)';
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

String _$topicDetailHash() => r'5fa285fd1947476cbbb4ae065e9d26026c89592e';

/// A single topic's detail, plus subscribe/unsubscribe (todo 293).

final class TopicDetailFamily extends $Family
    with
        $ClassFamilyOverride<
          TopicDetail,
          AsyncValue<ForumTopicDetail>,
          ForumTopicDetail,
          FutureOr<ForumTopicDetail>,
          int
        > {
  TopicDetailFamily._()
    : super(
        retry: null,
        name: r'topicDetailProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// A single topic's detail, plus subscribe/unsubscribe (todo 293).

  TopicDetailProvider call(int topicId) =>
      TopicDetailProvider._(argument: topicId, from: this);

  @override
  String toString() => r'topicDetailProvider';
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293).

abstract class _$TopicDetail extends $AsyncNotifier<ForumTopicDetail> {
  late final _$args = ref.$arg as int;
  int get topicId => _$args;

  FutureOr<ForumTopicDetail> build(int topicId);
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, () => build(_$args));
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
    required int super.argument,
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
        '($argument)';
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

String _$topicPostsHash() => r'512a6a121e564a3353bb16ccfe521a6036751331';

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.

final class TopicPostsFamily extends $Family
    with
        $ClassFamilyOverride<
          TopicPosts,
          AsyncValue<PagedList<ForumPost>>,
          PagedList<ForumPost>,
          FutureOr<PagedList<ForumPost>>,
          int
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

  TopicPostsProvider call(int topicId) =>
      TopicPostsProvider._(argument: topicId, from: this);

  @override
  String toString() => r'topicPostsProvider';
}

/// Posts in a topic (oldest-first), cursor-paginated with [loadMore], plus a
/// reaction toggle that updates the affected post in place.

abstract class _$TopicPosts extends $AsyncNotifier<PagedList<ForumPost>> {
  late final _$args = ref.$arg as int;
  int get topicId => _$args;

  FutureOr<PagedList<ForumPost>> build(int topicId);
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, () => build(_$args));
  }
}

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.

@ProviderFor(RecentTopics)
final recentTopicsProvider = RecentTopicsProvider._();

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.
final class RecentTopicsProvider
    extends $AsyncNotifierProvider<RecentTopics, List<ForumTopicStub>> {
  /// Recent topics from the offline delta-sync mirror. On open it runs a delta
  /// sync (consuming `/sync/` upserts + tombstones); if the network is
  /// unavailable it falls back to the cached mirror so the list works offline.
  RecentTopicsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'recentTopicsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$recentTopicsHash();

  @$internal
  @override
  RecentTopics create() => RecentTopics();
}

String _$recentTopicsHash() => r'cdcb6d8f9a4e74121f3c1ec6624c30f74aa578a5';

/// Recent topics from the offline delta-sync mirror. On open it runs a delta
/// sync (consuming `/sync/` upserts + tombstones); if the network is
/// unavailable it falls back to the cached mirror so the list works offline.

abstract class _$RecentTopics extends $AsyncNotifier<List<ForumTopicStub>> {
  FutureOr<List<ForumTopicStub>> build();
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, build);
  }
}

/// The user's notifications (cursor-paginated, newest first).

@ProviderFor(NotificationsFeed)
final notificationsFeedProvider = NotificationsFeedProvider._();

/// The user's notifications (cursor-paginated, newest first).
final class NotificationsFeedProvider
    extends
        $AsyncNotifierProvider<
          NotificationsFeed,
          PagedList<ForumNotification>
        > {
  /// The user's notifications (cursor-paginated, newest first).
  NotificationsFeedProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'notificationsFeedProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$notificationsFeedHash();

  @$internal
  @override
  NotificationsFeed create() => NotificationsFeed();
}

String _$notificationsFeedHash() => r'a5d19458edf41647f2c59a1851c4251a141e9160';

/// The user's notifications (cursor-paginated, newest first).

abstract class _$NotificationsFeed
    extends $AsyncNotifier<PagedList<ForumNotification>> {
  FutureOr<PagedList<ForumNotification>> build();
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, build);
  }
}

/// Unread notification count, for the bell badge.

@ProviderFor(unreadNotificationCount)
final unreadNotificationCountProvider = UnreadNotificationCountProvider._();

/// Unread notification count, for the bell badge.

final class UnreadNotificationCountProvider
    extends $FunctionalProvider<AsyncValue<int>, int, FutureOr<int>>
    with $FutureModifier<int>, $FutureProvider<int> {
  /// Unread notification count, for the bell badge.
  UnreadNotificationCountProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'unreadNotificationCountProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$unreadNotificationCountHash();

  @$internal
  @override
  $FutureProviderElement<int> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<int> create(Ref ref) {
    return unreadNotificationCount(ref);
  }
}

String _$unreadNotificationCountHash() =>
    r'3784b4dd8f950ce5e47db8f36a1de116af0f98bc';
