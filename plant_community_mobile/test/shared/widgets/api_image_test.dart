import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/shared/widgets/api_image.dart';

import '../../support/private_photo_cache.dart';

const _origin = 'https://api.test';

Future<Map<String, String>?> _headersFor(
  WidgetTester tester,
  String url, {
  String? token = 'tok-123',
}) async {
  final api = ApiService(baseUrl: '$_origin/api/v1', authToken: token);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiServiceProvider.overrideWithValue(api),
        ...privatePhotoOverrides(),
      ],
      child: MaterialApp(home: ApiImage(url: url)),
    ),
  );
  return tester
      .widget<CachedNetworkImage>(find.byType(CachedNetworkImage))
      .httpHeaders;
}

void main() {
  testWidgets('ApiImage adds auth header only for API URLs', (tester) async {
    final api = await _headersFor(
      tester,
      '$_origin/api/v1/plant-identification/scans/j/photos/whole/',
    );
    expect(api?['Authorization'], 'Bearer tok-123');
    expect(api?['Accept'], 'image/*');

    final firebase = await _headersFor(
      tester,
      'https://firebasestorage.googleapis.com/v0/b/x/o/p.jpg',
    );
    expect(firebase, isNull);
  });

  testWidgets('ApiImage never sends the token to a look-alike host', (
    tester,
  ) async {
    for (final url in [
      'https://api.test.evil.com/a.jpg',
      'https://evil.com/?u=https://api.test/api/v1/a.jpg',
      'http://api.test/api/v1/a.jpg',
      'https://api.test:8443/a.jpg',
    ]) {
      expect(await _headersFor(tester, url), isNull, reason: url);
    }
  });

  testWidgets('ApiImage loads an API URL without a header when no token', (
    tester,
  ) async {
    final headers = await _headersFor(
      tester,
      '$_origin/api/v1/x/',
      token: null,
    );
    expect(headers, isNull);
  });

  testWidgets('API photos use the private store under a per-user key', (
    tester,
  ) async {
    final cache = FakePhotoCache();
    final api = ApiService(baseUrl: '$_origin/api/v1', authToken: 'tok');
    const photo = '$_origin/api/v1/plant-identification/scans/j/photos/leaf/';
    const public = 'https://firebasestorage.googleapis.com/v0/b/x/o/p.jpg';
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiServiceProvider.overrideWithValue(api),
          ...privatePhotoOverrides(cache: cache, uid: 'user-a'),
        ],
        child: const MaterialApp(
          home: Column(
            children: [
              SizedBox(height: 50, child: ApiImage(url: photo)),
              SizedBox(height: 50, child: ApiImage(url: public)),
            ],
          ),
        ),
      ),
    );
    final images = tester
        .widgetList<CachedNetworkImage>(find.byType(CachedNetworkImage))
        .toList();
    expect(images[0].cacheManager, same(cache));
    expect(images[0].cacheKey, 'user-a|$photo');
    // Public images keep the default cache and URL key.
    expect(images[1].cacheManager, isNull);
    expect(images[1].cacheKey, isNull);
  });

  testWidgets('signing out or switching account empties the private store', (
    tester,
  ) async {
    final cache = FakePhotoCache();
    final uid = NotifierProvider<_Uid, String?>(() => _Uid('user-a'));
    final container = ProviderContainer(
      overrides: [
        privatePhotoCacheManagerProvider.overrideWithValue(cache),
        currentUserIdProvider.overrideWith((ref) => ref.watch(uid)),
      ],
    );
    container.read(privatePhotoCacheProvider);

    container.read(uid.notifier).set(null); // sign out
    // Flush as Riverpod's scheduler would (see scan_job_tracker_test).
    container.read(currentUserIdProvider);
    await tester.pump();
    expect(cache.emptied, 1);

    // Signing in from signed-out is not a user leaving: no clear (it is
    // also the cold-start restore).
    container.read(uid.notifier).set('user-b');
    container.read(currentUserIdProvider);
    await tester.pump();
    expect(cache.emptied, 1);

    container.read(uid.notifier).set('user-c'); // direct account switch
    container.read(currentUserIdProvider);
    await tester.pump();
    expect(cache.emptied, 2);

    container.dispose(); // inside the body: its scheduler timer must not leak
    await tester.pump();
  });

  test('photo fetches send the token held now, not the one at build', () async {
    final api = ApiService(baseUrl: '$_origin/api/v1', authToken: 'old');
    String? sent;
    final service = LiveTokenFileService(
      () => api,
      httpClient: MockClient((request) async {
        sent = request.headers['Authorization'];
        return http.Response('', 200);
      }),
    );
    api.replaceAuthToken('refreshed'); // a token refresh mid-session

    await service.get(
      '$_origin/api/v1/x/photos/leaf/',
      headers: {'Authorization': 'Bearer old'},
    );

    expect(sent, 'Bearer refreshed');
  });
  test('after sign-out no token goes out, not even the one captured at '
      'build', () async {
    final api = ApiService(baseUrl: '$_origin/api/v1', authToken: null);
    Map<String, String>? sent;
    final service = LiveTokenFileService(
      () => api,
      httpClient: MockClient((request) async {
        sent = request.headers;
        return http.Response('', 401);
      }),
    );

    await service.get(
      '$_origin/api/v1/x/photos/leaf/',
      headers: {'Authorization': 'Bearer old', 'Accept': 'image/*'},
    );

    expect(sent!.containsKey('Authorization'), isFalse);
    expect(sent!['Accept'], 'image/*');
  });
}

/// The signed-in user, switchable mid-test.
class _Uid extends Notifier<String?> {
  _Uid(this._initial);
  final String? _initial;

  @override
  String? build() => _initial;

  void set(String? uid) => state = uid;
}
