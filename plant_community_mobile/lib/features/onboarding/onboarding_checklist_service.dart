import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../services/api_service.dart';
import '../../services/auth_service.dart';

part 'onboarding_checklist_service.g.dart';

/// Backend: GET/PATCH /api/v1/auth/me/onboarding/progress/ (todo 412).
const onboardingProgressPath = '/auth/me/onboarding/progress/';

/// One checklist step. The server DERIVES [done] from what the user did,
/// so the app never ticks a step itself.
@immutable
class OnboardingStep {
  const OnboardingStep({required this.key, required this.done});

  factory OnboardingStep.fromJson(Map<String, dynamic> json) =>
      OnboardingStep(key: json['key'] as String, done: json['done'] == true);

  final String key;
  final bool done;
}

@immutable
class OnboardingChecklist {
  const OnboardingChecklist({
    required this.steps,
    required this.complete,
    required this.dismissed,
  });

  factory OnboardingChecklist.fromJson(Map<String, dynamic> json) =>
      OnboardingChecklist(
        steps: [
          for (final step in (json['steps'] as List? ?? const []))
            OnboardingStep.fromJson(step as Map<String, dynamic>),
        ],
        complete: json['complete'] == true,
        dismissed: json['dismissed'] == true,
      );

  final List<OnboardingStep> steps;
  final bool complete;
  final bool dismissed;

  /// The home card shows until every step is done or the user dismisses it.
  bool get visible => !complete && !dismissed && steps.isNotEmpty;

  OnboardingChecklist copyWith({bool? dismissed}) => OnboardingChecklist(
    steps: steps,
    complete: complete,
    dismissed: dismissed ?? this.dismissed,
  );
}

/// The signed-in user's onboarding checklist, or null when signed out.
/// A failed fetch is an [AsyncError]; the home card then shows nothing.
@riverpod
class OnboardingChecklistService extends _$OnboardingChecklistService {
  @override
  Future<OnboardingChecklist?> build() async {
    final signedIn = ref.watch(
      authServiceProvider.select((state) => state.isAuthenticated),
    );
    if (!signedIn) return null;
    final response = await ref
        .read(apiServiceProvider)
        .get(onboardingProgressPath);
    return OnboardingChecklist.fromJson(
      (response.data as Map<String, dynamic>)['checklist']
          as Map<String, dynamic>,
    );
  }

  /// Hide the card for good. Optimistic: the card goes at once and comes
  /// back if the server refuses.
  Future<void> dismiss() async {
    final previous = state.value;
    if (previous == null) return;
    state = AsyncData(previous.copyWith(dismissed: true));
    try {
      final response = await ref
          .read(apiServiceProvider)
          .patch(onboardingProgressPath, data: {'completed_checklist': true});
      state = AsyncData(
        OnboardingChecklist.fromJson(
          (response.data as Map<String, dynamic>)['checklist']
              as Map<String, dynamic>,
        ),
      );
    } catch (e) {
      // Any failure (an ApiException, or an unexpected response shape)
      // brings the card back rather than hiding it for good.
      if (kDebugMode) {
        debugPrint('[ONBOARDING] Dismiss failed: $e');
      }
      state = AsyncData(previous);
    }
  }
}
