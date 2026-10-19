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

String _$topicLiveHash() => r'9d3e74338b984dc6a02a2a1ba790fa5748cea00a';

/// Live replies for one open topic. Owns the socket client and makes every
/// decision about an event: insert, pill, splice, remove, refetch the
/// topic, or "gone". The screen reports only whether the reader is at the
/// bottom, and its lifecycle (hidden or shown).
///
/// A socket opens only for a signed-in reader with "Live updates" on while
/// the app is shown. Every client callback is checked against the current
/// client, so a closed, replaced or stopped connection changes nothing.

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

abstract class _$TopicLive extends $Notifier<TopicLiveState> {
  late final _$args = ref.$arg as int;
  int get topicId => _$args;

  TopicLiveState build(int topicId);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<TopicLiveState, TopicLiveState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<TopicLiveState, TopicLiveState>,
              TopicLiveState,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}
