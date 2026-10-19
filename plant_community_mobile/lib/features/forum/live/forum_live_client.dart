import 'dart:async';
import 'dart:math' as math;

import 'forum_live_channel.dart';
import 'forum_live_event.dart';

/// The server's accept-then-close codes (slice 2, `ws/forum/topics/<id>/`).
const liveCloseDisabled = 4503; // FORUM_LIVE_UPDATES_ENABLED is off
const liveCloseUnauthenticated = 4401; // no valid user
const liveCloseNotFound = 4404; // topic not visible, or removed
const liveCloseLimited = 4429; // socket cap

/// App-level heartbeat: a ping this often, and a drop when nothing at all
/// arrives within [livePongTimeout] of it.
const livePingInterval = Duration(seconds: 25);
const livePongTimeout = Duration(seconds: 10);

const _pingFrame = '{"type":"ping"}';

/// `1000 + random · min(29 000, 4000 · 2^attempt)` ms: the first retry is
/// spread over 1–5 s, so a deploy doesn't bring every phone back in the same
/// second, and the cap is 30 s.
Duration liveBackoff(int attempt, double random) {
  final spread = attempt >= 3 ? 29000 : math.min(29000, 4000 << attempt);
  return Duration(milliseconds: 1000 + (random * spread).round());
}

/// One topic's socket: connect, the close-code rules, backoff and heartbeat.
/// Framework-free; the `TopicLive` notifier owns one and makes every
/// decision about the events it delivers.
///
/// - 4503 and 4429 stop it for good (`stopped`); 4404 is `gone`.
/// - 4401 runs [refreshAuth] once and reconnects once with the token
///   [token] then returns; a second 4401 in a row stops it.
/// - Any other close, or a connect that throws, retries after [liveBackoff].
///
/// The token goes only into the `Authorization` header: never a log line, a
/// URL or an error message.
class ForumLiveClient {
  ForumLiveClient({
    required ForumLiveConnector connect,
    required Uri uri,
    required String? Function() token,
    required Future<void> Function() refreshAuth,
    required void Function(LiveEvent) onEvent,
    required void Function() onOpen,
    required void Function(LiveStatus) onStatus,
    double Function()? random,
  }) : _connector = connect,
       _uri = uri,
       _token = token,
       _refreshAuth = refreshAuth,
       _onEvent = onEvent,
       _onOpen = onOpen,
       _onStatus = onStatus,
       _random = random ?? math.Random().nextDouble;

  final ForumLiveConnector _connector;
  final Uri _uri;
  final String? Function() _token;
  final Future<void> Function() _refreshAuth;
  final void Function(LiveEvent) _onEvent;
  final void Function() _onOpen;
  final void Function(LiveStatus) _onStatus;
  final double Function() _random;

  ForumLiveChannel? _channel;
  StreamSubscription<Object?>? _sub;
  int _attempt = 0;

  /// A 4401 already ran the refresh, and no frame has arrived since.
  bool _retriedAuth = false;
  bool _started = false;
  bool _closed = false;
  Timer? _retryTimer;
  Timer? _pingTimer;
  Timer? _pongTimer;

  void start() {
    if (_started || _closed) return;
    _started = true;
    unawaited(_connect());
  }

  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    _retryTimer?.cancel();
    _stopHeartbeat();
    final channel = _channel;
    _detach();
    _onStatus(LiveStatus.off);
    if (channel != null) await channel.close();
  }

  Future<void> _connect() async {
    _retryTimer = null;
    if (_closed) return;
    final token = _token();
    if (token == null) {
      _onStatus(LiveStatus.stopped);
      return;
    }
    _onStatus(LiveStatus.connecting);
    final ForumLiveChannel channel;
    try {
      channel = await _connector(_uri, {'Authorization': 'Bearer $token'});
    } catch (_) {
      // A refused handshake has no close code: back off and try again. The
      // error is not logged; it can carry the request.
      if (!_closed) _scheduleRetry();
      return;
    }
    if (_closed) {
      unawaited(channel.close());
      return;
    }
    _channel = channel;
    _attempt = 0;
    _sub = channel.frames.listen(
      _onFrame,
      onError: (Object _) {},
      onDone: () => _onDone(channel),
    );
    _onStatus(LiveStatus.live);
    _pingTimer = Timer.periodic(livePingInterval, (_) => _ping());
    _onOpen();
  }

  void _onFrame(Object? data) {
    _pongTimer?.cancel();
    _pongTimer = null;
    _retriedAuth = false;
    final frame = parseLiveFrame(data);
    if (frame is LiveEvent) _onEvent(frame);
  }

  void _ping() {
    _channel?.send(_pingFrame);
    _pongTimer ??= Timer(livePongTimeout, _drop);
  }

  /// No frame since the ping: the connection is dead without a close. Drop
  /// it and reconnect.
  void _drop() {
    _pongTimer = null;
    final channel = _channel;
    if (channel == null || _closed) return;
    _detach();
    unawaited(channel.close());
    _scheduleRetry();
  }

  Future<void> _onDone(ForumLiveChannel channel) async {
    if (!identical(channel, _channel) || _closed) return;
    _detach();
    switch (channel.closeCode) {
      case liveCloseDisabled || liveCloseLimited:
        _onStatus(LiveStatus.stopped);
      case liveCloseNotFound:
        _onStatus(LiveStatus.gone);
      case liveCloseUnauthenticated when !_retriedAuth:
        _retriedAuth = true;
        _onStatus(LiveStatus.connecting);
        await _refreshAuth();
        await _connect();
      case liveCloseUnauthenticated:
        _onStatus(LiveStatus.stopped);
      default:
        _scheduleRetry();
    }
  }

  /// The subscription's cancel is never awaited: nothing depends on it, and
  /// awaiting it stalled the caller under `testWidgets`' fake async.
  void _detach() {
    _stopHeartbeat();
    unawaited(_sub?.cancel());
    _sub = null;
    _channel = null;
  }

  void _stopHeartbeat() {
    _pingTimer?.cancel();
    _pingTimer = null;
    _pongTimer?.cancel();
    _pongTimer = null;
  }

  void _scheduleRetry() {
    _onStatus(LiveStatus.connecting);
    final delay = liveBackoff(_attempt, _random());
    _attempt++;
    _retryTimer = Timer(delay, () => unawaited(_connect()));
  }
}
