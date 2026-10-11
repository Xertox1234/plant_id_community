import 'dart:async';
import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/profile/edit_profile_screen.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/user_profile_service.dart';

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
  // Signed in: the profile is fetched only with a bearer (todo 558).
  _FakeApi({this.failPatch = false})
    : super(baseUrl: 'https://api.example.test/api/v1', authToken: 'jwt');

  final bool failPatch;
  Map<String, dynamic> user = _user();
  final patches = <({String path, Object? data})>[];
  final deletes = <String>[];

  /// When set, `get` waits on it: a fetch in flight.
  Completer<void>? getGate;

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    final gate = getGate;
    if (gate != null) await gate.future;
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: user,
    );
  }

  @override
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    deletes.add(path);
    user = {...user, 'avatar': null};
    return Response(
      requestOptions: RequestOptions(path: path),
      statusCode: 200,
      data: {'message': 'Profile photo removed', 'user': user},
    );
  }

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
  testWidgets('Save stays off while a reload holds an old profile the form '
      'never showed (todo 565 finding 5)', (tester) async {
    // The provider is alive before the screen opens (another screen holds
    // it) and reloading: `.value` is the old profile, but the form, and so
    // the bio field, is not on screen. Save used to send "" here.
    final api = _FakeApi()..user = _user(bio: 'Grows ferns.');
    final container = ProviderContainer(
      overrides: [apiServiceProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    final holding = container.listen(userProfileServiceProvider, (_, _) {});
    addTearDown(holding.close);
    await container.read(userProfileServiceProvider.future);
    final gate = api.getGate = Completer<void>();
    container.invalidate(userProfileServiceProvider, asReload: true);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: EditProfileScreen()),
      ),
    );
    await tester.pump();

    expect(container.read(userProfileServiceProvider).value, isNotNull);
    final save = tester.widget<TextButton>(
      find.widgetWithText(TextButton, 'Save'),
    );
    expect(save.onPressed, isNull);

    gate.complete();
    await tester.pumpAndSettle();
    expect(find.widgetWithText(TextField, 'Grows ferns.'), findsOneWidget);
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, 'Save'))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('the avatar is a cached network image (todo 565 finding 7)', (
    tester,
  ) async {
    final api = _FakeApi()
      ..user = _user(avatar: 'https://cdn.example.test/avatars/me.jpg');
    await _pump(tester, api);

    final avatar = tester.widget<CircleAvatar>(find.byType(CircleAvatar));
    expect(avatar.backgroundImage, isA<CachedNetworkImageProvider>());
    expect(
      (avatar.backgroundImage! as CachedNetworkImageProvider).url,
      'https://cdn.example.test/avatars/me.jpg',
    );
  });

  testWidgets('Remove photo deletes the avatar after a confirmation '
      '(todo 565 finding 9)', (tester) async {
    final api = _FakeApi()
      ..user = _user(avatar: 'https://cdn.example.test/avatars/me.jpg');
    await _pump(tester, api);

    await tester.tap(find.text('Remove photo'));
    await tester.pumpAndSettle();
    expect(api.deletes, isEmpty, reason: 'removed before confirming');
    await tester.tap(find.widgetWithText(TextButton, 'Remove'));
    await tester.pumpAndSettle();

    expect(api.deletes, ['/auth/user/avatar/']);
    expect(find.text('Photo removed'), findsOneWidget);
    expect(find.text('Add photo'), findsOneWidget);
    expect(find.text('Remove photo'), findsNothing);
  });

  testWidgets('Remove photo is offered only when there is a photo', (
    tester,
  ) async {
    await _pump(tester, _FakeApi());

    expect(find.text('Remove photo'), findsNothing);
  });

  testWidgets('cancelling the removal sends nothing', (tester) async {
    final api = _FakeApi()
      ..user = _user(avatar: 'https://cdn.example.test/avatars/me.jpg');
    await _pump(tester, api);

    await tester.tap(find.text('Remove photo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(api.deletes, isEmpty);
    expect(find.text('Remove photo'), findsOneWidget);
  });
}

class _OversizedPicker implements ProfileAvatarPicker {
  @override
  Future<String?> pick() async => throw ApiException(
    'That photo is over 2 MB. Pick a smaller one.',
    statusCode: 413,
  );
}
