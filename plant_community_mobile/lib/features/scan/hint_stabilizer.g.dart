// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'hint_stabilizer.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Clock used by the scan screen's [HintStabilizer]. Overridable in widget
/// tests, where fake time does not move `DateTime.now()`.

@ProviderFor(hintClock)
final hintClockProvider = HintClockProvider._();

/// Clock used by the scan screen's [HintStabilizer]. Overridable in widget
/// tests, where fake time does not move `DateTime.now()`.

final class HintClockProvider
    extends
        $FunctionalProvider<
          DateTime Function(),
          DateTime Function(),
          DateTime Function()
        >
    with $Provider<DateTime Function()> {
  /// Clock used by the scan screen's [HintStabilizer]. Overridable in widget
  /// tests, where fake time does not move `DateTime.now()`.
  HintClockProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'hintClockProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$hintClockHash();

  @$internal
  @override
  $ProviderElement<DateTime Function()> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  DateTime Function() create(Ref ref) {
    return hintClock(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(DateTime Function() value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<DateTime Function()>(value),
    );
  }
}

String _$hintClockHash() => r'541dae4c46dd3e06dbb4adfd773131cf41e36afd';
