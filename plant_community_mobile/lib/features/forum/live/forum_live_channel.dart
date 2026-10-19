import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// One open topic socket. The seam tests fake, the way `ForumApi` is faked.
abstract interface class ForumLiveChannel {
  /// Frames from the server: a `String` for a text frame. Done when the
  /// socket closes, after which [closeCode] says why.
  Stream<Object?> get frames;

  void send(String text);

  Future<void> close();

  int? get closeCode;
}

/// Opens a topic socket. Throws (for example a `WebSocketException`) when
/// the handshake is refused; there is no close code then.
typedef ForumLiveConnector =
    Future<ForumLiveChannel> Function(Uri uri, Map<String, String> headers);

final forumLiveConnectorProvider = Provider<ForumLiveConnector>(
  (ref) => ioForumLiveConnector,
);

/// A handshake that hangs this long counts as a failed connect (and backs
/// off) instead of waiting forever.
const _connectTimeout = Duration(seconds: 15);

/// The `dart:io` connector. `dart:io` sends no `Origin`, which the server
/// allows for a bearer-header client.
Future<ForumLiveChannel> ioForumLiveConnector(
  Uri uri,
  Map<String, String> headers,
) async {
  final client = HttpClient()..connectionTimeout = _connectTimeout;
  try {
    final socket = await WebSocket.connect(
      uri.toString(),
      headers: headers,
      customClient: client,
    );
    return _IoForumLiveChannel(socket);
  } finally {
    // The upgraded socket is detached from the client, so closing it here
    // frees the client without touching the open socket.
    client.close();
  }
}

class _IoForumLiveChannel implements ForumLiveChannel {
  _IoForumLiveChannel(this._socket);

  final WebSocket _socket;

  @override
  Stream<Object?> get frames => _socket;

  @override
  void send(String text) => _socket.add(text);

  @override
  Future<void> close() => _socket.close();

  @override
  int? get closeCode => _socket.closeCode;
}

/// The topic socket's URL: [apiBaseUrl]'s host with `ws`/`wss`, and the path
/// `/ws/forum/topics/<id>/` (no `/api/v1`).
Uri topicLiveUri(String apiBaseUrl, int topicId) {
  final base = Uri.parse(apiBaseUrl);
  return Uri(
    scheme: base.scheme == 'https' ? 'wss' : 'ws',
    host: base.host,
    port: base.hasPort ? base.port : null,
    path: '/ws/forum/topics/$topicId/',
  );
}
