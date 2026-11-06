// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'scan_job_tracker.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval]. It never writes a finished scan to My Collection:
/// the user keeps it explicitly (the server's keep/dismiss decision).
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET that lands after one of them
/// is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten.

@ProviderFor(ScanJobTracker)
final scanJobTrackerProvider = ScanJobTrackerProvider._();

/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval]. It never writes a finished scan to My Collection:
/// the user keeps it explicitly (the server's keep/dismiss decision).
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET that lands after one of them
/// is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten.
final class ScanJobTrackerProvider
    extends $NotifierProvider<ScanJobTracker, ScanTrackerState> {
  /// The one background scan job of this device: uploads it, polls it every
  /// [scanJobPollInterval]. It never writes a finished scan to My Collection:
  /// the user keeps it explicitly (the server's keep/dismiss decision).
  ///
  /// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
  /// a change of signed-in user bump it, so a GET that lands after one of them
  /// is dropped.
  ///
  /// A job belongs to the user signed in when it was tracked ([_ownerUid]).
  /// When that user signs out or another signs in, the job is forgotten.
  ScanJobTrackerProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'scanJobTrackerProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$scanJobTrackerHash();

  @$internal
  @override
  ScanJobTracker create() => ScanJobTracker();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ScanTrackerState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ScanTrackerState>(value),
    );
  }
}

String _$scanJobTrackerHash() => r'd4a3ef919e480319eca1017c4dc5da04ac35b1b0';

/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval]. It never writes a finished scan to My Collection:
/// the user keeps it explicitly (the server's keep/dismiss decision).
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET that lands after one of them
/// is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten.

abstract class _$ScanJobTracker extends $Notifier<ScanTrackerState> {
  ScanTrackerState build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<ScanTrackerState, ScanTrackerState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<ScanTrackerState, ScanTrackerState>,
              ScanTrackerState,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
