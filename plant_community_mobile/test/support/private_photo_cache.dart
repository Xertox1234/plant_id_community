import 'dart:async';

import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/api_image.dart';

/// A private-photo store that never loads (the image stays on its
/// placeholder) and counts how often it was emptied.
class FakePhotoCache extends Fake implements BaseCacheManager {
  int emptied = 0;

  @override
  Stream<FileResponse> getFileStream(
    String url, {
    String? key,
    Map<String, String>? headers,
    bool withProgress = false,
  }) => StreamController<FileResponse>().stream;

  @override
  Future<void> emptyCache() async => emptied++;
}

/// Overrides for a widget test that renders an [ApiImage] of an API URL:
/// no real cache on disk, and a signed-in user to scope the cache key.
List<Override> privatePhotoOverrides({
  FakePhotoCache? cache,
  String? uid = 'user-1',
}) => [
  privatePhotoCacheManagerProvider.overrideWithValue(cache ?? FakePhotoCache()),
  currentUserIdProvider.overrideWithValue(uid),
];
