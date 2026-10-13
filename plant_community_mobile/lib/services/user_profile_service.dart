import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../models/user_profile.dart';
import 'api_service.dart';

part 'user_profile_service.g.dart';

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
@riverpod
class UserProfileService extends _$UserProfileService {
  /// Bumped by [clear]. A fetch or an update captures it before its request
  /// and drops its result when it has moved: Riverpod discards a pending
  /// `build()` only on a rebuild or a dispose, not on a manual state write,
  /// so a response accepted under the session [clear] ended would otherwise
  /// put the previous account's profile back (todo 558 finding 5).
  int _clears = 0;

  @override
  Future<UserProfile?> build() async {
    // Signed out (or not signed in yet): no profile, and no request. An
    // anonymous GET would 401 into Riverpod's retry loop, over the
    // AsyncData(null) a sign-out's clear() left (todo 558 finding 1). The
    // next completed sign-in invalidates this provider, so it fetches then.
    if (!ref.read(apiServiceProvider).hasAuthToken) {
      return null;
    }
    final clears = _clears;
    // Auto-fetch on init. A thrown UserProfileException propagates out of
    // build() and Riverpod surfaces it as AsyncValue.error.
    final profile = await fetchProfile();
    return clears == _clears ? profile : null;
  }

  /// Fetch the current user's profile from the backend.
  ///
  /// Throws [UserProfileException] if the API call fails. Callers that need an
  /// `AsyncValue.error` state (`build`, `refresh`) let it propagate — do NOT
  /// catch it here and assign `state` manually, or the value returned to
  /// `build()` overwrites the error state.
  Future<UserProfile> fetchProfile() async {
    try {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Fetching current user profile');
      }

      final apiService = ref.read(apiServiceProvider);

      // GET /api/v1/auth/user/ returns UserProfileSerializer data directly
      // (no wrapper object).
      final response = await apiService.get('/auth/user/');

      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Profile fetched successfully');
      }

      return UserProfile.fromJson(response.data as Map<String, dynamic>);
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint(
          '[USER_PROFILE ERROR] Failed to fetch profile: ${e.message}',
        );
      }
      throw UserProfileException(
        'Failed to load profile: ${e.message}',
        statusCode: e.statusCode,
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected error: $e');
      }
      throw UserProfileException('Failed to load profile: $e');
    }
  }

  /// Update user profile
  ///
  /// Only provide fields you want to update. Null values are ignored.
  ///
  /// Throws [UserProfileException] if update fails
  Future<UserProfile?> updateProfile({
    String? firstName,
    String? lastName,
    String? bio,
    String? location,
    String? website,
    String? gardeningExperience,
    String? avatar,
    String? profileVisibility,
    bool? showEmail,
    bool? showLocation,
    bool? emailNotifications,
    bool? plantIdNotifications,
    bool? forumNotifications,
  }) async {
    try {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Updating profile');
      }

      // Build update data (only include non-null values)
      final updateData = <String, dynamic>{};

      if (firstName != null) updateData['first_name'] = firstName;
      if (lastName != null) updateData['last_name'] = lastName;
      if (bio != null) updateData['bio'] = bio;
      if (location != null) updateData['location'] = location;
      if (website != null) updateData['website'] = website;
      if (gardeningExperience != null) {
        updateData['gardening_experience'] = gardeningExperience;
      }
      if (avatar != null) updateData['avatar'] = avatar;
      if (profileVisibility != null) {
        updateData['profile_visibility'] = profileVisibility;
      }
      if (showEmail != null) updateData['show_email'] = showEmail;
      if (showLocation != null) updateData['show_location'] = showLocation;
      if (emailNotifications != null) {
        updateData['email_notifications'] = emailNotifications;
      }
      if (plantIdNotifications != null) {
        updateData['plant_id_notifications'] = plantIdNotifications;
      }
      if (forumNotifications != null) {
        updateData['forum_notifications'] = forumNotifications;
      }

      final clears = _clears;

      // Backend response: PATCH /api/v1/auth/user/update/
      // Returns wrapped response with message and user data:
      // {
      //   "message": "Profile updated successfully",
      //   "user": {
      //     "id": 1,
      //     "username": "john_doe",
      //     "email": "john@example.com",
      //     ... (all profile fields)
      //   }
      // }
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.patch(
        '/auth/user/update/',
        data: updateData,
      );

      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Profile updated successfully');
      }

      // Parse updated profile from response (nested under 'user' key)
      final updatedProfile = UserProfile.fromJson(
        response.data['user'] as Map<String, dynamic>,
      );

      // Update state, unless a sign-out cleared it meanwhile.
      if (clears == _clears) state = AsyncValue.data(updatedProfile);

      return updatedProfile;
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint(
          '[USER_PROFILE ERROR] Failed to update profile: ${e.message}',
        );
      }

      throw UserProfileException(
        'Failed to update profile: ${e.message}',
        statusCode: e.statusCode,
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected error: $e');
      }

      throw UserProfileException('Failed to update profile: $e');
    }
  }

  /// Upload [filePath] as the user's avatar (todo 455).
  ///
  /// The backend `avatar` is an ImageField, not a URL: it takes the file
  /// itself as a multipart PATCH to the same endpoint as [updateProfile], and
  /// validates it server side (an image, at most 2 MB, 50 to 4096 px).
  ///
  /// Throws [UserProfileException] if the upload fails.
  Future<UserProfile> uploadAvatar(String filePath) async {
    final clears = _clears;
    try {
      final formData = FormData.fromMap({
        'avatar': await MultipartFile.fromFile(
          filePath,
          filename: filePath.split('/').last,
        ),
      });
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.patch(
        '/auth/user/update/',
        data: formData,
      );
      final updatedProfile = UserProfile.fromJson(
        response.data['user'] as Map<String, dynamic>,
      );
      if (clears == _clears) state = AsyncValue.data(updatedProfile);
      return updatedProfile;
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Avatar upload failed: ${e.message}');
      }
      throw UserProfileException(
        'Failed to upload photo: ${e.message}',
        statusCode: e.statusCode,
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected avatar error: $e');
      }
      throw UserProfileException('Failed to upload photo: $e');
    }
  }

  /// Remove the user's avatar (todo 565 finding 9). The backend deletes the
  /// photo and its thumbnail from storage.
  ///
  /// Throws [UserProfileException] if the request fails.
  Future<UserProfile> deleteAvatar() async {
    final clears = _clears;
    try {
      final response = await ref
          .read(apiServiceProvider)
          .delete('/auth/user/avatar/');
      final updatedProfile = UserProfile.fromJson(
        response.data['user'] as Map<String, dynamic>,
      );
      if (clears == _clears) state = AsyncValue.data(updatedProfile);
      return updatedProfile;
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Avatar removal failed: ${e.message}');
      }
      throw UserProfileException(
        'Failed to remove photo: ${e.message}',
        statusCode: e.statusCode,
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected avatar removal error: $e');
      }
      throw UserProfileException('Failed to remove photo: $e');
    }
  }

  /// Refresh profile data from the backend, updating [state] with the result.
  /// A failed fetch lands as `AsyncValue.error` (via [AsyncValue.guard]) so the
  /// UI can show its error/retry branch. A [clear] while it runs wins: the
  /// result is dropped.
  Future<void> refresh() async {
    final clears = _clears;
    state = const AsyncValue<UserProfile?>.loading();
    final result = await AsyncValue.guard(fetchProfile);
    if (clears == _clears) state = result;
  }

  /// Clear profile state (on logout). Also fences off a fetch or update
  /// already in flight, whose result is then dropped ([_clears]).
  void clear() {
    _clears++;
    state = const AsyncValue.data(null);
  }
}

/// Custom exception for user profile errors
class UserProfileException implements Exception {
  final String message;

  /// The HTTP status of the failed request, when there was one: a caller
  /// tells a 429 (the shared `profile_updates` throttle) from other failures
  /// by it (todo 651).
  final int? statusCode;

  UserProfileException(this.message, {this.statusCode});

  @override
  String toString() => 'UserProfileException: $message';
}
