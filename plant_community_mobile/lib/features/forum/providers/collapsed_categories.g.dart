// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'collapsed_categories.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Which forum-index categories the viewer has collapsed (spec §7.5),
/// matching the web's `useCollapsedCategories`.
///
/// [build] starts empty and applies the viewer's device copy once it is
/// read; signed in, it also fetches the member's list from their forum
/// profile, which then replaces the state and the device copy. A failed
/// fetch keeps the device copy silently. Nothing here delays the categories
/// feed. Rebuilt for every viewer change: work begun for one viewer never
/// touches the state, the device copy or the network once it is another's.
///
/// A save PUTs the whole list, so it is only ever built from the member's
/// server list with their pending taps re-applied, never from the device
/// copy, and only one is in flight at a time. [refresh] re-reads that list
/// when the forum tab refreshes its categories, so a list changed on the web
/// meanwhile is not overwritten by the next save.

@ProviderFor(CollapsedCategories)
final collapsedCategoriesProvider = CollapsedCategoriesProvider._();

/// Which forum-index categories the viewer has collapsed (spec §7.5),
/// matching the web's `useCollapsedCategories`.
///
/// [build] starts empty and applies the viewer's device copy once it is
/// read; signed in, it also fetches the member's list from their forum
/// profile, which then replaces the state and the device copy. A failed
/// fetch keeps the device copy silently. Nothing here delays the categories
/// feed. Rebuilt for every viewer change: work begun for one viewer never
/// touches the state, the device copy or the network once it is another's.
///
/// A save PUTs the whole list, so it is only ever built from the member's
/// server list with their pending taps re-applied, never from the device
/// copy, and only one is in flight at a time. [refresh] re-reads that list
/// when the forum tab refreshes its categories, so a list changed on the web
/// meanwhile is not overwritten by the next save.
final class CollapsedCategoriesProvider
    extends $NotifierProvider<CollapsedCategories, Set<int>> {
  /// Which forum-index categories the viewer has collapsed (spec §7.5),
  /// matching the web's `useCollapsedCategories`.
  ///
  /// [build] starts empty and applies the viewer's device copy once it is
  /// read; signed in, it also fetches the member's list from their forum
  /// profile, which then replaces the state and the device copy. A failed
  /// fetch keeps the device copy silently. Nothing here delays the categories
  /// feed. Rebuilt for every viewer change: work begun for one viewer never
  /// touches the state, the device copy or the network once it is another's.
  ///
  /// A save PUTs the whole list, so it is only ever built from the member's
  /// server list with their pending taps re-applied, never from the device
  /// copy, and only one is in flight at a time. [refresh] re-reads that list
  /// when the forum tab refreshes its categories, so a list changed on the web
  /// meanwhile is not overwritten by the next save.
  CollapsedCategoriesProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'collapsedCategoriesProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$collapsedCategoriesHash();

  @$internal
  @override
  CollapsedCategories create() => CollapsedCategories();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(Set<int> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<Set<int>>(value),
    );
  }
}

String _$collapsedCategoriesHash() =>
    r'88780a1ee87db047b7dd40c078349eeaf9687956';

/// Which forum-index categories the viewer has collapsed (spec §7.5),
/// matching the web's `useCollapsedCategories`.
///
/// [build] starts empty and applies the viewer's device copy once it is
/// read; signed in, it also fetches the member's list from their forum
/// profile, which then replaces the state and the device copy. A failed
/// fetch keeps the device copy silently. Nothing here delays the categories
/// feed. Rebuilt for every viewer change: work begun for one viewer never
/// touches the state, the device copy or the network once it is another's.
///
/// A save PUTs the whole list, so it is only ever built from the member's
/// server list with their pending taps re-applied, never from the device
/// copy, and only one is in flight at a time. [refresh] re-reads that list
/// when the forum tab refreshes its categories, so a list changed on the web
/// meanwhile is not overwritten by the next save.

abstract class _$CollapsedCategories extends $Notifier<Set<int>> {
  Set<int> build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref = this.ref as $Ref<Set<int>, Set<int>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<Set<int>, Set<int>>,
              Set<int>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}
