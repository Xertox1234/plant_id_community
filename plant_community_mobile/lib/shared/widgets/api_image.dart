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
    final live = ApiImage.headersFor(_api(), url);
    return super.get(url, headers: {...?headers, ...?live});
  }
}

/// The store for the API's private photos, separate from the default cache
/// (which public images keep using) so it can be emptied on its own.
final privatePhotoCacheManagerProvider = Provider<BaseCacheManager>(
  (ref) => CacheManager(
    Config(
      privatePhotoCacheKey,
      stalePeriod: const Duration(days: 7),
      maxNrOfCacheObjects: 200,
      fileService: LiveTokenFileService(() => ref.read(apiServiceProvider)),
    ),
  ),
);

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
  await manager.emptyCache();
}

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
    return CachedNetworkImage(
      imageUrl: url,
      fit: fit,
      httpHeaders: headers,
      cacheManager: private ? ref.watch(privatePhotoCacheProvider) : null,
      cacheKey: private ? '${uid ?? '-'}|$url' : null,
      placeholder: placeholder,
      errorWidget: errorWidget,
    );
  }
}
