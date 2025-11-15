import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

void main() {
  group('UserProfile Model', () {
    test('fromJson creates UserProfile correctly', () {
      // Create test JSON data matching Django backend response
      final json = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'John',
        'last_name': 'Doe',
        'display_name': 'John Doe',
        'bio': 'Plant enthusiast',
        'location': 'San Francisco, CA',
        'website': 'https://example.com',
        'gardening_experience': 'intermediate',
        'avatar': 'https://example.com/avatar.jpg',
        'avatar_thumbnail': 'https://example.com/avatar_thumb.jpg',
        'profile_visibility': 'public',
        'show_email': true,
        'show_location': true,
        'email_notifications': true,
        'plant_id_notifications': true,
        'forum_notifications': false,
        'follower_count': 10,
        'following_count': 15,
        'plants_identified': 25,
        'identifications_helped': 5,
        'forum_posts_count': 8,
        'plant_collections_count': 3,
        'date_joined': '2025-01-15T10:00:00Z',
        'last_login': '2025-11-15T12:30:00Z',
      };

      // Convert from JSON
      final profile = UserProfile.fromJson(json);

      // Verify all fields
      expect(profile.id, equals(1));
      expect(profile.username, equals('testuser'));
      expect(profile.email, equals('test@example.com'));
      expect(profile.firstName, equals('John'));
      expect(profile.lastName, equals('Doe'));
      expect(profile.displayName, equals('John Doe'));
      expect(profile.bio, equals('Plant enthusiast'));
      expect(profile.location, equals('San Francisco, CA'));
      expect(profile.website, equals('https://example.com'));
      expect(profile.gardeningExperience, equals('intermediate'));
      expect(profile.avatar, equals('https://example.com/avatar.jpg'));
      expect(
        profile.avatarThumbnail,
        equals('https://example.com/avatar_thumb.jpg'),
      );
      expect(profile.profileVisibility, equals('public'));
      expect(profile.showEmail, isTrue);
      expect(profile.showLocation, isTrue);
      expect(profile.emailNotifications, isTrue);
      expect(profile.plantIdNotifications, isTrue);
      expect(profile.forumNotifications, isFalse);
      expect(profile.followerCount, equals(10));
      expect(profile.followingCount, equals(15));
      expect(profile.plantsIdentified, equals(25));
      expect(profile.identificationsHelped, equals(5));
      expect(profile.forumPostsCount, equals(8));
      expect(profile.plantCollectionsCount, equals(3));
      expect(profile.dateJoined, isA<DateTime>());
      expect(profile.lastLogin, isA<DateTime>());
    });

    test('toJson converts UserProfile to JSON correctly', () {
      final profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        firstName: 'John',
        lastName: 'Doe',
        bio: 'Plant lover',
        location: 'NYC',
        dateJoined: DateTime.parse('2025-01-01T00:00:00Z'),
      );

      final json = profile.toJson();

      // Verify JSON contains editable fields in snake_case
      expect(json['first_name'], equals('John'));
      expect(json['last_name'], equals('Doe'));
      expect(json['bio'], equals('Plant lover'));
      expect(json['location'], equals('NYC'));

      // Verify readonly fields are NOT in JSON
      expect(json.containsKey('id'), isFalse);
      expect(json.containsKey('username'), isFalse);
      expect(json.containsKey('email'), isFalse);
      expect(json.containsKey('follower_count'), isFalse);
    });

    test('copyWith creates new instance with updated fields', () {
      final original = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        firstName: 'John',
        bio: 'Original bio',
        dateJoined: DateTime.parse('2025-01-01T00:00:00Z'),
      );

      final updated = original.copyWith(
        bio: 'Updated bio',
        location: 'New York',
      );

      // Verify updated fields changed
      expect(updated.bio, equals('Updated bio'));
      expect(updated.location, equals('New York'));

      // Verify unchanged fields remain same
      expect(updated.id, equals(original.id));
      expect(updated.username, equals(original.username));
      expect(updated.firstName, equals(original.firstName));
    });

    test('fullName getter returns correct display name', () {
      // Test with displayName
      var profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        displayName: 'Custom Name',
        dateJoined: DateTime.now(),
      );
      expect(profile.fullName, equals('Custom Name'));

      // Test with first/last name
      profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        firstName: 'John',
        lastName: 'Doe',
        dateJoined: DateTime.now(),
      );
      expect(profile.fullName, equals('John Doe'));

      // Test fallback to username
      profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        dateJoined: DateTime.now(),
      );
      expect(profile.fullName, equals('testuser'));
    });

    test('isProfileComplete returns correct status', () {
      // Complete profile
      var profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        bio: 'Test bio',
        location: 'NYC',
        dateJoined: DateTime.now(),
      );
      expect(profile.isProfileComplete, isTrue);

      // Incomplete profile (no bio)
      profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        location: 'NYC',
        dateJoined: DateTime.now(),
      );
      expect(profile.isProfileComplete, isFalse);

      // Incomplete profile (no location)
      profile = UserProfile(
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        bio: 'Test bio',
        dateJoined: DateTime.now(),
      );
      expect(profile.isProfileComplete, isFalse);
    });

    test('empty creates empty profile', () {
      final profile = UserProfile.empty();

      expect(profile.id, equals(0));
      expect(profile.username, isEmpty);
      expect(profile.email, isEmpty);
      expect(profile.dateJoined, isA<DateTime>());
    });

    test('handles null optional fields', () {
      final json = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'date_joined': '2025-01-15T10:00:00Z',
        // All optional fields are null
      };

      final profile = UserProfile.fromJson(json);

      expect(profile.firstName, isNull);
      expect(profile.lastName, isNull);
      expect(profile.bio, isNull);
      expect(profile.location, isNull);
      expect(profile.website, isNull);
      expect(profile.avatar, isNull);
      expect(profile.lastLogin, isNull);
    });
  });

  group('UserProfileException', () {
    test('has correct message', () {
      final exception = UserProfileException('Test error');
      expect(exception.message, equals('Test error'));
      expect(exception.toString(), equals('UserProfileException: Test error'));
    });
  });

  // Integration tests would go here
  // These would require mocking ApiService and testing the actual service methods
  // Example structure:
  //
  // group('UserProfileService', () {
  //   testWidgets('fetchProfile returns profile data', (tester) async {
  //     final container = ProviderContainer(
  //       overrides: [
  //         // Mock ApiService to return test data
  //       ],
  //     );
  //
  //     final service = container.read(userProfileServiceProvider.notifier);
  //     final profile = await service.fetchProfile();
  //
  //     expect(profile, isNotNull);
  //     expect(profile!.username, equals('testuser'));
  //   });
  // });
}
