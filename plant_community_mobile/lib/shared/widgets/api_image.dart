import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/api_service.dart';

/// A network image that signs in for the app's own private photo URLs.
///
/// Scan photos are served by the API behind `Authorization: Bearer`, so a
/// plain [CachedNetworkImage] would 401. The header goes only to URLs on the
/// API's own origin (scheme, host and port compared as parsed parts, never a
/// substring), so a look-alike host or a third-party URL (the older Firebase
/// Storage entries) never sees the token and loads as it always did.
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
    return CachedNetworkImage(
      imageUrl: url,
      fit: fit,
      httpHeaders: headersFor(ref.watch(apiServiceProvider), url),
      placeholder: placeholder,
      errorWidget: errorWidget,
    );
  }
}
