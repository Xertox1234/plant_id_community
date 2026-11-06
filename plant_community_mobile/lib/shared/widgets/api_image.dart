import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/api_service.dart';
import '../../services/auth_service.dart';

/// The cache key of the private-photo store (its own files and database).
const privatePhotoCacheKey = 'privateApiPhotos';

/// Fetches with the token [ApiService] holds NOW, not the one captured when
/// the widget was built: a token refreshed while a result screen is open
/// would otherwise 401 the next photo load (scan-2 audit L14).
@visibleForTesting
class LiveTokenFileService extends HttpFileService {
  LiveTokenFileService(this._api, {super.httpClient});

  final ApiService Function() _api;

  @override
  Future<FileServiceResponse> get(String url, {Map<String, String>? headers}) {
    // The captured Authorization is never sent: after a sign-out it would be
    // the previous user's token. Only the token held now goes out, and none
    // when there is none.
    final merged = {...?headers}..remove('Authorization');
    final live = ApiImage.headersFor(_api(), url);
    if (live != null) merged.addAll(live);
    return super.get(url, headers: merged);
  }
}

/// The store for the API's private photos, separate from the default cache
/// (which public images keep using) so it can be emptied on its own.
final privatePhotoCacheManagerProvider = Provider<BaseCacheManager>(
  (ref) => PrivatePhotoCacheManager(
    Config(
      privatePhotoCacheKey,
      stalePeriod: const Duration(days: 7),
      maxNrOfCacheObjects: 200,
      fileService: LiveTokenFileService(() => ref.read(apiServiceProvider)),
    ),
  ),
);

/// A photo store that can list the keys of the files it holds on disk, so
/// one scan's photos can be found among them (from earlier sessions too).
abstract interface class ListsStoredKeys {
  Future<List<String>> storedKeys();
}

/// The private-photo [CacheManager], able to list its stored keys.
class PrivatePhotoCacheManager extends CacheManager implements ListsStoredKeys {
  PrivatePhotoCacheManager(super.config) : _repo = config.repo;

  final CacheInfoRepository _repo;

  @override
  Future<List<String>> storedKeys() async {
    // Opening is counted per connection: this pair leaves the store's own
    // connection open.
    await _repo.open();
    try {
      return [for (final o in await _repo.getAllObjects()) o.key];
    } finally {
      await _repo.close();
    }
  }
}

/// The private cache keys [ApiImage] has used this session: the in-memory
/// image cache cannot be listed, so eviction looks here.
final _sessionPhotoKeys = <String>{};

/// [privatePhotoCacheManagerProvider], emptied whenever the signed-in user
/// changes (sign-out, account switch): private scan photos must not outlive
/// the session that loaded them (scan-2 audit M7).
final privatePhotoCacheProvider = Provider<BaseCacheManager>((ref) {
  final manager = ref.watch(privatePhotoCacheManagerProvider);
  ref.listen<String?>(currentUserIdProvider, (previous, next) {
    // A signed-in user leaving (sign-out, account switch). Not null -> uid:
    // that is the session restoring at launch, and the per-user key already
    // keeps another account's files unreachable.
    if (previous != null && previous != next) {
      unawaited(clearPrivatePhotos(manager));
    }
  });
  return manager;
});

/// Empties the private-photo store on disk and every decoded image in memory
/// (the in-memory cache keys on the URL too, so it would serve them still).
Future<void> clearPrivatePhotos(BaseCacheManager manager) async {
  PaintingBinding.instance.imageCache
    ..clear()
    ..clearLiveImages();
  _sessionPhotoKeys.clear();
  await manager.emptyCache();
}

/// Removes every cached photo of scan [jobId] (all roles, any user key) from
/// [manager] on disk and from the decoded-image cache in memory, after the
/// server erased them (dismiss, remove). A key matches when it holds
/// `/scans/<jobId>/photos/`. Best effort: a store that cannot be listed
/// still loses the keys used this session.
Future<void> evictScanPhotos(BaseCacheManager manager, String jobId) async {
  final marker = '/scans/$jobId/photos/';
  final keys = <String>{..._sessionPhotoKeys};
  if (manager is ListsStoredKeys) {
    try {
      keys.addAll(await (manager as ListsStoredKeys).storedKeys());
    } catch (e) {
      debugPrint('[API_IMAGE] Listing stored photos failed: ${e.runtimeType}');
    }
  }
  final images = PaintingBinding.instance.imageCache;
  for (final key in keys.where((k) => k.contains(marker)).toList()) {
    final bar = key.indexOf('|');
    final url = bar < 0 ? key : key.substring(bar + 1);
    // Same equality as the provider [ApiImage] builds: cacheKey and scale.
    images.evict(CachedNetworkImageProvider(url, cacheKey: key));
    _sessionPhotoKeys.remove(key);
    await manager.removeFile(key);
  }
}

/// Records [key] as used this session (what [ApiImage] does for an API
/// photo), for tests of [evictScanPhotos].
@visibleForTesting
void debugRecordPhotoKey(String key) => _sessionPhotoKeys.add(key);

/// A network image that signs in for the app's own private photo URLs.
///
/// Scan photos are served by the API behind `Authorization: Bearer`, so a
/// plain [CachedNetworkImage] would 401. The header goes only to URLs on the
/// API's own origin (scheme, host and port compared as parsed parts, never a
/// substring), so a look-alike host or a third-party URL (the older Firebase
/// Storage entries) never sees the token and loads as it always did.
///
/// API photos go to [privatePhotoCacheProvider] under a key scoped by the
/// signed-in user, so even a file the sign-out clear missed (the app was
/// killed first) can never be served to another account.
class ApiImage extends ConsumerWidget {
  const ApiImage({
    super.key,
    required this.url,
    this.fit = BoxFit.cover,
    this.placeholder,
    this.errorWidget,
  });

  final String url;
  final BoxFit fit;
  final PlaceholderWidgetBuilder? placeholder;
  final LoadingErrorWidgetBuilder? errorWidget;

  /// The headers [url] needs, or null when it needs none.
  @visibleForTesting
  static Map<String, String>? headersFor(ApiService api, String url) {
    final token = api.authToken;
    if (token == null || token.isEmpty) return null;
    final target = Uri.tryParse(url);
    final origin = Uri.tryParse(api.baseUrl);
    if (target == null || origin == null) return null;
    if (!target.hasScheme || !origin.hasScheme || origin.host.isEmpty) {
      return null;
    }
    final sameOrigin =
        target.scheme == origin.scheme &&
        target.host == origin.host &&
        target.port == origin.port;
    if (!sameOrigin) return null;
    return {'Authorization': 'Bearer $token', 'Accept': 'image/*'};
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final headers = headersFor(ref.watch(apiServiceProvider), url);
    final private = headers != null;
    // Only API photos need the user: public images never read auth state.
    final uid = private ? ref.watch(currentUserIdProvider) : null;
    final cacheKey = private ? '${uid ?? '-'}|$url' : null;
    if (cacheKey != null) _sessionPhotoKeys.add(cacheKey);
    return CachedNetworkImage(
      imageUrl: url,
      fit: fit,
      httpHeaders: headers,
      cacheManager: private ? ref.watch(privatePhotoCacheProvider) : null,
      cacheKey: cacheKey,
      placeholder: placeholder,
      errorWidget: errorWidget,
    );
  }
}
