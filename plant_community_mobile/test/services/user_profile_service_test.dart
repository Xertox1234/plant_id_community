import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/models/user_profile.dart';
import 'package:plant_community_mobile/services/api_service.dart';
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

  group('UserProfileService', () {
    late _FakeApiService fakeApi;

    setUp(() => fakeApi = _FakeApiService());

    ProviderContainer makeContainer() {
      final container = ProviderContainer(
        overrides: [apiServiceProvider.overrideWithValue(fakeApi)],
        // Disable Riverpod's automatic retry so a failed build settles
        // deterministically on AsyncError instead of cycling through
        // AsyncLoading(retrying).
        retry: (_, _) => null,
      );
      addTearDown(container.dispose);
      // userProfileServiceProvider is autoDispose; keep a listener so it is
      // not disposed mid-load while a test awaits its future.
      container.listen(userProfileServiceProvider, (_, _) {});
      return container;
    }

    test('build() loads and parses the profile on success', () async {
      fakeApi.getResult = _response(_profileJson(username: 'alice'));
      final container = makeContainer();

      final profile = await container.read(userProfileServiceProvider.future);

      expect(profile, isNotNull);
      expect(profile!.username, equals('alice'));
      expect(profile.firstName, equals('John'));
    });

    test('build() surfaces AsyncError when the fetch fails', () async {
      // Regression guard: fetchProfile must THROW so build() yields
      // AsyncValue.error — not swallow the failure into AsyncData(null).
      fakeApi.getResult = ApiException('server down', statusCode: 500);
      final container = makeContainer();

      // Let the async build settle, then inspect the resulting state.
      await pumpEventQueue();

      final state = container.read(userProfileServiceProvider);
      expect(state, isA<AsyncError<UserProfile?>>());
      expect((state as AsyncError).error, isA<UserProfileException>());
    });

    test(
      'updateProfile sends only non-null fields and returns the profile',
      () async {
        fakeApi.getResult = _response(_profileJson());
        final container = makeContainer();
        await container.read(userProfileServiceProvider.future);

        fakeApi.patchResult = _response({
          'message': 'ok',
          'user': _profileJson(username: 'updated'),
        });

        final notifier = container.read(userProfileServiceProvider.notifier);
        final updated = await notifier.updateProfile(bio: 'New bio');

        expect(updated, isNotNull);
        expect(updated!.username, equals('updated'));
        expect(fakeApi.lastPatchPath, equals('/auth/user/update/'));
        expect(fakeApi.lastPatchData, equals({'bio': 'New bio'}));
      },
    );

    test('updateProfile throws UserProfileException on API failure', () async {
      fakeApi.getResult = _response(_profileJson());
      final container = makeContainer();
      await container.read(userProfileServiceProvider.future);

      fakeApi.patchResult = ApiException('bad request', statusCode: 400);
      final notifier = container.read(userProfileServiceProvider.notifier);

      await expectLater(
        notifier.updateProfile(bio: 'x'),
        throwsA(isA<UserProfileException>()),
      );
    });

    test('clear() resets state to data(null)', () async {
      fakeApi.getResult = _response(_profileJson());
      final container = makeContainer();
      await container.read(userProfileServiceProvider.future);

      container.read(userProfileServiceProvider.notifier).clear();

      final state = container.read(userProfileServiceProvider);
      expect(state, isA<AsyncData<UserProfile?>>());
      expect(state.value, isNull);
    });
  });
}

/// Minimal [ApiService] stand-in for tests. Each method returns its configured
/// result, or throws it when the result is an [Exception]. No real network.
class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: null);

  Object? getResult;
  Object? patchResult;
  String? lastPatchPath;
  Map<String, dynamic>? lastPatchData;

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    final result = getResult;
    if (result is Exception) throw result;
    return result as Response;
  }

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    lastPatchPath = path;
    lastPatchData = data as Map<String, dynamic>?;
    final result = patchResult;
    if (result is Exception) throw result;
    return result as Response;
  }
}

Response<dynamic> _response(dynamic data) => Response<dynamic>(
  requestOptions: RequestOptions(path: '/'),
  data: data,
);

Map<String, dynamic> _profileJson({String username = 'testuser'}) => {
  'id': 1,
  'username': username,
  'email': 'test@example.com',
  'first_name': 'John',
  'date_joined': '2025-01-15T10:00:00Z',
  'email_notifications': true,
};
