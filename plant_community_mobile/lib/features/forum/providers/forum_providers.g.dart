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

String _$topicDetailHash() => r'53a58642f5691840b609ff0c0d2ccfd5cd84b5b6';

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).

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

  /// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
  /// bookmark toggle and the accepted-answer mark/clear (todo 341).

  TopicDetailProvider call(int topicId) =>
      TopicDetailProvider._(argument: topicId, from: this);

  @override
  String toString() => r'topicDetailProvider';
}

/// A single topic's detail, plus subscribe/unsubscribe (todo 293), the
/// bookmark toggle and the accepted-answer mark/clear (todo 341).

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

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341).

@ProviderFor(ForumUserProfile)
final forumUserProfileProvider = ForumUserProfileFamily._();

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341).
final class ForumUserProfileProvider
    extends $AsyncNotifierProvider<ForumUserProfile, ForumProfile> {
  /// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
  /// plus the viewer's block/unblock of that member (todo 341).
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

String _$forumUserProfileHash() => r'c233b82c86ec4604ae18852faaac33203e9fcb07';

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341).

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
  /// plus the viewer's block/unblock of that member (todo 341).

  ForumUserProfileProvider call(String username) =>
      ForumUserProfileProvider._(argument: username, from: this);

  @override
  String toString() => r'forumUserProfileProvider';
}

/// A public forum profile, keyed by username (`GET /forum/users/{username}/`),
/// plus the viewer's block/unblock of that member (todo 341).

abstract class _$ForumUserProfile extends $AsyncNotifier<ForumProfile> {
  late final _$args = ref.$arg as String;
  String get username => _$args;

  FutureOr<ForumProfile> build(String username);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<ForumProfile>, ForumProfile>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<ForumProfile>, ForumProfile>,
              AsyncValue<ForumProfile>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
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
  void runBuild() {
    final ref = this.ref as $Ref<AuthorBlockChange?, AuthorBlockChange?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AuthorBlockChange?, AuthorBlockChange?>,
              AuthorBlockChange?,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
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

String _$topicPostsHash() => r'9f0a5d3f37a25d7330a968e11cab567599a4c784';

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

/// The user's DM inbox (cursor-paginated, most recent activity first).

@ProviderFor(ConversationsFeed)
final conversationsFeedProvider = ConversationsFeedProvider._();

/// The user's DM inbox (cursor-paginated, most recent activity first).
final class ConversationsFeedProvider
    extends
        $AsyncNotifierProvider<
          ConversationsFeed,
          PagedList<ForumConversation>
        > {
  /// The user's DM inbox (cursor-paginated, most recent activity first).
  ConversationsFeedProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'conversationsFeedProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$conversationsFeedHash();

  @$internal
  @override
  ConversationsFeed create() => ConversationsFeed();
}

String _$conversationsFeedHash() => r'563bc5e01b5e7dbc3bef4262373b4a42141d1776';

/// The user's DM inbox (cursor-paginated, most recent activity first).

abstract class _$ConversationsFeed
    extends $AsyncNotifier<PagedList<ForumConversation>> {
  FutureOr<PagedList<ForumConversation>> build();
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, build);
  }
}

/// Conversations with unread messages, for the inbox badge.

@ProviderFor(unreadConversationCount)
final unreadConversationCountProvider = UnreadConversationCountProvider._();

/// Conversations with unread messages, for the inbox badge.

final class UnreadConversationCountProvider
    extends $FunctionalProvider<AsyncValue<int>, int, FutureOr<int>>
    with $FutureModifier<int>, $FutureProvider<int> {
  /// Conversations with unread messages, for the inbox badge.
  UnreadConversationCountProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'unreadConversationCountProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$unreadConversationCountHash();

  @$internal
  @override
  $FutureProviderElement<int> $createElement($ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<int> create(Ref ref) {
    return unreadConversationCount(ref);
  }
}

String _$unreadConversationCountHash() =>
    r'7e9a51b095a5ef04f5d7029917574f955b32a89f';

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341).

@ProviderFor(BookmarksFeed)
final bookmarksFeedProvider = BookmarksFeedProvider._();

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341).
final class BookmarksFeedProvider
    extends
        $AsyncNotifierProvider<BookmarksFeed, PagedList<ForumTopicListItem>> {
  /// The viewer's bookmarked topics (cursor-paginated, most recently
  /// bookmarked first — todo 341).
  BookmarksFeedProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'bookmarksFeedProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$bookmarksFeedHash();

  @$internal
  @override
  BookmarksFeed create() => BookmarksFeed();
}

String _$bookmarksFeedHash() => r'91a4e431dffd7886366c3a89c4385b363f20e686';

/// The viewer's bookmarked topics (cursor-paginated, most recently
/// bookmarked first — todo 341).

abstract class _$BookmarksFeed
    extends $AsyncNotifier<PagedList<ForumTopicListItem>> {
  FutureOr<PagedList<ForumTopicListItem>> build();
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
    element.handleCreate(ref, build);
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
    required String super.argument,
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
        '($argument)';
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
    r'd6466cc5f39a39a1d25775d866d8fbcf66239ab4';

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
          String
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

  ConversationThreadProvider call(String username) =>
      ConversationThreadProvider._(argument: username, from: this);

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
  late final _$args = ref.$arg as String;
  String get username => _$args;

  FutureOr<ConversationThreadState> build(String username);
  @$mustCallSuper
  @override
  void runBuild() {
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
    element.handleCreate(ref, () => build(_$args));
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
  void runBuild() {
    final ref = this.ref as $Ref<MentionSearchState, MentionSearchState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<MentionSearchState, MentionSearchState>,
              MentionSearchState,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
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
  void runBuild() {
    final ref = this.ref as $Ref<ForumSearchResult, ForumSearchResult>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<ForumSearchResult, ForumSearchResult>,
              ForumSearchResult,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
