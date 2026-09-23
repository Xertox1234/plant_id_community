// Composer "Choose from your photos" (todo 374): attaching an image the user
// already shared references its id. No upload, no new image row.
//
// Bounded pump()s after anything that mounts a CachedNetworkImage (the picker
// tiles, the attached thumbnail): the blocked-network harness never resolves
// them, so pumpAndSettle() would time out (docs/rules/flutter.md).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../support/forum_test_support.dart';

const _reused = ForumImageBlock(
  id: 7,
  url: 'https://example.com/forum/images/7.jpg',
  alt: 'Yellowing monstera leaf',
  width: 800,
  height: 600,
);

final _chooseButton = find.widgetWithText(
  OutlinedButton,
  'Choose from your photos',
);
final _tile7 = find.byKey(const ValueKey('forumMyImages.tile.7'));

Future<void> _pumpComposerBehindHome(
  WidgetTester tester,
  FakeForumApi api, {
  ForumComposeArgs args = const ForumComposeArgs.reply(topicId: 10),
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        forumApiProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => FakeAuthService(loggedIn: true)),
      ],
      child: MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => ForumComposerScreen(args: args),
                ),
              ),
              child: const Text('open composer'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open composer'));
  await tester.pumpAndSettle();
}

Future<void> _pumpSheet(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
  await tester.pump();
}

Future<void> _pickReused(WidgetTester tester) async {
  await tester.tap(_chooseButton);
  await _pumpSheet(tester);
  await tester.tap(_tile7);
  await _pumpSheet(tester);
}

void main() {
  testWidgets('picking a photo attaches it without uploading, and the reply '
      'references its id', (tester) async {
    final api = FakeForumApi()..myImages = [_reused];
    await _pumpComposerBehindHome(tester, api);

    await _pickReused(tester);

    // The thumbnail replaced both attach buttons; nothing went over the wire
    // except the list read.
    expect(_chooseButton, findsNothing);
    expect(find.byTooltip('Remove photo'), findsOneWidget);
    expect(api.uploadImageFilePaths, isEmpty);
    expect(api.uploadImageKeys, isEmpty);
    expect(api.fetchMyImagesCalls, [null]);

    await tester.enterText(find.byType(TextField), 'same plant, a week on');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(api.createReplyBodies.single, [
      {'type': 'paragraph', 'value': 'same plant, a week on'},
      {'type': 'image', 'value': 7},
    ]);
  });

  testWidgets('an image alone is enough to post a new topic', (tester) async {
    final api = FakeForumApi()..myImages = [_reused];
    await _pumpComposerBehindHome(
      tester,
      api,
      args: const ForumComposeArgs.topic(boardSlug: 'general'),
    );

    await tester.enterText(find.byType(TextField).first, 'What is this?');
    await _pickReused(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Post'));
    await tester.pumpAndSettle();

    expect(api.createTopicBodies.single, [
      {'type': 'image', 'value': 7},
    ]);
    expect(api.uploadImageKeys, isEmpty);
  });

  testWidgets('dismissing the sheet attaches nothing', (tester) async {
    final api = FakeForumApi()..myImages = [_reused];
    await _pumpComposerBehindHome(tester, api);

    await tester.tap(_chooseButton);
    await _pumpSheet(tester);
    expect(_tile7, findsOneWidget); // positive control: the sheet is open
    await tester.tapAt(const Offset(10, 10)); // the barrier above the sheet
    await _pumpSheet(tester);

    expect(_tile7, findsNothing);
    expect(_chooseButton, findsOneWidget);
    expect(find.byTooltip('Remove photo'), findsNothing);
  });

  testWidgets('a picked photo with no text is unsent input for the back '
      'guard', (tester) async {
    final api = FakeForumApi()..myImages = [_reused];
    await _pumpComposerBehindHome(tester, api);

    await _pickReused(tester);
    await tester.pageBack();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Discard draft?'), findsOneWidget);
  });

  testWidgets('removing a picked photo offers both attach buttons again', (
    tester,
  ) async {
    final api = FakeForumApi()..myImages = [_reused];
    await _pumpComposerBehindHome(tester, api);

    await _pickReused(tester);
    await tester.tap(find.byTooltip('Remove photo'));
    await tester.pump();

    expect(_chooseButton, findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Add photo'), findsOneWidget);
  });
}
