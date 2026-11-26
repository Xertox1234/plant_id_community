import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../models/models.dart';

/// Apply a `/sync/` delta to a topic map, keyed by topic id.
///
/// Pure and side-effect-free so the sync logic can be exercised without any
/// platform I/O: [upserts] overwrite/insert, [deleted] tombstones remove.
/// Returns a new map (the input is not mutated).
Map<int, ForumTopicStub> applyForumSyncDelta(
  Map<int, ForumTopicStub> current, {
  required List<ForumTopicStub> upserts,
  required List<ForumTombstone> deleted,
}) {
  final next = Map<int, ForumTopicStub>.of(current);
  for (final stub in upserts) {
    next[stub.id] = stub;
  }
  for (final tombstone in deleted) {
    next.remove(tombstone.topicId);
  }
  return next;
}

/// Local persistence for the forum offline topic mirror + its sync cursor.
///
/// Two implementations: [InMemoryForumSyncStore] (tests / default) and
/// [FileForumSyncStore] (device, JSON file). Keeping the persistence behind
/// this seam means the pure delta logic (`applyForumSyncDelta`) and the
/// [ForumSyncService] pagination loop are tested against the in-memory impl,
/// while `path_provider` — which throws in headless `flutter test` — is never
/// touched by the test suite.
///
/// The mirror holds topic titles and one cursor for whoever synced last, so
/// every end of a session (and an account switch) [clear]s it (audit F24).
/// A sync that was running when it was cleared must not write the last
/// account's rows back: it takes [generation] before it loads and writes
/// through [saveSnapshot], which drops a write from an older generation.
abstract class ForumSyncStore {
  Future<ForumSyncCursor> loadCursor();
  Future<void> saveCursor(ForumSyncCursor cursor);
  Future<Map<int, ForumTopicStub>> loadTopics();
  Future<void> saveTopics(Map<int, ForumTopicStub> topics);

  /// Bumped by every [clear], synchronously.
  int get generation;

  /// Save [topics] and [cursor] together, only while the store is still at
  /// [generation]. Returns false, writing nothing, once a [clear] has run
  /// since.
  Future<bool> saveSnapshot(
    Map<int, ForumTopicStub> topics,
    ForumSyncCursor cursor, {
    required int generation,
  });

  /// Forget the mirror and the cursor, on disk and in memory. Never throws.
  Future<void> clear();
}

/// In-memory store. Used by tests and as the safe default when no persistent
/// store is available.
class InMemoryForumSyncStore implements ForumSyncStore {
  ForumSyncCursor _cursor = const ForumSyncCursor();
  Map<int, ForumTopicStub> _topics = {};
  int _generation = 0;

  @override
  int get generation => _generation;

  @override
  Future<ForumSyncCursor> loadCursor() async => _cursor;

  @override
  Future<void> saveCursor(ForumSyncCursor cursor) async => _cursor = cursor;

  @override
  Future<Map<int, ForumTopicStub>> loadTopics() async =>
      Map<int, ForumTopicStub>.of(_topics);

  @override
  Future<void> saveTopics(Map<int, ForumTopicStub> topics) async =>
      _topics = Map<int, ForumTopicStub>.of(topics);

  @override
  Future<bool> saveSnapshot(
    Map<int, ForumTopicStub> topics,
    ForumSyncCursor cursor, {
    required int generation,
  }) async {
    if (generation != _generation) return false;
    _topics = Map<int, ForumTopicStub>.of(topics);
    _cursor = cursor;
    return true;
  }

  @override
  Future<void> clear() async {
    _generation++;
    _topics = {};
    _cursor = const ForumSyncCursor();
  }
}

/// JSON-file-backed store under the app documents directory. Deliberately
/// thin: all delta logic lives in [applyForumSyncDelta] / [ForumSyncService].
///
/// Every operation runs on one serial chain, so a [clear] can neither be
/// overtaken by a load that repopulates the memory copy nor by a write that
/// recreates the file after the delete.
class FileForumSyncStore implements ForumSyncStore {
  FileForumSyncStore({
    this.fileName = 'forum_sync_cache.json',
    Future<Directory> Function()? directory,
  }) : _directory = directory ?? getApplicationDocumentsDirectory;

  final String fileName;
  final Future<Directory> Function() _directory;
  File? _cachedFile;
  int _generation = 0;

  /// In-memory copy of the decoded cache. This store is the only writer of the
  /// file, so once loaded it stays authoritative — every method reads/writes
  /// this map instead of re-decoding the file (a sync run touches the store
  /// 4× and would otherwise decode the whole file each time).
  Map<String, dynamic>? _data;

  /// The tail of the serial chain every operation runs on.
  Future<void> _tail = Future<void>.value();

  Future<T> _serial<T>(Future<T> Function() operation) {
    final result = _tail.then((_) => operation());
    _tail = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  @override
  int get generation => _generation;

  Future<File> _file() async {
    if (_cachedFile != null) return _cachedFile!;
    final dir = await _directory();
    return _cachedFile = File(p.join(dir.path, fileName));
  }

  Future<Map<String, dynamic>> _load() async {
    if (_data != null) return _data!;
    try {
      final file = await _file();
      if (await file.exists()) {
        final raw = await file.readAsString();
        if (raw.isNotEmpty) {
          return _data = jsonDecode(raw) as Map<String, dynamic>;
        }
      }
    } catch (_) {
      // A corrupt/unreadable cache should degrade to "nothing synced yet",
      // never crash the forum.
    }
    return _data = <String, dynamic>{};
  }

  Future<void> _persist() async {
    final file = await _file();
    await file.writeAsString(jsonEncode(_data ?? const {}), flush: true);
  }

  @override
  Future<ForumSyncCursor> loadCursor() => _serial(() async {
    final cursor = (await _load())['cursor'];
    if (cursor is Map<String, dynamic>) {
      return ForumSyncCursor.fromJson(cursor);
    }
    return const ForumSyncCursor();
  });

  @override
  Future<void> saveCursor(ForumSyncCursor cursor) => _serial(() async {
    (await _load())['cursor'] = cursor.toJson();
    await _persist();
  });

  @override
  Future<Map<int, ForumTopicStub>> loadTopics() => _serial(() async {
    final list = (await _load())['topics'];
    final result = <int, ForumTopicStub>{};
    if (list is List) {
      for (final entry in list.whereType<Map<String, dynamic>>()) {
        final stub = ForumTopicStub.fromJson(entry);
        result[stub.id] = stub;
      }
    }
    return result;
  });

  @override
  Future<void> saveTopics(Map<int, ForumTopicStub> topics) => _serial(() async {
    (await _load())['topics'] = topics.values.map((s) => s.toJson()).toList();
    await _persist();
  });

  @override
  Future<bool> saveSnapshot(
    Map<int, ForumTopicStub> topics,
    ForumSyncCursor cursor, {
    required int generation,
  }) => _serial(() async {
    // Checked on the chain: a clear() queued ahead of this write has bumped
    // the generation (synchronously) and emptied the file by now.
    if (generation != _generation) return false;
    final data = await _load();
    data['topics'] = topics.values.map((s) => s.toJson()).toList();
    data['cursor'] = cursor.toJson();
    await _persist();
    return true;
  });

  @override
  Future<void> clear() {
    // Synchronously, so a sync running now sees it before its next write.
    _generation++;
    return _serial(() async {
      _data = <String, dynamic>{};
      try {
        final file = await _file();
        if (await file.exists()) await file.delete();
      } catch (_) {
        // Nothing to delete (no documents directory in a test), or the
        // platform refused: the memory copy is empty either way, and the
        // next save overwrites the file.
      }
    });
  }
}

/// Injectable sync store. Production uses the file-backed store; tests
/// override this with an [InMemoryForumSyncStore].
final forumSyncStoreProvider = Provider<ForumSyncStore>(
  (ref) => FileForumSyncStore(),
);
