import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_body_renderer.dart';

/// Todo 429: a run of 2+ consecutive cards shows the first as a full card
/// and each later one as a compact row.

const _a = EmbedBlock(
  url: 'https://youtu.be/a',
  title: 'Alpha',
  providerName: 'YouTube',
);
const _b = EmbedBlock(
  url: 'https://youtu.be/b',
  title: 'Bravo',
  providerName: 'YouTube',
);
const _c = EmbedBlock(
  url: 'https://vimeo.com/3',
  title: 'Charlie',
  providerName: 'Vimeo',
);
const _link = LinkPreviewBlock(
  url: 'https://example.org/guide',
  title: 'Delta guide',
  siteName: 'Example',
  domain: 'example.org',
);

Future<List<String>> _pump(
  WidgetTester tester,
  List<ForumBodyBlock> blocks,
) async {
  final opened = <String>[];
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: ForumBodyRenderer(blocks, onOpenLink: opened.add),
        ),
      ),
    ),
  );
  return opened;
}

/// Only a FULL embed card has the "Watch on PROVIDER" line; a compact row
/// shows the bare provider.
int _fullEmbedCards() => find.textContaining('Watch on ').evaluate().length;

void main() {
  testWidgets('three consecutive embeds: one full card, then two rows', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, const [_a, _b, _c]);

    expect(_fullEmbedCards(), 1);
    expect(find.text('Watch on YouTube'), findsOneWidget);
    // The rows: provider as the bare second line, labelled like the web's
    // rows, "title, provider" (todo 453).
    expect(find.text('Vimeo'), findsOneWidget);
    expect(find.bySemanticsLabel('Bravo, YouTube'), findsOneWidget);
    expect(find.bySemanticsLabel('Charlie, Vimeo'), findsOneWidget);
    handle.dispose();
  });

  testWidgets('a lone embed renders as today, with no row', (tester) async {
    await _pump(tester, const [_a]);

    expect(_fullEmbedCards(), 1);
    expect(find.text('YouTube'), findsNothing);
  });

  testWidgets('a paragraph between two embeds ends the run', (tester) async {
    await _pump(tester, const [_a, ParagraphBlock('<p>between</p>'), _b]);

    expect(_fullEmbedCards(), 2);
    expect(find.text('YouTube'), findsNothing);
  });

  testWidgets(
    'each row is its own semantics node whose tap opens that row\'s URL',
    (tester) async {
      final handle = tester.ensureSemantics();
      final opened = await _pump(tester, const [_a, _b, _c]);

      for (final (label, url) in [
        ('Bravo, YouTube', 'https://youtu.be/b'),
        ('Charlie, Vimeo', 'https://vimeo.com/3'),
      ]) {
        final node = tester.getSemantics(find.bySemanticsLabel(label));
        final data = node.getSemanticsData();
        expect(data.hasAction(SemanticsAction.tap), isTrue);
        expect(data.flagsCollection.isButton, isTrue);
        // One node: the InkWell adds no unlabeled child (never merged/split).
        expect(node.childrenCount, 0);
        // A video row has no link actions.
        expect(data.hasAction(SemanticsAction.longPress), isFalse);
        expect(data.customSemanticsActionIds ?? const <int>[], isEmpty);
        node.owner!.performAction(node.id, SemanticsAction.tap);
        await tester.pump();
        expect(opened.last, url);
      }
      expect(opened, ['https://youtu.be/b', 'https://vimeo.com/3']);
      handle.dispose();
    },
  );

  testWidgets('a link card joins a run and its row keeps the address actions', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final opened = await _pump(tester, const [_a, _link]);

    final node = tester.getSemantics(
      find.bySemanticsLabel('Delta guide, https://example.org/…'),
    );
    final data = node.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.hasAction(SemanticsAction.longPress), isTrue);
    expect(data.customSemanticsActionIds, hasLength(2));
    expect(node.childrenCount, 0);

    await tester.tap(find.text('Delta guide'));
    expect(opened, ['https://example.org/guide']);
    handle.dispose();
  });

  testWidgets('a link row\'s custom actions show the address and copy it', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
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
    await _pump(tester, const [_a, _link]);
    final row = find.semantics.byLabel('Delta guide, https://example.org/…');

    tester.semantics.customAction(
      row,
      const CustomSemanticsAction(label: 'Show full address'),
    );
    await tester.pumpAndSettle();
    expect(find.text('https://example.org/guide'), findsOneWidget);
    Navigator.of(tester.element(find.text('https://example.org/guide'))).pop();
    await tester.pumpAndSettle();

    tester.semantics.customAction(
      row,
      const CustomSemanticsAction(label: 'Copy link'),
    );
    await tester.pumpAndSettle();
    expect(writes, ['https://example.org/guide']);
    handle.dispose();
  });

  testWidgets('a row shows its thumbnail at 72x48', (tester) async {
    await _pump(tester, const [
      _a,
      EmbedBlock(
        url: 'https://youtu.be/t',
        title: 'Thumbed',
        providerName: 'YouTube',
        thumbnailUrl: 'https://i.ytimg.com/t.jpg',
      ),
    ]);
    await tester.pump();

    final image = tester.widget<CachedNetworkImage>(
      find.byType(CachedNetworkImage),
    );
    expect(image.imageUrl, 'https://i.ytimg.com/t.jpg');
    expect(tester.getSize(find.byType(CachedNetworkImage)), const Size(72, 48));
  });

  testWidgets('a link card with no usable URL breaks the run', (tester) async {
    await _pump(tester, const [_a, LinkPreviewBlock(url: ''), _b]);

    expect(_fullEmbedCards(), 2);
    expect(find.text('YouTube'), findsNothing);
  });

  testWidgets(
    'a link row names its real address, never the page\'s own site name',
    (tester) async {
      final handle = tester.ensureSemantics();
      await _pump(tester, const [
        _c,
        LinkPreviewBlock(
          url: 'https://evil.example/watch',
          title: 'Watch this',
          siteName: 'YouTube',
          domain: 'evil.example',
        ),
      ]);

      expect(
        find.bySemanticsLabel('Watch this, https://evil.example/…'),
        findsOneWidget,
      );
      expect(find.text('https://evil.example/…'), findsOneWidget);
      expect(find.text('YouTube'), findsNothing);
      handle.dispose();
    },
  );

  testWidgets('a blank embed is not a card: it breaks the run', (tester) async {
    await _pump(tester, const [_a, EmbedBlock(url: ''), _b]);

    expect(find.text('Video unavailable'), findsOneWidget);
    expect(_fullEmbedCards(), 2);
  });

  testWidgets('a row is at least 48 dp tall', (tester) async {
    await _pump(tester, const [_a, _b]);

    final row = find.ancestor(
      of: find.text('Bravo'),
      matching: find.byType(InkWell),
    );
    expect(tester.getSize(row).height, greaterThanOrEqualTo(48));
  });

  test('the card-type set is one constant', () {
    expect(forumCardBlockTypes, {EmbedBlock, LinkPreviewBlock});
    expect(isForumCardBlock(_a), isTrue);
    expect(isForumCardBlock(_link), isTrue);
    expect(isForumCardBlock(const EmbedBlock(url: '')), isFalse);
    // Same rule as the web's isCardBlock: a URL-less or scheme-less embed
    // never joins a run, even with a title.
    expect(
      isForumCardBlock(const EmbedBlock(url: '', title: 'Old video')),
      isFalse,
    );
    expect(
      isForumCardBlock(const EmbedBlock(url: 'youtube.com/watch?v=x')),
      isFalse,
    );
    expect(isForumCardBlock(const HeadingBlock('H')), isFalse);
  });

  // Todo 453, finding 4 (owner decision 2026-09-30): all four labels match
  // the web's — "title, second line", the role saying what it is.
  testWidgets('full cards and rows are labelled like the web', (tester) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, const [
      _a,
      _link,
      ParagraphBlock('<p>between</p>'),
      _link,
      _b,
    ]);

    // Full cards: the video says what it shows — a match for the web's
    // no-player FALLBACK card only (a web player is an iframe titled
    // "Alpha"; todo 505) — and the link its short address.
    expect(find.bySemanticsLabel('Alpha, Watch on YouTube'), findsOneWidget);
    // Rows: "title, provider" and "title, address".
    expect(find.bySemanticsLabel('Bravo, YouTube'), findsOneWidget);
    expect(
      find.bySemanticsLabel('Delta guide, https://example.org/…'),
      findsNWidgets(2), // one full card, one row
    );
    // No label keeps the old "video:" / "Link:" prefix.
    expect(
      find.bySemanticsLabel(RegExp(r'video: |^Video: |^Link: ')),
      findsNothing,
    );
    handle.dispose();
  });

  testWidgets('a row or card with no second line is labelled by its title', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, const [
      EmbedBlock(url: 'https://youtu.be/x', title: 'No provider'),
      EmbedBlock(url: 'https://youtu.be/y', title: 'Also none'),
      LinkPreviewBlock(url: 'https://example.org'),
    ]);

    expect(find.bySemanticsLabel('No provider'), findsOneWidget);
    expect(find.bySemanticsLabel('Also none'), findsOneWidget);
    // The title IS the address: said once, not "address, address".
    expect(find.bySemanticsLabel('https://example.org'), findsOneWidget);
    handle.dispose();
  });

  // Todo 453, finding 2: one size for the tile, the image and the row.
  testWidgets('a row with no thumbnail shows its 72x48 placeholder tile', (
    tester,
  ) async {
    await _pump(tester, const [_a, _b]);

    final tile = find.descendant(
      of: find.ancestor(of: find.text('Bravo'), matching: find.byType(InkWell)),
      matching: find.byType(ClipRRect),
    );
    expect(tester.getSize(tile), const Size(72, 48));
    expect(find.byType(CachedNetworkImage), findsNothing);
  });

  // Todo 453, finding 3: a run on a 375 pt phone with long text, also at a
  // large text scale (LEARNINGS 2026-08-28, todo 317: the overflow only went
  // hard at larger text scales).
  for (final scale in [1.0, 2.0]) {
    testWidgets('a run with long titles fits a 375 pt screen at ${scale}x text', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(375, 812);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final long = 'A very long title about repotting ' * 6;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(
              size: const Size(375, 812),
              textScaler: TextScaler.linear(scale),
            ),
            child: Scaffold(
              body: SingleChildScrollView(
                child: ForumBodyRenderer([
                  _a,
                  EmbedBlock(
                    url: 'https://youtu.be/long',
                    title: long,
                    providerName: 'A provider with a very long name indeed',
                  ),
                  LinkPreviewBlock(
                    url:
                        'https://a-very-long-subdomain.of-a-very-long-domain.example.org/x',
                    title: long,
                    siteName: 'Example',
                  ),
                ], onOpenLink: (_) {}),
              ),
            ),
          ),
        ),
      );

      // No overflow at this scale, and each row's long title is cut to one
      // ellipsized line rather than pushing the row wider (todo 505: a
      // width check under a bounded parent proved nothing).
      expect(tester.takeException(), isNull);
      final titles = find.text(long);
      expect(titles, findsNWidgets(2)); // the video row and the link row
      for (final title in titles.evaluate()) {
        final text = title.widget as Text;
        expect(text.maxLines, 1);
        expect(text.overflow, TextOverflow.ellipsis);
        final paragraph = tester.renderObject<RenderParagraph>(
          find.descendant(
            of: find.byWidget(text),
            matching: find.byType(RichText),
          ),
        );
        expect(paragraph.didExceedMaxLines, isTrue);
        expect(paragraph.size.width, lessThan(375));
      }
    });
  }

  // Todo 453, finding 1: the run rule and the card read one derivation, so a
  // link card joins a run exactly when it renders something.
  testWidgets('a link card joins a run exactly when it renders', (
    tester,
  ) async {
    // Each case also states whether it SHOULD render (todo 505): the parity
    // checks alone pass even when linkPreviewDisplay's null rule is wrong,
    // since the card and the run rule both read it.
    const cases = [
      (LinkPreviewBlock(url: 'https://example.org/guide', title: 'T'), true),
      (LinkPreviewBlock(url: 'https://example.org'), true),
      (LinkPreviewBlock(url: 'http://example.org/x', siteName: 'S'), true),
      (LinkPreviewBlock(url: ''), false),
      (LinkPreviewBlock(url: 'example.org/guide', title: 'T'), false),
      (LinkPreviewBlock(url: 'javascript:alert(1)', title: 'T'), false),
      (LinkPreviewBlock(url: 'https://u:p@example.org/', title: 'T'), false),
    ];
    for (final (card, expected) in cases) {
      await _pump(tester, [card]);
      final renders = find.byType(InkWell).evaluate().isNotEmpty;
      expect(renders, expected, reason: card.url);
      expect(isForumCardBlock(card), renders, reason: card.url);
      expect(linkPreviewDisplay(card) != null, renders, reason: card.url);
    }
  });

  test(
    'linkPreviewDisplay derives the title fallback, second line and label',
    () {
      final full = linkPreviewDisplay(_link)!;
      expect(full.href, 'https://example.org/guide');
      expect(full.address, 'https://example.org/…');
      expect(full.title, 'Delta guide');
      expect(full.detail, 'https://example.org/…');
      expect(full.label, 'Delta guide, https://example.org/…');

      expect(
        linkPreviewDisplay(
          const LinkPreviewBlock(url: 'https://example.org/g', siteName: 'Ex'),
        )!.title,
        'Ex',
      );
      expect(
        linkPreviewDisplay(
          const LinkPreviewBlock(
            url: 'https://example.org/g',
            domain: 'ex.org',
          ),
        )!.title,
        'ex.org',
      );
      final bare = linkPreviewDisplay(
        const LinkPreviewBlock(url: 'https://example.org/g'),
      )!;
      expect(bare.title, 'https://example.org/…');
      expect(bare.detail, '');
      expect(bare.label, 'https://example.org/…');
    },
  );

  // Todo 505, findings 3 and 4: an untitled video row is titled and labelled
  // by its SHORT address, never the full URL a screen reader would spell out.
  testWidgets('an untitled video row says its short address, not its URL', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, const [
      _a,
      EmbedBlock(url: 'https://youtu.be/xyz?t=42', providerName: 'YouTube'),
      EmbedBlock(url: 'https://vimeo.com/77'),
    ]);

    expect(
      find.bySemanticsLabel('https://youtu.be/…, YouTube'),
      findsOneWidget,
    );
    expect(find.bySemanticsLabel('https://vimeo.com/…'), findsOneWidget);
    expect(find.text('https://youtu.be/…'), findsOneWidget);
    expect(find.text('https://vimeo.com/…'), findsOneWidget);
    // The full URLs are neither shown nor spoken.
    expect(find.bySemanticsLabel(RegExp(r'xyz|/77')), findsNothing);
    expect(find.textContaining('xyz'), findsNothing);
    expect(find.textContaining('/77'), findsNothing);
    handle.dispose();
  });

  // Todo 505, finding 1: a link row reads its label from linkPreviewDisplay
  // rather than re-deriving it.
  testWidgets('a link row is labelled by linkPreviewDisplay', (tester) async {
    final handle = tester.ensureSemantics();
    const bare = LinkPreviewBlock(url: 'https://example.org/g');
    await _pump(tester, const [_a, _link, bare]);

    expect(
      find.bySemanticsLabel(linkPreviewDisplay(_link)!.label),
      findsOneWidget,
    );
    // The title IS the address: the display's label says it once.
    expect(linkPreviewDisplay(bare)!.label, 'https://example.org/…');
    expect(find.bySemanticsLabel('https://example.org/…'), findsOneWidget);
    handle.dispose();
  });
}
