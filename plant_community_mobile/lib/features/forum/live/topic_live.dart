import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import 'forum_live_channel.dart';
import 'forum_live_client.dart';
import 'forum_live_event.dart';
import 'live_updates_settings.dart';

part 'topic_live.g.dart';

/// What the thread screen renders for live replies.
@immutable
class TopicLiveState {
  const TopicLiveState({
    this.status = LiveStatus.off,
    this.pendingCount = 0,
    this.flashIds = const {},
    this.introSeq = 0,
  });

  final LiveStatus status;

  /// New replies waiting behind the "N new replies" pill.
  final int pendingCount;

  /// Posts to highlight: inserted live, or revealed by the pill.
  final Set<int> flashIds;

  /// Goes up by one when the first-time "Replies now appear live." toast is
  /// due.
  final int introSeq;

  bool get gone => status == LiveStatus.gone;

  TopicLiveState copyWith({
    LiveStatus? status,
    int? pendingCount,
    Set<int>? flashIds,
    int? introSeq,
  }) => TopicLiveState(
    status: status ?? this.status,
    pendingCount: pendingCount ?? this.pendingCount,
    flashIds: flashIds ?? this.flashIds,
    introSeq: introSeq ?? this.introSeq,
  );
}

/// The debounce on topic refetches (`topic.updated`, a removed answer).
const _topicRefetchDelay = Duration(milliseconds: 500);

/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.
@riverpod
class TopicLive extends _$TopicLive {
  ForumLiveClient? _client;
  bool _suspended = false;
  bool _atBottom = true;

  /// Own replies in flight; `post.created` events are held meanwhile.
  int _ownReplies = 0;
  final List<int> _held = [];
  final Set<int> _creating = {};
  final Set<int> _updating = {};
  bool _introAsked = false;
  Timer? _topicTimer;

  @override
  TopicLiveState build(int topicId) {
    final signedIn = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    final enabled = ref.watch(liveUpdatesSettingProvider);
    ref.onDispose(_shutdown);
    if (!signedIn || !enabled || _suspended) return const TopicLiveState();
    final client = _newClient();
    _client = client;
    // Started after build returns: the client reports its first status
    // synchronously, and build may not write state.
    scheduleMicrotask(() {
      if (identical(client, _client)) client.start();
    });
    return const TopicLiveState(status: LiveStatus.connecting);
  }

  /// The scroll position, from the screen: a live reply slides in only when
  /// the reader is at the bottom.
  void setReaderAtBottom(bool atBottom) => _atBottom = atBottom;

  /// The app was hidden: close the socket, and fetch nothing until [resume].
  void suspend() {
    if (_suspended) return;
    _suspended = true;
    _topicTimer?.cancel();
    _closeClient();
    if (!state.gone) state = state.copyWith(status: LiveStatus.off);
  }

  /// The app is shown again: one new connection, which catches up on open.
  /// This makes one new attempt even after 4503 or 4429.
  void resume() {
    if (!_suspended) return;
    _suspended = false;
    if (state.gone) return;
    final signedIn = ref.read(authServiceProvider).isAuthenticated;
    if (!signedIn || !ref.read(liveUpdatesSettingProvider)) return;
    final client = _newClient();
    _client = client;
    client.start();
  }

  /// The reader's own reply is being written: hold `post.created` events
  /// until [endOwnReply], so it never shows twice or counts in the pill.
  void beginOwnReply() => _ownReplies++;

  /// After the reply's refresh walk settles, whether it worked or not. A held
  /// event whose post is now loaded is dropped; any other is applied.
  void endOwnReply() {
    if (_ownReplies == 0) return;
    _ownReplies--;
    if (_ownReplies > 0) return;
    final held = [..._held];
    _held.clear();
    for (final id in held) {
      if (!_inList(id)) unawaited(_created(id));
    }
  }

  /// The pill was tapped: walk every page, highlight the new replies, and
  /// return the first one's id (null when there is none) for the screen to
  /// scroll to.
  Future<int?> takePending() async {
    final taken = state.pendingCount;
    try {
      await ref.read(topicPostsProvider(topicId).notifier).refreshAfterReply();
    } catch (_) {
      return null;
    }
    if (!ref.mounted) return null;
    final replies = (_posts?.items ?? const <ForumPost>[])
        .where((p) => !p.isOpeningPost)
        .toList();
    final count = math.min(taken, replies.length);
    final fresh = replies
        .sublist(replies.length - count)
        .map((p) => p.id)
        .toList();
    state = state.copyWith(
      pendingCount: math.max(0, state.pendingCount - taken),
      flashIds: {...state.flashIds, ...fresh},
    );
    return fresh.isEmpty ? null : fresh.first;
  }

  /// The highlight on [postId] has finished.
  void clearFlash(int postId) {
    if (!state.flashIds.contains(postId)) return;
    state = state.copyWith(flashIds: {...state.flashIds}..remove(postId));
  }

  ForumLiveClient _newClient() {
    final api = ref.read(apiServiceProvider);
    late final ForumLiveClient client;
    client = ForumLiveClient(
      connect: ref.read(forumLiveConnectorProvider),
      uri: topicLiveUri(api.baseUrl, topicId),
      token: () => api.authToken,
      refreshAuth: _refreshAuth,
      onEvent: (event) {
        if (identical(client, _client)) _onEvent(event);
      },
      onOpen: () {
        if (identical(client, _client)) unawaited(_catchUp(client));
      },
      onStatus: (status) {
        if (!identical(client, _client)) return;
        if (status == LiveStatus.gone) {
          _goGone();
        } else {
          state = state.copyWith(status: status);
        }
      },
    );
    return client;
  }

  void _closeClient() {
    final client = _client;
    // Cleared first, so the client's own `off` report is dropped.
    _client = null;
    if (client != null) unawaited(client.close());
  }

  void _shutdown() {
    _topicTimer?.cancel();
    _closeClient();
  }

  /// D2: on mobile the REST bearer is the socket bearer, so a peek read
  /// with an expired token 401s and ApiService refreshes it (or signs the
  /// user out, which closes the socket through the auth watch).
  Future<void> _refreshAuth() async {
    try {
      await ref.read(forumApiProvider).fetchTopicDetail(topicId, peek: true);
    } catch (_) {}
  }

  PagedList<ForumPost>? get _posts =>
      ref.read(topicPostsProvider(topicId)).asData?.value;

  bool _inList(int postId) => _posts?.items.any((p) => p.id == postId) ?? false;

  /// D9: on every open, the server's reply count is the truth. A result
  /// that arrives after this connection stopped (4503, 4429) or was
  /// replaced is dropped, so it can't show a pill while nothing is live.
  Future<void> _catchUp(ForumLiveClient client) async {
    final ForumTopicDetail fresh;
    try {
      fresh = await ref
          .read(forumApiProvider)
          .fetchTopicDetail(topicId, peek: true);
    } catch (_) {
      return;
    }
    if (!ref.mounted ||
        !identical(client, _client) ||
        state.status != LiveStatus.live) {
      return;
    }
    ref.read(topicDetailProvider(topicId).notifier).applyPeek(fresh);
    final posts = _posts;
    if (_ownReplies > 0 || posts == null || posts.hasMore) return;
    final loaded = posts.items.where((p) => !p.isOpeningPost).length;
    state = state.copyWith(
      pendingCount: math.max(0, fresh.replyCount - loaded),
    );
  }

  void _onEvent(LiveEvent event) {
    if (event.topicId != topicId) return;
    switch (event.type) {
      case LiveEventType.postCreated:
        final id = event.postId!;
        if (_ownReplies > 0) {
          _held.add(id);
        } else {
          unawaited(_created(id));
        }
      case LiveEventType.postUpdated:
        unawaited(_updated(event.postId!));
      case LiveEventType.postRemoved:
        _removed(event.postId!);
      case LiveEventType.topicUpdated:
        _scheduleTopicRefetch();
      case LiveEventType.topicRemoved:
        _goGone();
    }
  }

  Future<void> _created(int postId) async {
    if (_inList(postId) || !_creating.add(postId)) return;
    final client = _client;
    ForumPost? post;
    try {
      post = await ref.read(forumApiProvider).fetchPost(postId);
    } catch (_) {
      post = null;
    } finally {
      _creating.remove(postId);
    }
    if (!ref.mounted ||
        !identical(client, _client) ||
        post == null ||
        _inList(postId)) {
      return;
    }
    if (_ownReplies > 0) {
      _held.add(postId);
      return;
    }
    final posts = _posts;
    if (posts == null) return;
    if (_atBottom && !posts.hasMore && state.pendingCount == 0) {
      ref.read(topicPostsProvider(topicId).notifier).applyLivePost(post);
      state = state.copyWith(flashIds: {...state.flashIds, postId});
    } else {
      state = state.copyWith(pendingCount: state.pendingCount + 1);
    }
    unawaited(_maybeIntro());
  }

  Future<void> _updated(int postId) async {
    if (!_inList(postId) || !_updating.add(postId)) return;
    ForumPost? post;
    try {
      post = await ref.read(forumApiProvider).fetchPost(postId);
    } catch (_) {
      post = null;
    } finally {
      _updating.remove(postId);
    }
    if (!ref.mounted || post == null) return;
    ref.read(topicPostsProvider(topicId).notifier).applyEditedPost(post);
  }

  void _removed(int postId) {
    ref.read(topicPostsProvider(topicId).notifier).removeLocal(postId);
    clearFlash(postId);
    final solved = ref
        .read(topicDetailProvider(topicId))
        .asData
        ?.value
        .solvedPostId;
    if (solved == postId) _scheduleTopicRefetch();
  }

  void _scheduleTopicRefetch() {
    _topicTimer?.cancel();
    _topicTimer = Timer(_topicRefetchDelay, () => unawaited(_refetchTopic()));
  }

  Future<void> _refetchTopic() async {
    final ForumTopicDetail fresh;
    try {
      fresh = await ref
          .read(forumApiProvider)
          .fetchTopicDetail(topicId, peek: true);
    } catch (_) {
      return;
    }
    if (!ref.mounted || state.gone) return;
    ref.read(topicDetailProvider(topicId).notifier).applyPeek(fresh);
  }

  void _goGone() {
    _topicTimer?.cancel();
    _closeClient();
    state = state.copyWith(status: LiveStatus.gone);
  }

  /// D18: the intro is due on the first event-driven insert or pill of the
  /// session, never on a catch-up pill, and once per device.
  Future<void> _maybeIntro() async {
    if (_introAsked) return;
    _introAsked = true;
    final due = await ref.read(liveToastFlagsProvider).takeIntro();
    if (due && ref.mounted) {
      state = state.copyWith(introSeq: state.introSeq + 1);
    }
  }
}
