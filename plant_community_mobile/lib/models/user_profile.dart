/// User profile model matching Django backend UserProfileSerializer
///
/// This model represents the complete user profile data from the backend.
/// Fields are based on `apps/users/serializers.py::UserProfileSerializer`
class UserProfile {
  /// Unique user ID
  final int id;

  /// Unique username (read-only on backend)
  final String username;

  /// User's email address
  final String email;

  /// First name (optional)
  final String? firstName;

  /// Last name (optional)
  final String? lastName;

  /// Display name (read-only, computed from first_name + last_name)
  final String? displayName;

  /// User biography/about section
  final String? bio;

  /// User's location (city, country)
  final String? location;

  /// User's website URL
  final String? website;

  /// Gardening experience level (beginner, intermediate, expert)
  final String? gardeningExperience;

  /// Profile avatar URL (full size)
  final String? avatar;

  /// Profile avatar thumbnail URL (for lists/cards)
  final String? avatarThumbnail;

  /// Profile visibility setting (public, private, friends_only)
  final String profileVisibility;

  /// Show email on public profile
  final bool showEmail;

  /// Show location on public profile
  final bool showLocation;

  /// Enable email notifications
  final bool emailNotifications;

  /// Enable plant identification notifications
  final bool plantIdNotifications;

  /// Enable forum notifications
  final bool forumNotifications;

  /// Number of followers (read-only)
  final int followerCount;

  /// Number of users following (read-only)
  final int followingCount;

  /// Number of plants identified (read-only)
  final int plantsIdentified;

  /// Number of identifications helped with (read-only)
  final int identificationsHelped;

  /// Number of forum posts (read-only)
  final int forumPostsCount;

  /// Number of plant collections (read-only)
  final int plantCollectionsCount;

  /// Account creation date
  final DateTime dateJoined;

  /// Last login timestamp
  final DateTime? lastLogin;

  const UserProfile({
    required this.id,
    required this.username,
    required this.email,
    this.firstName,
    this.lastName,
    this.displayName,
    this.bio,
    this.location,
    this.website,
    this.gardeningExperience,
    this.avatar,
    this.avatarThumbnail,
    this.profileVisibility = 'public',
    this.showEmail = false,
    this.showLocation = false,
    this.emailNotifications = true,
    this.plantIdNotifications = true,
    this.forumNotifications = true,
    this.followerCount = 0,
    this.followingCount = 0,
    this.plantsIdentified = 0,
    this.identificationsHelped = 0,
    this.forumPostsCount = 0,
    this.plantCollectionsCount = 0,
    required this.dateJoined,
    this.lastLogin,
  });

  /// Copy with new values
  UserProfile copyWith({
    int? id,
    String? username,
    String? email,
    String? firstName,
    String? lastName,
    String? displayName,
    String? bio,
    String? location,
    String? website,
    String? gardeningExperience,
    String? avatar,
    String? avatarThumbnail,
    String? profileVisibility,
    bool? showEmail,
    bool? showLocation,
    bool? emailNotifications,
    bool? plantIdNotifications,
    bool? forumNotifications,
    int? followerCount,
    int? followingCount,
    int? plantsIdentified,
    int? identificationsHelped,
    int? forumPostsCount,
    int? plantCollectionsCount,
    DateTime? dateJoined,
    DateTime? lastLogin,
  }) {
    return UserProfile(
      id: id ?? this.id,
      username: username ?? this.username,
      email: email ?? this.email,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      displayName: displayName ?? this.displayName,
      bio: bio ?? this.bio,
      location: location ?? this.location,
      website: website ?? this.website,
      gardeningExperience: gardeningExperience ?? this.gardeningExperience,
      avatar: avatar ?? this.avatar,
      avatarThumbnail: avatarThumbnail ?? this.avatarThumbnail,
      profileVisibility: profileVisibility ?? this.profileVisibility,
      showEmail: showEmail ?? this.showEmail,
      showLocation: showLocation ?? this.showLocation,
      emailNotifications: emailNotifications ?? this.emailNotifications,
      plantIdNotifications: plantIdNotifications ?? this.plantIdNotifications,
      forumNotifications: forumNotifications ?? this.forumNotifications,
      followerCount: followerCount ?? this.followerCount,
      followingCount: followingCount ?? this.followingCount,
      plantsIdentified: plantsIdentified ?? this.plantsIdentified,
      identificationsHelped: identificationsHelped ?? this.identificationsHelped,
      forumPostsCount: forumPostsCount ?? this.forumPostsCount,
      plantCollectionsCount: plantCollectionsCount ?? this.plantCollectionsCount,
      dateJoined: dateJoined ?? this.dateJoined,
      lastLogin: lastLogin ?? this.lastLogin,
    );
  }

  /// Create UserProfile from JSON (backend response)
  ///
  /// Handles snake_case to camelCase conversion from Django backend
  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as int,
      username: json['username'] as String,
      email: json['email'] as String,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      displayName: json['display_name'] as String?,
      bio: json['bio'] as String?,
      location: json['location'] as String?,
      website: json['website'] as String?,
      gardeningExperience: json['gardening_experience'] as String?,
      avatar: json['avatar'] as String?,
      avatarThumbnail: json['avatar_thumbnail'] as String?,
      profileVisibility: json['profile_visibility'] as String? ?? 'public',
      showEmail: json['show_email'] as bool? ?? false,
      showLocation: json['show_location'] as bool? ?? false,
      emailNotifications: json['email_notifications'] as bool? ?? true,
      plantIdNotifications: json['plant_id_notifications'] as bool? ?? true,
      forumNotifications: json['forum_notifications'] as bool? ?? true,
      followerCount: json['follower_count'] as int? ?? 0,
      followingCount: json['following_count'] as int? ?? 0,
      plantsIdentified: json['plants_identified'] as int? ?? 0,
      identificationsHelped: json['identifications_helped'] as int? ?? 0,
      forumPostsCount: json['forum_posts_count'] as int? ?? 0,
      plantCollectionsCount: json['plant_collections_count'] as int? ?? 0,
      dateJoined: DateTime.parse(json['date_joined'] as String),
      lastLogin: json['last_login'] != null
          ? DateTime.parse(json['last_login'] as String)
          : null,
    );
  }

  /// Convert to JSON for API requests (snake_case)
  ///
  /// Only includes editable fields
  Map<String, dynamic> toJson() {
    return {
      'first_name': firstName,
      'last_name': lastName,
      'bio': bio,
      'location': location,
      'website': website,
      'gardening_experience': gardeningExperience,
      'avatar': avatar,
      'profile_visibility': profileVisibility,
      'show_email': showEmail,
      'show_location': showLocation,
      'email_notifications': emailNotifications,
      'plant_id_notifications': plantIdNotifications,
      'forum_notifications': forumNotifications,
    };
  }

  /// Empty profile for initial state
  static UserProfile empty() {
    return UserProfile(
      id: 0,
      username: '',
      email: '',
      dateJoined: DateTime.now(),
    );
  }

  /// Get user's full display name or fallback to username
  String get fullName {
    if (displayName != null && displayName!.isNotEmpty) {
      return displayName!;
    }
    if (firstName != null || lastName != null) {
      return '${firstName ?? ''} ${lastName ?? ''}'.trim();
    }
    return username;
  }

  /// Check if profile is complete (has bio and location)
  bool get isProfileComplete {
    return bio != null && bio!.isNotEmpty && location != null && location!.isNotEmpty;
  }
}
