// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'user_profile_service.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// User profile service for managing user profile data
///
/// This service provides:
/// - Fetch current user profile from Django backend
/// - Update user profile fields
///
/// Backend endpoints used:
/// - GET /api/v1/auth/user/ - Fetch current user profile
/// - PATCH /api/v1/auth/user/update/ - Update profile
///
/// Usage:
/// ```dart
/// final profileService = ref.read(userProfileServiceProvider.notifier);
///
/// // Fetch profile
/// await profileService.fetchProfile();
///
/// // Update profile
/// await profileService.updateProfile(
///   firstName: 'John',
///   bio: 'Plant enthusiast',
/// );
///
/// // Refresh profile data
/// await profileService.refresh();
/// ```

@ProviderFor(UserProfileService)
const userProfileServiceProvider = UserProfileServiceProvider._();

/// User profile service for managing user profile data
///
/// This service provides:
/// - Fetch current user profile from Django backend
/// - Update user profile fields
///
/// Backend endpoints used:
/// - GET /api/v1/auth/user/ - Fetch current user profile
/// - PATCH /api/v1/auth/user/update/ - Update profile
///
/// Usage:
/// ```dart
/// final profileService = ref.read(userProfileServiceProvider.notifier);
///
/// // Fetch profile
/// await profileService.fetchProfile();
///
/// // Update profile
/// await profileService.updateProfile(
///   firstName: 'John',
///   bio: 'Plant enthusiast',
/// );
///
/// // Refresh profile data
/// await profileService.refresh();
/// ```
final class UserProfileServiceProvider
    extends $AsyncNotifierProvider<UserProfileService, UserProfile?> {
  /// User profile service for managing user profile data
  ///
  /// This service provides:
  /// - Fetch current user profile from Django backend
  /// - Update user profile fields
  ///
  /// Backend endpoints used:
  /// - GET /api/v1/auth/user/ - Fetch current user profile
  /// - PATCH /api/v1/auth/user/update/ - Update profile
  ///
  /// Usage:
  /// ```dart
  /// final profileService = ref.read(userProfileServiceProvider.notifier);
  ///
  /// // Fetch profile
  /// await profileService.fetchProfile();
  ///
  /// // Update profile
  /// await profileService.updateProfile(
  ///   firstName: 'John',
  ///   bio: 'Plant enthusiast',
  /// );
  ///
  /// // Refresh profile data
  /// await profileService.refresh();
  /// ```
  const UserProfileServiceProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'userProfileServiceProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$userProfileServiceHash();

  @$internal
  @override
  UserProfileService create() => UserProfileService();
}

String _$userProfileServiceHash() =>
    r'9add43b3f9b8df3276dd79e105b78d5458c5fef7';

/// User profile service for managing user profile data
///
/// This service provides:
/// - Fetch current user profile from Django backend
/// - Update user profile fields
///
/// Backend endpoints used:
/// - GET /api/v1/auth/user/ - Fetch current user profile
/// - PATCH /api/v1/auth/user/update/ - Update profile
///
/// Usage:
/// ```dart
/// final profileService = ref.read(userProfileServiceProvider.notifier);
///
/// // Fetch profile
/// await profileService.fetchProfile();
///
/// // Update profile
/// await profileService.updateProfile(
///   firstName: 'John',
///   bio: 'Plant enthusiast',
/// );
///
/// // Refresh profile data
/// await profileService.refresh();
/// ```

abstract class _$UserProfileService extends $AsyncNotifier<UserProfile?> {
  FutureOr<UserProfile?> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final created = build();
    final ref = this.ref as $Ref<AsyncValue<UserProfile?>, UserProfile?>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<UserProfile?>, UserProfile?>,
              AsyncValue<UserProfile?>,
              Object?,
              Object?
            >;
    element.handleValue(ref, created);
  }
}
