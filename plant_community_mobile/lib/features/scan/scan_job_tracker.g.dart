// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'scan_job_tracker.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval], and saves a finished plant to My Collection once.
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET or save that lands after one
/// of them is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten, and
/// a result is only ever saved to its owner's collection.

@ProviderFor(ScanJobTracker)
final scanJobTrackerProvider = ScanJobTrackerProvider._();

/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval], and saves a finished plant to My Collection once.
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET or save that lands after one
/// of them is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten, and
/// a result is only ever saved to its owner's collection.
final class ScanJobTrackerProvider
    extends $NotifierProvider<ScanJobTracker, ScanTrackerState> {
  /// The one background scan job of this device: uploads it, polls it every
  /// [scanJobPollInterval], and saves a finished plant to My Collection once.
  ///
  /// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
  /// a change of signed-in user bump it, so a GET or save that lands after one
  /// of them is dropped.
  ///
  /// A job belongs to the user signed in when it was tracked ([_ownerUid]).
  /// When that user signs out or another signs in, the job is forgotten, and
  /// a result is only ever saved to its owner's collection.
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

String _$scanJobTrackerHash() => r'4d48d354acd84b2dd17b05ae0d281b7a5d01a90b';

/// The one background scan job of this device: uploads it, polls it every
/// [scanJobPollInterval], and saves a finished plant to My Collection once.
///
/// Every async continuation checks [_gen]: [submit], [cancel], [dismiss] and
/// a change of signed-in user bump it, so a GET or save that lands after one
/// of them is dropped.
///
/// A job belongs to the user signed in when it was tracked ([_ownerUid]).
/// When that user signs out or another signs in, the job is forgotten, and
/// a result is only ever saved to its owner's collection.

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
