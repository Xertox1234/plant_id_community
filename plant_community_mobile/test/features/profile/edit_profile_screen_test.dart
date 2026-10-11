import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/profile/edit_profile_screen.dart';
import 'package:plant_community_mobile/services/api_service.dart';

/// Todo 455: a mobile user can set a bio and an avatar.
///
/// The real `UserProfileService` runs against a fake `ApiService`, so these
/// tests check the requests the screen actually sends: a JSON bio, and the
/// avatar as a multipart PATCH to `/auth/user/update/`.

Map<String, dynamic> _user({String bio = '', String? avatar}) => {
  'id': 1,
  'username': 'ada',
  'email': 'ada@example.com',
  'bio': bio,
  'avatar': avatar,
  'date_joined': '2026-01-01T00:00:00Z',
};

class _FakeApi extends ApiService {
  _FakeApi({this.failPatch = false})
    : super(baseUrl: 'https://api.example.test/api/v1');

  final bool failPatch;
  Map<String, dynamic> user = _user();
  final patches = <({String path, Object? data})>[];

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async => Response(
    requestOptions: RequestOptions(path: path),
    statusCode: 200,
    data: user,
  );

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    patches.add((path: path, data: data));
    if (failPatch) throw ApiException('Ensure this field has no more…');
    if (data is FormData) {
      user = {...user, 'avatar': 'https://cdn.example.test/avatars/me.jpg'};
    } else if (data is Map && data.containsKey('bio')) {
      user = {...user, 'bio': data['bio']};
    }
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {'message': 'Profile updated successfully', 'user': user},
    );
  }
}

class _FakePicker implements ProfileAvatarPicker {
  _FakePicker(this.result);
  final String? result;
  var picks = 0;

  @override
  Future<String?> pick() async {
    picks++;
    return result;
  }
}

Future<GoRouter> _pump(
  WidgetTester tester,
  _FakeApi api, {
  ProfileAvatarPicker? picker,
}) async {
  final router = GoRouter(
    initialLocation: '/profile',
    routes: [
      GoRoute(
        path: '/profile',
        builder: (_, _) => const Scaffold(body: Text('profile screen')),
        routes: [
          GoRoute(
            path: 'edit',
            builder: (_, _) =>
                EditProfileScreen(avatarPicker: picker ?? _FakePicker(null)),
          ),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [apiServiceProvider.overrideWithValue(api)],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  router.push('/profile/edit');
  await tester.pumpAndSettle();
  return router;
}

void main() {
  testWidgets('shows the current bio', (tester) async {
    final api = _FakeApi()..user = _user(bio: 'Grows ferns.');
    await _pump(tester, api);

    expect(find.widgetWithText(TextField, 'Grows ferns.'), findsOneWidget);
    expect(find.text('Add photo'), findsOneWidget);
  });

  testWidgets('Save sends the bio and returns to the profile', (tester) async {
    final api = _FakeApi();
    await _pump(tester, api);

    await tester.enterText(find.byType(TextField), '  Monstera person  ');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(api.patches, hasLength(1));
    expect(api.patches.single.path, '/auth/user/update/');
    expect(api.patches.single.data, {'bio': 'Monstera person'});
    expect(find.text('profile screen'), findsOneWidget);
  });

  testWidgets('a refused save keeps the screen open and says why', (
    tester,
  ) async {
    final api = _FakeApi(failPatch: true);
    await _pump(tester, api);

    await tester.enterText(find.byType(TextField), 'x');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.byType(EditProfileScreen), findsOneWidget);
    expect(find.textContaining('Failed to update profile'), findsOneWidget);
  });

  testWidgets('picking a photo uploads it as a multipart avatar', (
    tester,
  ) async {
    final dir = Directory.systemTemp.createTempSync('avatar_test');
    addTearDown(() => dir.deleteSync(recursive: true));
    final file = File('${dir.path}/me.jpg')..writeAsBytesSync([1, 2, 3]);
    final api = _FakeApi();
    final picker = _FakePicker(file.path);
    await _pump(tester, api, picker: picker);

    await tester.tap(find.text('Add photo'));
    await tester.runAsync(() async {
      // MultipartFile.fromFile reads the real file system.
      for (var i = 0; i < 20 && api.patches.isEmpty; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 10));
      }
    });
    await tester.pumpAndSettle();

    expect(picker.picks, 1);
    expect(api.patches, hasLength(1));
    final sent = api.patches.single;
    expect(sent.path, '/auth/user/update/');
    expect(sent.data, isA<FormData>());
    final form = sent.data! as FormData;
    expect(form.files.single.key, 'avatar');
    expect(form.files.single.value.filename, 'me.jpg');
    expect(find.text('Photo updated'), findsOneWidget);
    expect(find.text('Change photo'), findsOneWidget);
  });

  testWidgets('a cancelled pick sends nothing', (tester) async {
    final api = _FakeApi();
    await _pump(tester, api, picker: _FakePicker(null));

    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();

    expect(api.patches, isEmpty);
  });

  testWidgets('an oversized pick is refused before any upload', (tester) async {
    final api = _FakeApi();
    await _pump(tester, api, picker: _OversizedPicker());

    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();

    expect(api.patches, isEmpty);
    expect(find.textContaining('over 2 MB'), findsOneWidget);
  });
}

class _OversizedPicker implements ProfileAvatarPicker {
  @override
  Future<String?> pick() async => throw ApiException(
    'That photo is over 2 MB. Pick a smaller one.',
    statusCode: 413,
  );
}
