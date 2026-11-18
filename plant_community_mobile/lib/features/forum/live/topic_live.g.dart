// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'topic_live.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.
///
/// Never for a topic in a forum the reader holds an unlock token for: the
/// server keeps live replies off for password forums and closes such a
/// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
/// instead. Staff read a password forum without a token, and their socket
/// works, so only a held token decides, not the forum having a password.

@ProviderFor(TopicLive)
final topicLiveProvider = TopicLiveFamily._();

/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.
///
/// Never for a topic in a forum the reader holds an unlock token for: the
/// server keeps live replies off for password forums and closes such a
/// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
/// instead. Staff read a password forum without a token, and their socket
/// works, so only a held token decides, not the forum having a password.
final class TopicLiveProvider
    extends $NotifierProvider<TopicLive, TopicLiveState> {
  /// Live replies for one open topic. Owns the socket client and makes every
  /// decision about an event: insert, pill, splice, remove, refetch the
  /// topic, or "gone". The screen reports only whether the reader is at the
  /// bottom, and its lifecycle (hidden or shown).
  ///
  /// A socket opens only for a signed-in reader with "Live updates" on while
  /// the app is shown. Every client callback is checked against the current
  /// client, so a closed, replaced or stopped connection changes nothing.
  ///
  /// Never for a topic in a forum the reader holds an unlock token for: the
  /// server keeps live replies off for password forums and closes such a
  /// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
  /// instead. Staff read a password forum without a token, and their socket
  /// works, so only a held token decides, not the forum having a password.
  TopicLiveProvider._({
    required TopicLiveFamily super.from,
    required int super.argument,
  }) : super(
         retry: null,
         name: r'topicLiveProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$topicLiveHash();

  @override
  String toString() {
    return r'topicLiveProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  TopicLive create() => TopicLive();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(TopicLiveState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<TopicLiveState>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is TopicLiveProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$topicLiveHash() => r'c2ff83214ae663b5b88f0f1184f429972953b342';

/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.
///
/// Never for a topic in a forum the reader holds an unlock token for: the
/// server keeps live replies off for password forums and closes such a
/// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
/// instead. Staff read a password forum without a token, and their socket
/// works, so only a held token decides, not the forum having a password.

final class TopicLiveFamily extends $Family
    with
        $ClassFamilyOverride<
          TopicLive,
          TopicLiveState,
          TopicLiveState,
          TopicLiveState,
          int
        > {
  TopicLiveFamily._()
    : super(
        retry: null,
        name: r'topicLiveProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Live replies for one open topic. Owns the socket client and makes every
  /// decision about an event: insert, pill, splice, remove, refetch the
  /// topic, or "gone". The screen reports only whether the reader is at the
  /// bottom, and its lifecycle (hidden or shown).
  ///
  /// A socket opens only for a signed-in reader with "Live updates" on while
  /// the app is shown. Every client callback is checked against the current
  /// client, so a closed, replaced or stopped connection changes nothing.
  ///
  /// Never for a topic in a forum the reader holds an unlock token for: the
  /// server keeps live replies off for password forums and closes such a
  /// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
  /// instead. Staff read a password forum without a token, and their socket
  /// works, so only a held token decides, not the forum having a password.

  TopicLiveProvider call(int topicId) =>
      TopicLiveProvider._(argument: topicId, from: this);

  @override
  String toString() => r'topicLiveProvider';
}

/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.
///
/// Never for a topic in a forum the reader holds an unlock token for: the
/// server keeps live replies off for password forums and closes such a
/// socket with 4404, which reads as "removed" (spec §7.4). It is live-off
/// instead. Staff read a password forum without a token, and their socket
/// works, so only a held token decides, not the forum having a password.

abstract class _$TopicLive extends $Notifier<TopicLiveState> {
  late final _$args = ref.$arg as int;
  int get topicId => _$args;

  TopicLiveState build(int topicId);
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<TopicLiveState, TopicLiveState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<TopicLiveState, TopicLiveState>,
              TopicLiveState,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, () => build(_$args));
  }
}
