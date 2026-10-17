// The composer previews the link cards readers will get (todo 654), and a
// post the server split into paragraphs and cards opens editable (todo 655).
//
// After the card appears, use bounded pump()s, never pumpAndSettle(): its
// image is a CachedNetworkImage, which the blocked-network test harness
// never resolves (docs/rules/flutter.md).
import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/forum_rich_text_markup.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/screens/forum_composer_screen.dart';
import 'package:plant_community_mobile/features/forum/services/forum_api.dart';
import 'package:plant_community_mobile/features/forum/widgets/link_preview_card_view.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import 'support/forum_test_support.dart';

const _debounce = Duration(milliseconds: 450);
const _url = 'https://en.wikipedia.org/wiki/Monstera';

LinkPreviewBlock _card(
  String url, {
  String title = 'Monstera',
  String image = '',
}) => LinkPreviewBlock(
  url: url,
  title: title,
  siteName: 'Wikipedia',
  domain: 'en.wikipedia.org',
  imageUrl: image,
);

final _preview = find.byKey(const ValueKey('composer-link-preview'));

Future<void> _pumpComposer(
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
      child: MaterialApp(home: ForumComposerScreen(args: args)),
    ),
  );
  await tester.pump();
}

Future<void> _type(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField).last, text);
  await tester.pump();
}

void main() {
  group('the composer link preview (todo 654)', () {
    testWidgets('a link on its own line shows the reader card after the '
        'debounce, with the site https image', (tester) async {
      final api = FakeForumApi()
        ..linkPreviews = {
          _url: _card(_url, image: 'https://upload.example/og.png'),
        };
      await _pumpComposer(tester, api);

      await _type(tester, 'Look at this plant:\n$_url\nLovely.');
      await tester.pump(_debounce - const Duration(milliseconds: 50));
      expect(api.linkPreviewCalls, isEmpty, reason: 'still debouncing');
      expect(_preview, findsNothing);

      await tester.pump(const Duration(milliseconds: 60));
      await tester.pump();

      expect(api.linkPreviewCalls, [_url]);
      // The very widget the reader draws, not a lookalike.
      expect(
        find.descendant(
          of: _preview,
          matching: find.byType(LinkPreviewCardView),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(of: _preview, matching: find.text('Monstera')),
        findsOneWidget,
      );
      expect(
        tester
            .widget<CachedNetworkImage>(
              find.descendant(
                of: _preview,
                matching: find.byType(CachedNetworkImage),
              ),
            )
            .imageUrl,
        'https://upload.example/og.png',
      );
      // A tap in the composer opens nothing.
      final card = tester.widget<LinkPreviewCardView>(
        find.byType(LinkPreviewCardView),
      );
      expect(card.onOpenLink, isNull);
    });

    testWidgets('a card whose image is not https shows without an image', (
      tester,
    ) async {
      // The API keeps only an https image (forum_api_link_preview_test.dart),
      // so the composer gets an empty one and draws no image.
      final api = FakeForumApi()..linkPreviews = {_url: _card(_url)};
      await _pumpComposer(tester, api);

      await _type(tester, _url);
      await tester.pump(_debounce);
      await tester.pump();

      expect(_preview, findsOneWidget);
      expect(find.byType(CachedNetworkImage), findsNothing);
    });

    for (final (name, text) in [
      ('a URL inside prose', 'Read $_url first.'),
      ('a list item', '- $_url'),
      ('inline code', '`$_url`'),
      ('a video URL', 'https://youtu.be/dQw4w9WgXcQ'),
    ]) {
      testWidgets('$name shows no card and is never fetched', (tester) async {
        final api = FakeForumApi()..linkPreviews = {_url: _card(_url)};
        await _pumpComposer(tester, api);

        await _type(tester, text);
        await tester.pump(_debounce * 2);

        expect(api.linkPreviewCalls, isEmpty);
        expect(_preview, findsNothing);
        expect(find.textContaining('more link'), findsNothing);
      });
    }

    testWidgets('an available: false reply shows no card', (tester) async {
      final api = FakeForumApi(); // no preview for any URL: available false
      await _pumpComposer(tester, api);

      await _type(tester, _url);
      await tester.pump(_debounce);
      await tester.pump();

      expect(api.linkPreviewCalls, [_url]);
      expect(_preview, findsNothing);
    });

    testWidgets('with several link lines the first gets the card and the hint '
        'counts the rest up to the ceiling, not a video', (tester) async {
      final urls = [for (var n = 0; n < 7; n++) 'https://site$n.example/'];
      final api = FakeForumApi()..linkPreviews = {urls[0]: _card(urls[0])};
      await _pumpComposer(tester, api);

      await _type(
        tester,
        ['Sites:', urls[0], 'https://youtu.be/dQw4w9WgXcQ', urls[1]].join('\n'),
      );
      await tester.pump(_debounce);
      await tester.pump();
      expect(api.linkPreviewCalls, [urls[0]]);
      expect(_preview, findsOneWidget);
      expect(find.text('+1 more link will show as a card'), findsOneWidget);

      // Seven link lines: five cards at most, so four more than the first.
      await _type(tester, urls.join('\n'));
      await tester.pump(_debounce);
      await tester.pump();
      expect(find.text('+4 more links will show as cards'), findsOneWidget);
      // Only the first link is ever fetched; it did not change.
      expect(api.linkPreviewCalls, [urls[0]]);
    });

    testWidgets('editing the URL replaces the card', (tester) async {
      const other = 'https://example.com/other';
      final api = FakeForumApi()
        ..linkPreviews = {
          _url: _card(_url),
          other: _card(other, title: 'Other page'),
        };
      await _pumpComposer(tester, api);

      await _type(tester, _url);
      await tester.pump(_debounce);
      await tester.pump();
      expect(find.text('Monstera'), findsOneWidget);

      await _type(tester, other);
      // The old card goes at once; the new one comes after the debounce.
      expect(find.text('Monstera'), findsNothing);
      await tester.pump(_debounce);
      await tester.pump();
      expect(find.text('Other page'), findsOneWidget);
      expect(api.linkPreviewCalls, [_url, other]);
    });

    testWidgets('a stale reply never shows', (tester) async {
      const other = 'https://example.com/other';
      final gate = Completer<void>();
      final api = FakeForumApi()
        ..linkPreviews = {
          _url: _card(_url),
          other: _card(other, title: 'Other page'),
        }
        ..linkPreviewGates = {_url: gate};
      await _pumpComposer(tester, api);

      await _type(tester, _url);
      await tester.pump(_debounce); // the first request is now in flight
      expect(api.linkPreviewCalls, [_url]);

      await _type(tester, other);
      await tester.pump(_debounce);
      await tester.pump();
      expect(find.text('Other page'), findsOneWidget);

      gate.complete(); // the first link's reply arrives late
      await tester.pump();
      await tester.pump();
      expect(find.text('Monstera'), findsNothing);
      expect(find.text('Other page'), findsOneWidget);
    });

    testWidgets('dispose cancels the debounce timer', (tester) async {
      final api = FakeForumApi()..linkPreviews = {_url: _card(_url)};
      await _pumpComposer(tester, api);

      await _type(tester, _url);
      await tester.pumpWidget(const SizedBox()); // the composer is gone
      await tester.pump(_debounce * 2);

      // No request after the screen closed, and no pending timer left (the
      // test harness fails a test that ends with one).
      expect(api.linkPreviewCalls, isEmpty);
    });

    for (final (name, configure) in <(String, void Function(FakeForumApi))>[
      (
        'a throttled preview',
        (api) => api.failLinkPreviewWith = ApiException(
          'Too many requests',
          statusCode: 429,
        ),
      ),
      ('a failed preview', (api) => api.failLinkPreviewWith = StateError('x')),
    ]) {
      testWidgets('$name shows nothing and the post still submits', (
        tester,
      ) async {
        final api = FakeForumApi();
        configure(api);
        await _pumpComposer(tester, api);

        await _type(tester, 'Hello\n$_url');
        await tester.pump(_debounce);
        await tester.pump();
        expect(api.linkPreviewCalls, [_url]);
        expect(_preview, findsNothing);
        // No error shown for a preview: it is a convenience, not a step.
        expect(find.textContaining('Too many'), findsNothing);

        await tester.tap(find.widgetWithText(FilledButton, 'Post'));
        await tester.pump();
        await tester.pump();
        expect(api.createReplyKeys, hasLength(1));
        expect(api.createReplyBodies.single.single, {
          'type': 'paragraph',
          'value': 'Hello<br>$_url',
        });
      });
    }
  });

  group('a post the server split into paragraphs and cards (todo 655)', () {
    // What the server stores for the composer's "Intro\nurl\nOutro":
    // paragraph, card, paragraph (todo 655, test_link_previews.py).
    final split = <ForumBodyBlock>[
      const ParagraphBlock('Intro'),
      _card(_url),
      const ParagraphBlock(
        '<a href="https://x.example/" target="_blank" '
        'rel="noopener noreferrer nofollow">https://x.example/</a> and '
        '<strong>bold</strong>',
      ),
      const EmbedBlock(url: 'https://youtu.be/dQw4w9WgXcQ'),
      const ParagraphBlock('Outro<br>second line'),
    ];

    test('opens fully editable, in body order, each card as its URL', () {
      final args = ForumComposeArgs.edit(post: post(id: 7, body: split));

      expect(args.hasNonTextContent, isFalse);
      expect(
        args.initialBodyText,
        [
          'Intro',
          _url,
          '[https://x.example/](https://x.example/) and **bold**',
          'https://youtu.be/dQw4w9WgXcQ',
          'Outro',
          'second line',
        ].join('\n'),
      );
    });

    test('saving it unchanged sends the lines the server splits back into '
        'the same blocks', () {
      final args = ForumComposeArgs.edit(
        post: post(
          id: 7,
          body: [
            const ParagraphBlock('Intro'),
            _card(_url),
            const ParagraphBlock('Outro'),
          ],
        ),
      );

      // buildParagraphBody's HTML: what the backend round-trip test
      // (test_655_an_unchanged_resave_of_a_split_post_stores_the_same_body)
      // resends and gets the same stored body back from, with no fetch.
      expect(buildParagraphBody(args.initialBodyText), [
        {'type': 'paragraph', 'value': 'Intro<br>$_url<br>Outro'},
      ]);
    });

    test('a URL with a marker character round-trips escaped', () {
      const url = 'https://en.wikipedia.org/wiki/Monstera_deliciosa';
      final args = ForumComposeArgs.edit(
        post: post(id: 7, body: [const ParagraphBlock('Intro'), _card(url)]),
      );

      expect(generateForumRichHtml(args.initialBodyText), 'Intro<br>$url');
    });

    for (final (name, block) in <(String, ForumBodyBlock)>[
      ('a heading', const HeadingBlock('H')),
      ('an image', const ForumImageBlock(id: 1, url: '/i.jpg', alt: '')),
      ('markup outside the grammar', const ParagraphBlock('<h2>Care</h2>')),
      ('a card with no usable link', const LinkPreviewBlock(url: '')),
    ]) {
      test('$name among them still warns', () {
        final args = ForumComposeArgs.edit(
          post: post(
            id: 7,
            body: [const ParagraphBlock('Intro'), _card(_url), block],
          ),
        );

        expect(args.hasNonTextContent, isTrue);
        expect(args.initialBodyText, isEmpty);
      });
    }

    testWidgets('opens in the composer with no warning, and its card is '
        'previewed', (tester) async {
      final api = FakeForumApi()..linkPreviews = {_url: _card(_url)};
      await _pumpComposer(
        tester,
        api,
        args: ForumComposeArgs.edit(
          post: post(
            id: 7,
            canEdit: true,
            body: [
              const ParagraphBlock('Intro'),
              _card(_url),
              const ParagraphBlock('Outro'),
            ],
          ),
        ),
      );

      expect(find.textContaining("can't show here yet"), findsNothing);
      final field = tester.widget<TextField>(find.byType(TextField).last);
      expect(field.controller!.text, 'Intro\n$_url\nOutro');
      await tester.pump(_debounce);
      await tester.pump();
      expect(_preview, findsOneWidget);
    });
  });
}
