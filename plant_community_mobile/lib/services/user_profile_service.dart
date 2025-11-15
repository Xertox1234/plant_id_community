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
  @override
  Future<UserProfile?> build() async {
    // Auto-fetch profile on initialization
    return await fetchProfile();
  }

  /// Fetch current user's profile from backend
  ///
  /// Returns null if user is not authenticated or fetch fails
  ///
  /// Throws [UserProfileException] if API call fails
  Future<UserProfile?> fetchProfile() async {
    try {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Fetching current user profile');
      }

      final apiService = ref.read(apiServiceProvider);

      // Backend response: GET /api/v1/auth/user/
      // Returns UserProfileSerializer data directly (no wrapper):
      // {
      //   "id": 1,
      //   "username": "john_doe",
      //   "email": "john@example.com",
      //   "first_name": "John",
      //   ... (all profile fields)
      // }
      final response = await apiService.get('/auth/user/');

      if (kDebugMode) {
        debugPrint('[USER_PROFILE] Profile fetched successfully');
      }

      final profile = UserProfile.fromJson(response.data as Map<String, dynamic>);

      // Update state
      state = AsyncValue.data(profile);

      return profile;
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Failed to fetch profile: ${e.message}');
      }

      // Set error state
      state = AsyncValue.error(
        UserProfileException('Failed to load profile: ${e.message}'),
        StackTrace.current,
      );

      return null;
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected error: $e');
      }

      state = AsyncValue.error(
        UserProfileException('Failed to load profile: $e'),
        StackTrace.current,
      );

      return null;
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

      // Update state
      state = AsyncValue.data(updatedProfile);

      return updatedProfile;
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Failed to update profile: ${e.message}');
      }

      throw UserProfileException('Failed to update profile: ${e.message}');
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[USER_PROFILE ERROR] Unexpected error: $e');
      }

      throw UserProfileException('Failed to update profile: $e');
    }
  }

  // TODO: Add uploadAvatar() method when FirebaseStorageService is implemented
  // TODO: Add deleteAvatar() method when FirebaseStorageService is implemented

  /// Refresh profile data from backend
  ///
  /// Alias for fetchProfile() for clarity
  Future<UserProfile?> refresh() => fetchProfile();

  /// Clear profile state (on logout)
  void clear() {
    state = const AsyncValue.data(null);
  }
}

/// Custom exception for user profile errors
class UserProfileException implements Exception {
  final String message;

  UserProfileException(this.message);

  @override
  String toString() => 'UserProfileException: $message';
}
