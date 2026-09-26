import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_body_renderer.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_html_text.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

Future<void> _pump(
  WidgetTester tester,
  List<ForumBodyBlock> blocks, {
  int? currentTopicId,
}) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: ForumBodyRenderer(blocks, currentTopicId: currentTopicId),
        ),
      ),
    ),
  );
}

/// The renderer behind a real router so a quote's "in topic" link can
/// navigate; returns the URIs the `forumTopic` route was opened with.
Future<List<Uri>> _pumpRouted(
  WidgetTester tester,
  List<ForumBodyBlock> blocks, {
  int? currentTopicId,
}) async {
  final opened = <Uri>[];
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, _) => Scaffold(
          body: ForumBodyRenderer(blocks, currentTopicId: currentTopicId),
        ),
      ),
      GoRoute(
        path: '/forum/topics/:id',
        name: 'forumTopic',
        builder: (_, state) {
          opened.add(state.uri);
          return const Scaffold(body: Text('topic'));
        },
      ),
    ],
  );
  await tester.pumpWidget(MaterialApp.router(routerConfig: router));
  return opened;
}

void main() {
  testWidgets('renders heading, paragraph, quote, code and unknown blocks', (
    tester,
  ) async {
    await _pump(tester, const [
      HeadingBlock('The heading'),
      ParagraphBlock('<p>Hello <strong>world</strong></p>'),
      QuoteBlock('A wise quote'),
      CodeBlock(code: 'print("hi")', language: 'dart'),
      UnknownBlock('gallery'),
    ]);

    expect(find.text('The heading'), findsOneWidget);
    expect(find.textContaining('world'), findsOneWidget);
    expect(find.text('A wise quote'), findsOneWidget);
    expect(find.text('print("hi")'), findsOneWidget);
    expect(
      find.textContaining('Unsupported content (gallery)'),
      findsOneWidget,
    );
  });

  testWidgets('image block renders a CachedNetworkImage', (tester) async {
    await _pump(tester, const [
      ForumImageBlock(
        id: 7,
        url: 'https://example.com/plant.png',
        alt: 'a plant',
        width: 100,
        height: 80,
      ),
    ]);
    expect(find.byType(CachedNetworkImage), findsOneWidget);
  });

  testWidgets('embed renders a thumbnail card, never a player', (tester) async {
    await _pump(tester, const [
      EmbedBlock(
        url: 'https://youtu.be/dQw4w9WgXcQ',
        providerName: 'YouTube',
        title: 'Repotting a monstera',
        thumbnailUrl: 'https://i.ytimg.com/t.jpg',
      ),
      EmbedBlock(url: 'https://vimeo.com/148751763'),
    ]);
    expect(find.text('Repotting a monstera'), findsOneWidget);
    expect(find.text('Watch on YouTube'), findsOneWidget);
    expect(find.byType(CachedNetworkImage), findsOneWidget); // thumbnail only
    // No provider, no title: the link itself is the label.
    expect(find.text('https://vimeo.com/148751763'), findsNWidgets(2));
  });

  testWidgets(
    'tapping an embed card hands its URL to onOpenLink, like a link',
    (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ForumBodyRenderer(const [
              EmbedBlock(url: 'https://youtu.be/dQw4w9WgXcQ', title: 'T'),
            ], onOpenLink: opened.add),
          ),
        ),
      );
      await tester.tap(find.text('T'));
      expect(opened, ['https://youtu.be/dQw4w9WgXcQ']);
    },
  );

  testWidgets(
    'a screen reader can open an embed card: it carries a tap action',
    (tester) async {
      final handle = tester.ensureSemantics();
      final opened = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ForumBodyRenderer(const [
              EmbedBlock(url: 'https://youtu.be/dQw4w9WgXcQ', title: 'T'),
            ], onOpenLink: opened.add),
          ),
        ),
      );

      final node = tester.getSemantics(find.bySemanticsLabel(RegExp(r': T$')));
      expect(node.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);

      node.owner!.performAction(node.id, SemanticsAction.tap);
      await tester.pump();
      expect(opened, ['https://youtu.be/dQw4w9WgXcQ']);
      handle.dispose();
    },
  );

  testWidgets('an embed card with no URL is not announced as a button', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ForumBodyRenderer(const [
            EmbedBlock(url: '', title: 'T'),
          ], onOpenLink: (_) {}),
        ),
      ),
    );

    final data = tester
        .getSemantics(find.bySemanticsLabel(RegExp(r': T$')))
        .getSemanticsData();
    expect(data.flagsCollection.isButton, isFalse);
    expect(data.hasAction(SemanticsAction.tap), isFalse);
    handle.dispose();
  });

  testWidgets('a blank embed envelope renders the unavailable placeholder', (
    tester,
  ) async {
    await _pump(tester, const [EmbedBlock(url: '')]);
    expect(find.textContaining('Video unavailable'), findsOneWidget);
  });

  testWidgets('deleted image renders the unavailable placeholder', (
    tester,
  ) async {
    await _pump(tester, const [DeletedImageBlock()]);
    expect(find.textContaining('Image unavailable'), findsOneWidget);
  });

  testWidgets('empty body renders nothing tall', (tester) async {
    await _pump(tester, const []);
    expect(find.byType(ForumBodyRenderer), findsOneWidget);
  });

  group('post_quote (todo 342)', () {
    const bob = ForumAuthor(
      username: 'bob',
      displayName: 'Bob B',
      trustLevel: 2,
    );
    const live = PostQuoteBlock(
      text: 'Water it less.',
      postId: 42,
      available: true,
      topicId: 7,
      author: bob,
    );

    testWidgets('an available quote shows the text, who wrote it and an '
        '"in topic" link with a 48dp target', (tester) async {
      await _pump(tester, const [live]);

      expect(find.text('Water it less.'), findsOneWidget);
      expect(find.text('Bob B'), findsOneWidget);
      expect(find.text('in topic'), findsOneWidget);
      expect(find.textContaining('no longer available'), findsNothing);
      // Neither flag set: the normal card, nothing collapsed.
      expect(find.text('Show anyway'), findsNothing);
      expect(find.textContaining('a member you'), findsNothing);
      expect(
        tester.getSize(find.byType(TextButton)).height,
        greaterThanOrEqualTo(48),
      );
    });

    testWidgets('a quote of a post in the CURRENT topic keeps the '
        'attribution but drops "in topic"', (tester) async {
      await _pump(tester, const [live], currentTopicId: 7);

      expect(find.text('Water it less.'), findsOneWidget);
      expect(find.byType(AuthorAvatar), findsOneWidget);
      expect(find.text('Bob B'), findsOneWidget);
      // Pushing the thread the viewer is already on would stack a duplicate.
      expect(find.text('in topic'), findsNothing);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('a quote of a post in ANOTHER topic still links there when '
        'the surface knows its own topic', (tester) async {
      final opened = await _pumpRouted(tester, const [live], currentTopicId: 3);

      await tester.tap(find.text('in topic'));
      await tester.pumpAndSettle();

      expect(opened.single.path, '/forum/topics/7');
      expect(opened.single.queryParameters, {'postId': '42'});
    });

    testWidgets('announces itself as a quote from its author; "a member" '
        'once the author is gone', (tester) async {
      await _pump(tester, const [live]);
      expect(
        find.bySemanticsLabel(RegExp('^Quote from Bob B')),
        findsOneWidget,
      );

      await _pump(tester, const [
        PostQuoteBlock(text: 'Gone now', postId: 43, available: false),
      ]);
      expect(
        find.bySemanticsLabel(RegExp('^Quote from a member')),
        findsOneWidget,
      );
    });

    testWidgets('an available quote whose envelope lacks author and topic '
        'renders the excerpt neutrally — never the "gone" notice', (
      tester,
    ) async {
      await _pump(tester, const [
        PostQuoteBlock(text: 'Orphan excerpt', postId: 44, available: true),
      ]);

      expect(find.text('Orphan excerpt'), findsOneWidget);
      expect(find.textContaining('no longer available'), findsNothing);
      expect(find.byType(AuthorAvatar), findsNothing);
      expect(find.text('in topic'), findsNothing);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('an author with no topic id is named but not linked', (
      tester,
    ) async {
      await _pump(tester, const [
        PostQuoteBlock(
          text: 'No topic',
          postId: 45,
          available: true,
          author: bob,
        ),
      ]);

      expect(find.text('No topic'), findsOneWidget);
      expect(find.text('Bob B'), findsOneWidget);
      expect(find.textContaining('no longer available'), findsNothing);
      expect(find.text('in topic'), findsNothing);
    });

    group('blocked / muted author', () {
      const blocked = PostQuoteBlock(
        text: 'Water it less.',
        postId: 42,
        available: true,
        topicId: 7,
        author: bob,
        isBlocked: true,
      );

      testWidgets('a blocked author\'s quote collapses to a one-line notice '
          'with no excerpt in the tree; "Show anyway" reveals the card', (
        tester,
      ) async {
        await _pump(tester, const [blocked]);

        expect(find.text('Quote from a member you blocked.'), findsOneWidget);
        expect(find.byIcon(LucideIcons.ban), findsOneWidget);
        expect(find.text('Show anyway'), findsOneWidget);
        expect(find.text('Water it less.'), findsNothing);
        expect(find.text('Bob B'), findsNothing);
        expect(find.text('in topic'), findsNothing);
        // Collapsed, not hidden: the block still occupies the body.
        expect(find.byType(ForumBodyRenderer), findsOneWidget);

        await tester.tap(find.text('Show anyway'));
        await tester.pump();

        expect(find.text('Quote from a member you blocked.'), findsNothing);
        expect(find.text('Show anyway'), findsNothing);
        expect(find.text('Water it less.'), findsOneWidget);
        expect(find.text('Bob B'), findsOneWidget);
        expect(find.text('in topic'), findsOneWidget);
      });

      testWidgets('a muted author gets the muted wording', (tester) async {
        await _pump(tester, const [
          PostQuoteBlock(
            text: 'Water it less.',
            postId: 42,
            available: true,
            topicId: 7,
            author: bob,
            isMuted: true,
          ),
        ]);

        expect(find.text('Quote from a member you muted.'), findsOneWidget);
        expect(find.byIcon(LucideIcons.volumeX), findsOneWidget);
        expect(find.text('Show anyway'), findsOneWidget);
        expect(find.text('Water it less.'), findsNothing);
        expect(find.textContaining('blocked'), findsNothing);
      });

      testWidgets('blocked wins the wording when both flags are set', (
        tester,
      ) async {
        await _pump(tester, const [
          PostQuoteBlock(
            text: 'Water it less.',
            postId: 42,
            available: true,
            topicId: 7,
            author: bob,
            isBlocked: true,
            isMuted: true,
          ),
        ]);

        expect(find.text('Quote from a member you blocked.'), findsOneWidget);
        expect(find.textContaining('muted'), findsNothing);
      });
    });

    testWidgets('a gone quote keeps its text under a muted notice, no link', (
      tester,
    ) async {
      await _pump(tester, const [
        PostQuoteBlock(text: 'Gone now', postId: 43, available: false),
      ]);

      expect(find.text('Gone now'), findsOneWidget);
      expect(find.text('Quoted post is no longer available'), findsOneWidget);
      expect(find.text('in topic'), findsNothing);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('the text is plain: markup renders literally, never as HTML', (
      tester,
    ) async {
      const hostile = '<script>alert(1)</script> & <b>bold</b>';
      await _pump(tester, const [
        PostQuoteBlock(
          text: hostile,
          postId: 42,
          available: true,
          topicId: 7,
          author: bob,
        ),
      ]);

      expect(find.text(hostile), findsOneWidget);
      expect(find.byType(ForumHtmlText), findsNothing);
    });

    testWidgets('"in topic" opens the quoted post in its topic', (
      tester,
    ) async {
      final opened = await _pumpRouted(tester, const [live]);

      await tester.tap(find.text('in topic'));
      await tester.pumpAndSettle();

      expect(opened.single.path, '/forum/topics/7');
      expect(opened.single.queryParameters, {'postId': '42'});
    });
  });

  group('link preview card (todo 428)', () {
    const fullUrl = 'https://microsoft.com/en-us/windows/some/long/path?x=1';
    const short = 'https://microsoft.com/…';
    const card = LinkPreviewBlock(
      url: fullUrl,
      title: 'Windows 11',
      description: 'The newest Windows.',
      siteName: 'Microsoft',
      domain: 'microsoft.com',
    );

    Future<List<String>> pumpCard(
      WidgetTester tester, {
      LinkPreviewBlock block = card,
    }) async {
      final opened = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ForumBodyRenderer([block], onOpenLink: opened.add),
          ),
        ),
      );
      return opened;
    }

    List<String> clipboardWrites(WidgetTester tester) {
      final writes = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'Clipboard.setData') {
            writes.add((call.arguments as Map)['text'] as String);
          }
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      return writes;
    }

    testWidgets('shows the title, site and short address — never the URL', (
      tester,
    ) async {
      await pumpCard(tester);

      expect(find.text('Windows 11'), findsOneWidget);
      expect(find.text('MICROSOFT'), findsOneWidget);
      expect(find.text('The newest Windows.'), findsOneWidget);
      expect(find.text(short), findsOneWidget);
      expect(find.textContaining('/en-us/'), findsNothing);
    });

    testWidgets('falls back to the short address when the page gave no title', (
      tester,
    ) async {
      await pumpCard(tester, block: const LinkPreviewBlock(url: fullUrl));

      expect(find.text(short), findsOneWidget);
      expect(find.textContaining('/en-us/'), findsNothing);
    });

    testWidgets('tapping hands the full URL to onOpenLink', (tester) async {
      final opened = await pumpCard(tester);

      await tester.tap(find.text('Windows 11'));
      expect(opened, [fullUrl]);
    });

    testWidgets(
      'the spoken label is the title and short address, not the URL',
      (tester) async {
        final handle = tester.ensureSemantics();
        final opened = await pumpCard(tester);

        final node = tester.getSemantics(
          find.bySemanticsLabel('Link: Windows 11, $short'),
        );
        final data = node.getSemanticsData();
        expect(data.label, isNot(contains('/en-us/')));
        expect(data.hint, isNot(contains('/en-us/')));
        expect(data.value, isNot(contains('/en-us/')));
        expect(data.hasAction(SemanticsAction.tap), isTrue);

        node.owner!.performAction(node.id, SemanticsAction.tap);
        await tester.pump();
        expect(opened, [fullUrl]);
        // No other node on screen speaks the full URL either, and the card
        // is ONE node: without excludeSemantics the InkWell adds a focusable
        // child with its own tap action and no label — an unlabeled button.
        expect(find.bySemanticsLabel(RegExp('/en-us/')), findsNothing);
        expect(node.childrenCount, 0);
        handle.dispose();
      },
    );

    testWidgets('a long-press shows the full address with "Copy link"', (
      tester,
    ) async {
      final writes = clipboardWrites(tester);
      await pumpCard(tester);

      await tester.longPress(find.text('Windows 11'));
      await tester.pumpAndSettle();
      expect(find.text(fullUrl), findsOneWidget);

      await tester.tap(find.text('Copy link'));
      await tester.pumpAndSettle();
      expect(writes, [fullUrl]);
      expect(find.text('Link copied'), findsOneWidget);
      expect(find.text(fullUrl), findsNothing); // the sheet closed
    });

    testWidgets('a screen reader reaches the full address and "Copy link" '
        'as custom actions, with no gesture', (tester) async {
      final handle = tester.ensureSemantics();
      final writes = clipboardWrites(tester);
      await pumpCard(tester);
      final cardNode = find.semantics.byLabel('Link: Windows 11, $short');

      tester.semantics.customAction(
        cardNode,
        const CustomSemanticsAction(label: 'Show full address'),
      );
      await tester.pumpAndSettle();
      expect(find.text(fullUrl), findsOneWidget);
      Navigator.of(tester.element(find.text(fullUrl))).pop();
      await tester.pumpAndSettle();

      tester.semantics.customAction(
        cardNode,
        const CustomSemanticsAction(label: 'Copy link'),
      );
      await tester.pumpAndSettle();
      expect(writes, [fullUrl]);
      handle.dispose();
    });

    testWidgets('a card with no usable link renders nothing', (tester) async {
      await pumpCard(
        tester,
        block: const LinkPreviewBlock(url: '', title: 'Stale'),
      );

      expect(find.text('Stale'), findsNothing);
      expect(find.textContaining('Unsupported'), findsNothing);
    });

    testWidgets('a stored card image is shown from its own URL', (
      tester,
    ) async {
      await pumpCard(
        tester,
        block: const LinkPreviewBlock(
          url: fullUrl,
          title: 'T',
          imageUrl: 'https://media.example.org/forum/link-previews/x.webp',
        ),
      );

      expect(
        tester
            .widget<CachedNetworkImage>(find.byType(CachedNetworkImage))
            .imageUrl,
        'https://media.example.org/forum/link-previews/x.webp',
      );
    });
  });
}
