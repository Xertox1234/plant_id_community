// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'topic_missing_out.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The signed-out "missing out" check (spec "Signed-out readers", D17).
/// Signed-out readers never get a socket; instead a peek read every
/// [missingOutPollInterval] while the app is shown. The first read sets the
/// baseline reply count. When a later read is higher, and the toast hasn't
/// shown this launch or in the last 24 h, the state (a sequence number) goes
/// up by one and the check stops for this screen.
///
/// When the toast can't show anyway, the check never starts, so it costs
/// no request.

@ProviderFor(TopicMissingOut)
final topicMissingOutProvider = TopicMissingOutFamily._();

/// The signed-out "missing out" check (spec "Signed-out readers", D17).
/// Signed-out readers never get a socket; instead a peek read every
/// [missingOutPollInterval] while the app is shown. The first read sets the
/// baseline reply count. When a later read is higher, and the toast hasn't
/// shown this launch or in the last 24 h, the state (a sequence number) goes
/// up by one and the check stops for this screen.
///
/// When the toast can't show anyway, the check never starts, so it costs
/// no request.
final class TopicMissingOutProvider
    extends $NotifierProvider<TopicMissingOut, int> {
  /// The signed-out "missing out" check (spec "Signed-out readers", D17).
  /// Signed-out readers never get a socket; instead a peek read every
  /// [missingOutPollInterval] while the app is shown. The first read sets the
  /// baseline reply count. When a later read is higher, and the toast hasn't
  /// shown this launch or in the last 24 h, the state (a sequence number) goes
  /// up by one and the check stops for this screen.
  ///
  /// When the toast can't show anyway, the check never starts, so it costs
  /// no request.
  TopicMissingOutProvider._({
    required TopicMissingOutFamily super.from,
    required int super.argument,
  }) : super(
         retry: null,
         name: r'topicMissingOutProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$topicMissingOutHash();

  @override
  String toString() {
    return r'topicMissingOutProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  TopicMissingOut create() => TopicMissingOut();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(int value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<int>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is TopicMissingOutProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$topicMissingOutHash() => r'd8af5dbd9b6bbbfbb7916391348e98fb46d0b3ae';

/// The signed-out "missing out" check (spec "Signed-out readers", D17).
/// Signed-out readers never get a socket; instead a peek read every
/// [missingOutPollInterval] while the app is shown. The first read sets the
/// baseline reply count. When a later read is higher, and the toast hasn't
/// shown this launch or in the last 24 h, the state (a sequence number) goes
/// up by one and the check stops for this screen.
///
/// When the toast can't show anyway, the check never starts, so it costs
/// no request.

final class TopicMissingOutFamily extends $Family
    with $ClassFamilyOverride<TopicMissingOut, int, int, int, int> {
  TopicMissingOutFamily._()
    : super(
        retry: null,
        name: r'topicMissingOutProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// The signed-out "missing out" check (spec "Signed-out readers", D17).
  /// Signed-out readers never get a socket; instead a peek read every
  /// [missingOutPollInterval] while the app is shown. The first read sets the
  /// baseline reply count. When a later read is higher, and the toast hasn't
  /// shown this launch or in the last 24 h, the state (a sequence number) goes
  /// up by one and the check stops for this screen.
  ///
  /// When the toast can't show anyway, the check never starts, so it costs
  /// no request.

  TopicMissingOutProvider call(int topicId) =>
      TopicMissingOutProvider._(argument: topicId, from: this);

  @override
  String toString() => r'topicMissingOutProvider';
}

/// The signed-out "missing out" check (spec "Signed-out readers", D17).
/// Signed-out readers never get a socket; instead a peek read every
/// [missingOutPollInterval] while the app is shown. The first read sets the
/// baseline reply count. When a later read is higher, and the toast hasn't
/// shown this launch or in the last 24 h, the state (a sequence number) goes
/// up by one and the check stops for this screen.
///
/// When the toast can't show anyway, the check never starts, so it costs
/// no request.

abstract class _$TopicMissingOut extends $Notifier<int> {
  late final _$args = ref.$arg as int;
  int get topicId => _$args;

  int build(int topicId);
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<int, int>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<int, int>,
              int,
              Object?,
              Object?
            >;
    element.handleCreate(ref, () => build(_$args));
  }
}
