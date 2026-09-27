// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'onboarding_checklist_service.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The signed-in user's onboarding checklist, or null when signed out.
/// A failed fetch is an [AsyncError]; the home card then shows nothing.

@ProviderFor(OnboardingChecklistService)
final onboardingChecklistServiceProvider =
    OnboardingChecklistServiceProvider._();

/// The signed-in user's onboarding checklist, or null when signed out.
/// A failed fetch is an [AsyncError]; the home card then shows nothing.
final class OnboardingChecklistServiceProvider
    extends
        $AsyncNotifierProvider<
          OnboardingChecklistService,
          OnboardingChecklist?
        > {
  /// The signed-in user's onboarding checklist, or null when signed out.
  /// A failed fetch is an [AsyncError]; the home card then shows nothing.
  OnboardingChecklistServiceProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'onboardingChecklistServiceProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$onboardingChecklistServiceHash();

  @$internal
  @override
  OnboardingChecklistService create() => OnboardingChecklistService();
}

String _$onboardingChecklistServiceHash() =>
    r'64dd33e7dafb87c486b9f24e4b35f999ca75ade3';

/// The signed-in user's onboarding checklist, or null when signed out.
/// A failed fetch is an [AsyncError]; the home card then shows nothing.

abstract class _$OnboardingChecklistService
    extends $AsyncNotifier<OnboardingChecklist?> {
  FutureOr<OnboardingChecklist?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref
            as $Ref<AsyncValue<OnboardingChecklist?>, OnboardingChecklist?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<
                AsyncValue<OnboardingChecklist?>,
                OnboardingChecklist?
              >,
              AsyncValue<OnboardingChecklist?>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}
