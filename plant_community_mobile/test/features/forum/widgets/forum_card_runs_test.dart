import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
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
/// shows the bare provider. Rows and cards share their label format.
int _fullEmbedCards() => find.textContaining('Watch on ').evaluate().length;

void main() {
  testWidgets('three consecutive embeds: one full card, then two rows', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, const [_a, _b, _c]);

    expect(_fullEmbedCards(), 1);
    expect(find.text('Watch on YouTube'), findsOneWidget);
    // The rows: provider as the bare second line, labelled like a card.
    expect(find.text('Vimeo'), findsOneWidget);
    expect(find.bySemanticsLabel('YouTube video: Bravo'), findsOneWidget);
    expect(find.bySemanticsLabel('Vimeo video: Charlie'), findsOneWidget);
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
        ('YouTube video: Bravo', 'https://youtu.be/b'),
        ('Vimeo video: Charlie', 'https://vimeo.com/3'),
      ]) {
        final node = tester.getSemantics(find.bySemanticsLabel(label));
        final data = node.getSemanticsData();
        expect(data.hasAction(SemanticsAction.tap), isTrue);
        expect(data.flagsCollection.isButton, isTrue);
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
      find.bySemanticsLabel('Link: Delta guide, https://example.org/…'),
    );
    final data = node.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    expect(data.hasAction(SemanticsAction.longPress), isTrue);
    expect(data.customSemanticsActionIds, hasLength(2));

    await tester.tap(find.text('Delta guide'));
    expect(opened, ['https://example.org/guide']);
    handle.dispose();
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
        find.bySemanticsLabel('Link: Watch this, https://evil.example/…'),
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
}
