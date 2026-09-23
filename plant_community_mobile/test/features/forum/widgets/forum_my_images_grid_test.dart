// "My forum photos" grid (todo 374): the shared widget behind the composer's
// "Choose from your photos" sheet and the delete-your-photos screen.
//
// After any pump that mounts tiles, use bounded pump()s, never
// pumpAndSettle(): tiles are CachedNetworkImages, and the blocked-network
// test harness never resolves them (docs/rules/flutter.md).
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_my_images_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_my_images_grid.dart';
import 'package:plant_community_mobile/services/api_service.dart';

import '../support/forum_test_support.dart';

ForumImageBlock _image(int id, {String alt = ''}) => ForumImageBlock(
  id: id,
  url: 'https://example.com/forum/images/$id.jpg',
  alt: alt,
  width: 800,
  height: 600,
);

Finder _tile(int id) => find.byKey(ValueKey('forumMyImages.tile.$id'));

Finder _deleteButtonOn(int id) =>
    find.descendant(of: _tile(id), matching: find.byTooltip('Delete photo'));

const _empty = Key('forumMyImages.empty');
const _forbidden = Key('forumMyImages.forbidden');
const _error = Key('forumMyImages.error');

Future<void> _pumpGrid(
  WidgetTester tester,
  FakeForumApi api, {
  ValueChanged<ForumImageBlock>? onPick,
  bool allowDelete = false,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [forumApiProvider.overrideWithValue(api)],
      child: MaterialApp(
        home: Scaffold(
          body: ForumMyImagesGrid(onPick: onPick, allowDelete: allowDelete),
        ),
      ),
    ),
  );
  await tester.pump(); // the first fetch resolves
  await tester.pump();
}

Future<void> _pumpDialog(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  group('loading states', () {
    testWidgets('renders one tile per image and no empty/403/error state', (
      tester,
    ) async {
      // Positive control for every "absent" assertion below.
      final api = FakeForumApi()..myImages = [_image(1), _image(2)];
      await _pumpGrid(tester, api);

      expect(_tile(1), findsOneWidget);
      expect(_tile(2), findsOneWidget);
      expect(find.byKey(_empty), findsNothing);
      expect(find.byKey(_forbidden), findsNothing);
      expect(find.byKey(_error), findsNothing);
      expect(api.fetchMyImagesCalls, [null]);
    });

    testWidgets('an empty library is the empty state, not the 403 state', (
      tester,
    ) async {
      await _pumpGrid(tester, FakeForumApi());

      expect(find.byKey(_empty), findsOneWidget);
      expect(find.byKey(_forbidden), findsNothing);
      expect(find.byKey(_error), findsNothing);
    });

    testWidgets('a 403 is its own state, not empty and not a retryable error', (
      tester,
    ) async {
      // The message deliberately says nothing about "403" or "forbidden":
      // DRF's sentence doesn't either, so only the status can route this.
      final api = FakeForumApi()
        ..failFetchMyImagesWith = ApiException(
          'You do not have permission to browse forum images.',
          statusCode: 403,
        );
      await _pumpGrid(tester, api);

      expect(find.byKey(_forbidden), findsOneWidget);
      expect(find.byKey(_empty), findsNothing);
      expect(find.byKey(_error), findsNothing);
      expect(find.text('Retry'), findsNothing);
    });

    testWidgets('any other failure offers Retry, which reloads', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..myImages = [_image(1)]
        ..failFetchMyImagesWith = ApiException('boom', statusCode: 500);
      await _pumpGrid(tester, api);

      expect(find.byKey(_error), findsOneWidget);
      expect(find.byKey(_forbidden), findsNothing);
      expect(find.byKey(_empty), findsNothing);

      api.failFetchMyImagesWith = null;
      await tester.tap(find.text('Retry'));
      await tester.pump();
      await tester.pump();

      expect(_tile(1), findsOneWidget);
      expect(api.fetchMyImagesCalls, [null, null]);
    });
  });

  group('pagination', () {
    testWidgets('Load more passes the next URL through unchanged', (
      tester,
    ) async {
      const next =
          'https://api.example.com/forum/images/mine/?cursor=cD0yNA%3D%3D';
      final api = FakeForumApi()
        ..myImagePages = [
          CursorPage(items: [_image(1), _image(2)], next: next),
          CursorPage(items: [_image(3)]),
        ];
      await _pumpGrid(tester, api);

      expect(_tile(3), findsNothing);
      await tester.tap(find.text('Load more'));
      await tester.pump();
      await tester.pump();

      expect(api.fetchMyImagesCalls, [null, next]);
      expect(_tile(1), findsOneWidget);
      expect(_tile(3), findsOneWidget);
      // The last page has no `next`: nothing more to offer.
      expect(find.text('Load more'), findsNothing);
    });

    testWidgets('a failed Load more keeps what loaded and can be retried', (
      tester,
    ) async {
      const next = 'https://api.example.com/forum/images/mine/?cursor=abc';
      final api = FakeForumApi()
        ..myImagePages = [
          CursorPage(items: [_image(1)], next: next),
          CursorPage(items: [_image(2)]),
        ];
      await _pumpGrid(tester, api);

      api.failFetchMyImagesWith = ApiException('boom', statusCode: 500);
      await tester.tap(find.text('Load more'));
      await tester.pump();
      await tester.pump();

      expect(find.text('Could not load more photos.'), findsOneWidget);
      expect(_tile(1), findsOneWidget);
      expect(find.text('Load more'), findsOneWidget);
    });
  });

  group('picking', () {
    testWidgets('tapping a tile hands back that image; no delete buttons', (
      tester,
    ) async {
      final picked = <ForumImageBlock>[];
      final api = FakeForumApi()..myImages = [_image(1), _image(2)];
      await _pumpGrid(tester, api, onPick: picked.add);

      expect(find.byTooltip('Delete photo'), findsNothing);
      await tester.tap(_tile(2));
      await tester.pump();

      expect(picked.map((image) => image.id), [2]);
      expect(api.deleteMyImageCalls, isEmpty);
    });

    testWidgets('a screen reader can pick a tile: it carries a tap action', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      final picked = <ForumImageBlock>[];
      final api = FakeForumApi()..myImages = [_image(3, alt: 'Fern')];
      await _pumpGrid(tester, api, onPick: picked.add);

      final node = tester.getSemantics(
        find.bySemanticsLabel('Use this photo. Photo: Fern'),
      );
      expect(node.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);

      node.owner!.performAction(node.id, SemanticsAction.tap);
      await tester.pump();
      expect(picked.map((image) => image.id), [3]);
      handle.dispose();
    });

    testWidgets('showForumMyImagesPicker resolves to the tapped image', (
      tester,
    ) async {
      final api = FakeForumApi()..myImages = [_image(5, alt: 'Monstera')];
      ForumImageBlock? result;
      var resolved = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [forumApiProvider.overrideWithValue(api)],
          child: MaterialApp(
            home: Builder(
              builder: (context) => TextButton(
                onPressed: () async {
                  result = await showForumMyImagesPicker(context);
                  resolved = true;
                },
                child: const Text('open'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await _pumpDialog(tester);
      await tester.pump();

      expect(find.text('Choose from your photos'), findsOneWidget);
      await tester.tap(_tile(5));
      await _pumpDialog(tester);

      expect(resolved, isTrue);
      expect(result?.id, 5);
      expect(result?.alt, 'Monstera');
    });
  });

  group('deleting', () {
    testWidgets('Cancel sends nothing and keeps the tile', (tester) async {
      final api = FakeForumApi()..myImages = [_image(1)];
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      expect(find.text('Delete this photo?'), findsOneWidget);
      // The consequence is named before the user commits.
      expect(find.textContaining('disappear from any posts'), findsOneWidget);

      await tester.tap(find.text('Cancel'));
      await _pumpDialog(tester);

      expect(api.deleteMyImageCalls, isEmpty);
      expect(_tile(1), findsOneWidget);
    });

    testWidgets('confirming deletes that image and removes only its tile', (
      tester,
    ) async {
      final api = FakeForumApi()..myImages = [_image(1), _image(2)];
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(2));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);

      expect(api.deleteMyImageCalls, [2]);
      expect(api.myImages.map((image) => image.id), [1]);
      expect(_tile(2), findsNothing);
      expect(_tile(1), findsOneWidget);
      expect(find.text('Photo deleted.'), findsOneWidget);
    });

    testWidgets('deleting the last photo shows the empty state', (
      tester,
    ) async {
      final api = FakeForumApi()..myImages = [_image(1)];
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);

      expect(find.byKey(_empty), findsOneWidget);
    });

    testWidgets('deleting every loaded photo fetches the next page instead of '
        'claiming the library is empty', (tester) async {
      const next = 'https://api.example.com/forum/images/mine/?cursor=p2';
      final api = FakeForumApi()
        ..myImagePages = [
          CursorPage(items: [_image(1)], next: next),
          CursorPage(items: [_image(2)]),
        ];
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);
      await tester.pump();

      expect(api.fetchMyImagesCalls, [null, next]);
      expect(find.byKey(_empty), findsNothing);
      expect(_tile(2), findsOneWidget);
    });

    testWidgets('if that next-page fetch fails, Load more is offered, not '
        'the empty state', (tester) async {
      const next = 'https://api.example.com/forum/images/mine/?cursor=p2';
      final api = FakeForumApi()
        ..myImagePages = [
          CursorPage(items: [_image(1)], next: next),
          CursorPage(items: [_image(2)]),
        ];
      await _pumpGrid(tester, api, allowDelete: true);

      api.failFetchMyImagesWith = ApiException('boom', statusCode: 500);
      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);
      await tester.pump();

      expect(find.byKey(_empty), findsNothing);
      expect(find.text('Load more'), findsOneWidget);
    });

    testWidgets('a 403 explains and keeps the tile', (tester) async {
      final api = FakeForumApi()
        ..myImages = [_image(1)]
        ..failDeleteMyImageWith = ApiException(
          'You do not have permission to delete this image.',
          statusCode: 403,
        );
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);

      expect(api.deleteMyImageCalls, [1]);
      expect(
        find.text('You can only delete photos you uploaded.'),
        findsOneWidget,
      );
      expect(_tile(1), findsOneWidget);
    });

    testWidgets('a 429 surfaces the server message and keeps the tile', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..myImages = [_image(1)]
        ..failDeleteMyImageWith = ApiException(
          'Too many requests. Try again in 30 minutes.',
          statusCode: 429,
        );
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);

      expect(
        find.text('Too many requests. Try again in 30 minutes.'),
        findsOneWidget,
      );
      expect(_tile(1), findsOneWidget);
    });

    testWidgets('a 404 means it is already gone: the tile goes too', (
      tester,
    ) async {
      final api = FakeForumApi()
        ..myImages = [_image(1), _image(2)]
        ..failDeleteMyImageWith = ApiException('Not found.', statusCode: 404);
      await _pumpGrid(tester, api, allowDelete: true);

      await tester.tap(_deleteButtonOn(1));
      await _pumpDialog(tester);
      await tester.tap(find.text('Delete'));
      await _pumpDialog(tester);

      expect(_tile(1), findsNothing);
      expect(_tile(2), findsOneWidget);
    });
  });

  testWidgets('the My forum photos screen offers delete, not pick', (
    tester,
  ) async {
    final api = FakeForumApi()..myImages = [_image(1)];
    await tester.pumpWidget(
      ProviderScope(
        overrides: [forumApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: ForumMyImagesScreen()),
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(find.text('My forum photos'), findsOneWidget);
    expect(_deleteButtonOn(1), findsOneWidget);
    await tester.tap(_tile(1));
    await tester.pump();
    // Tapping the photo itself does nothing here: no dialog, no delete.
    expect(find.text('Delete this photo?'), findsNothing);
    expect(api.deleteMyImageCalls, isEmpty);
  });
}
