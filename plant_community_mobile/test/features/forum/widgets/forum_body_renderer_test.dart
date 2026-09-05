import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/forum_body_block.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_body_renderer.dart';

Future<void> _pump(WidgetTester tester, List<ForumBodyBlock> blocks) {
  return tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(child: ForumBodyRenderer(blocks)),
      ),
    ),
  );
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
}
