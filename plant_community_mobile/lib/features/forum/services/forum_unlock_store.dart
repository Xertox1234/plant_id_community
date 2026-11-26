import 'dart:convert';

import 'package:flutter/foundation.dart' show debugPrint, kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';

part 'forum_unlock_store.g.dart';

/// The password forums one member has unlocked on this phone: forum id to the
/// server's signed unlock token (spec §7.4). No `toString`, on purpose: the
/// tokens are credentials and must never reach a log.
class ForumUnlocks {
  const ForumUnlocks({required this.uid, required this.tokens});

  /// The Firebase uid of the member the tokens were issued to.
  final String uid;

  /// Forum id to token, oldest unlock first.
  final Map<int, String> tokens;
}

/// Where [ForumUnlocks] live between launches. Every method is total: a
/// storage failure or a corrupt value reads as "no unlocks" and never throws,
/// so it can never break the forum.
abstract class ForumUnlockStore {
  Future<ForumUnlocks?> load();
  Future<void> save(ForumUnlocks unlocks);
  Future<void> clear();
}

/// [ForumUnlockStore] in flutter_secure_storage with the default
/// `FlutterSecureStorage()` options (the auth tokens in `auth_service.dart`
/// use `first_unlock_this_device` since todo 715; these unlocks are only
/// read in the foreground), under one key holding
/// `{"uid": ..., "tokens": {"<forum id>": "<token>"}}`.
class SecureForumUnlockStore implements ForumUnlockStore {
  const SecureForumUnlockStore([this._storage = const FlutterSecureStorage()]);

  static const String storageKey = 'forum_unlock_tokens';

  final FlutterSecureStorage _storage;

  @override
  Future<ForumUnlocks?> load() async {
    try {
      final raw = await _storage.read(key: storageKey);
      if (raw == null) return null;
      return _decode(raw);
    } catch (_) {
      // Never log the error: a FormatException quotes the stored value, and
      // the stored value holds the tokens.
      _note('read');
      return null;
    }
  }

  @override
  Future<void> save(ForumUnlocks unlocks) async {
    try {
      await _storage.write(
        key: storageKey,
        value: jsonEncode({
          'uid': unlocks.uid,
          'tokens': {
            for (final e in unlocks.tokens.entries) '${e.key}': e.value,
          },
        }),
      );
    } catch (_) {
      _note('write');
    }
  }

  @override
  Future<void> clear() async {
    try {
      await _storage.delete(key: storageKey);
    } catch (_) {
      _note('delete');
    }
  }

  static ForumUnlocks? _decode(String raw) {
    final data = jsonDecode(raw);
    if (data is! Map) return null;
    final uid = data['uid'];
    final tokens = data['tokens'];
    if (uid is! String || uid.isEmpty || tokens is! Map) return null;
    final parsed = <int, String>{};
    for (final entry in tokens.entries) {
      final id = int.tryParse('${entry.key}');
      final token = entry.value;
      if (id == null || token is! String || token.isEmpty) continue;
      parsed[id] = token;
    }
    return ForumUnlocks(uid: uid, tokens: parsed);
  }

  static void _note(String what) {
    if (kDebugMode) debugPrint('[FORUM] unlock store $what failed');
  }
}

/// Injectable so tests can use an in-memory store.
final forumUnlockStoreProvider = Provider<ForumUnlockStore>(
  (ref) => const SecureForumUnlockStore(),
);

/// The unlocks sent on a forum request: the newest
/// [ApiService.maxForumUnlockTokens] (the server reads no more), newest first.
/// The categories feed snapshots the same list to know which tokens a
/// response answered.
List<MapEntry<int, String>> forumUnlockEntriesToSend(Map<int, String> tokens) {
  return tokens.entries
      .toList()
      .reversed
      .take(ApiService.maxForumUnlockTokens)
      .toList(growable: false);
}

/// The signed-in member's unlocks, kept in step with the store and with the
/// `X-Forum-Unlock` header [ApiService] sends.
///
/// Keyed on the signed-in member's Firebase uid (the same "signed in" as the
/// forum home's viewer: a Firebase user still waiting on its JWT is not):
/// - signed out (also at launch, before the session restores): no header,
///   and the store is left alone;
/// - signed in as the member the store holds: their tokens;
/// - signed in as anyone else: the store is cleared.
///
/// Every end of a session (`signOut()`, a session expiry, a sign-out
/// Firebase reports, a declined consent) and an account switch clear the
/// store and the header and end the unlock session (`AuthService`'s
/// `_forgetForumData`, through [ApiService], since this provider depends on
/// the auth one and not the other way round; audit F130);
/// `_resetForViewer` on the forum home must not, since it also runs at launch
/// and on an author block.
@Riverpod(keepAlive: true, name: 'forumUnlocksProvider')
class ForumUnlocksController extends _$ForumUnlocksController {
  /// Bumped by every [build], so work started under one member never lands
  /// under the next.
  int _builds = 0;
  String? _uid;

  /// [ApiService.forumUnlockSession] when this build began. Sign-out ends
  /// that session before the auth state stops naming the member, so work
  /// still running under it (a late unlock answer, a dead-token drop) is
  /// neither sent nor saved in that window.
  int _session = 0;

  @override
  Future<Map<int, String>> build() async {
    final build = ++_builds;
    // A listen, not a watch: the rebuild a member change causes is lazy
    // (nothing may read this provider for a while), and the header must not
    // wait for it. A watch would dispose this build before a listener ran.
    final uid = ref.read(authServiceProvider.select(_signedInUid));
    ref.listen(authServiceProvider.select(_signedInUid), (previous, next) {
      if (previous == next) return;
      ref.read(apiServiceProvider).setForumUnlockTokens(const []);
      ref.invalidateSelf();
    });
    _uid = uid;
    _session = ref.read(apiServiceProvider).forumUnlockSession;
    // Nothing from the previous viewer is sent while this one loads.
    ref.read(apiServiceProvider).setForumUnlockTokens(const []);
    if (uid == null) return const {};

    final store = ref.read(forumUnlockStoreProvider);
    final stored = await store.load();
    if (_superseded(build)) return const {};
    var tokens = <int, String>{};
    if (stored != null && stored.uid == uid) {
      tokens = Map.of(stored.tokens);
    } else if (stored != null) {
      // Another member's unlocks: they end on this phone.
      await store.clear();
      if (_superseded(build)) return const {};
    }
    _sendHeader(tokens);
    return tokens;
  }

  static String? _signedInUid(AuthState s) =>
      s.isAuthenticated ? s.firebaseUser?.uid : null;

  bool _superseded(int build) =>
      !ref.mounted ||
      build != _builds ||
      ref.read(apiServiceProvider).forumUnlockSession != _session;

  void _sendHeader(Map<int, String> tokens) {
    ref.read(apiServiceProvider).setForumUnlockTokens([
      for (final e in forumUnlockEntriesToSend(tokens)) e.value,
    ]);
  }

  /// Keep [token] for [forumId] (a fresh unlock) for the member [forUid]: the
  /// uid that sent the password. A no-op when signed out, and when the
  /// signed-in member is no longer [forUid] (an account switch while the
  /// unlock was out), so one member's token is never kept under another's.
  Future<void> add(int forumId, String token, {required String forUid}) async {
    if (token.isEmpty || forUid.isEmpty) return;
    await _mutate((tokens) {
      // Removed first so the newest unlock is last: it is sent first.
      tokens
        ..remove(forumId)
        ..[forumId] = token;
    }, forUid: forUid);
  }

  /// Forget [forumId]'s token. With [ifToken], only when the stored token is
  /// still that one: a token stored since is never dropped by an older
  /// answer.
  Future<void> drop(int forumId, {String? ifToken}) async {
    await _mutate((tokens) {
      if (ifToken != null && tokens[forumId] != ifToken) return;
      tokens.remove(forumId);
    });
  }

  /// Forget every unlock: state, store and header.
  Future<void> clear() async {
    final build = _builds;
    await future;
    if (_superseded(build)) return;
    state = const AsyncData({});
    _sendHeader(const {});
    await ref.read(forumUnlockStoreProvider).clear();
  }

  /// With [forUid], only while that member is this build's member. An
  /// account switch invalidates this provider, so [future] waits for the new
  /// member's build and [_uid] is theirs by then.
  Future<void> _mutate(
    void Function(Map<int, String> tokens) change, {
    String? forUid,
  }) async {
    final build = _builds;
    await future;
    final uid = _uid;
    if (_superseded(build) || uid == null) return;
    if (forUid != null && forUid != uid) return;
    final current = state.value ?? const <int, String>{};
    final next = Map<int, String>.of(current);
    change(next);
    if (_sameTokens(next, current)) return;
    state = AsyncData(next);
    _sendHeader(next);
    await ref
        .read(forumUnlockStoreProvider)
        .save(ForumUnlocks(uid: uid, tokens: next));
  }
}

bool _sameTokens(Map<int, String> a, Map<int, String> b) {
  if (a.length != b.length) return false;
  for (final e in a.entries) {
    if (b[e.key] != e.value) return false;
  }
  return true;
}
