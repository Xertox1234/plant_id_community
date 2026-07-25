import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/forum_body_block.dart';

void main() {
  group('parseForumBody', () {
    test('parses all five block types', () {
      final blocks = parseForumBody([
        {'type': 'heading', 'value': 'A heading', 'id': '1'},
        {'type': 'paragraph', 'value': '<p>Hello <strong>world</strong></p>'},
        {'type': 'quote', 'value': 'A wise quote'},
        {
          'type': 'code',
          'value': {'language': 'dart', 'code': 'void main() {}'},
        },
        {
          'type': 'image',
          'value': {
            'id': 7,
            'url': 'https://example.com/i.png',
            'alt': 'pic',
            'width': 100,
            'height': 80,
          },
        },
      ]);

      expect(blocks, hasLength(5));
      expect(blocks[0], isA<HeadingBlock>());
      expect((blocks[0] as HeadingBlock).text, 'A heading');
      expect(blocks[1], isA<ParagraphBlock>());
      expect((blocks[1] as ParagraphBlock).html, contains('<strong>'));
      expect(blocks[2], isA<QuoteBlock>());
      expect((blocks[2] as QuoteBlock).text, 'A wise quote');
      expect(blocks[3], isA<CodeBlock>());
      expect((blocks[3] as CodeBlock).language, 'dart');
      expect((blocks[3] as CodeBlock).code, 'void main() {}');
      expect(blocks[4], isA<ForumImageBlock>());
      expect((blocks[4] as ForumImageBlock).id, 7);
    });

    test('image with null value → DeletedImageBlock', () {
      final blocks = parseForumBody([
        {'type': 'image', 'value': null, 'id': '3'},
      ]);
      expect(blocks.single, isA<DeletedImageBlock>());
    });

    test('unknown block type → UnknownBlock preserving the type', () {
      final blocks = parseForumBody([
        {'type': 'embed', 'value': 'whatever'},
      ]);
      expect(blocks.single, isA<UnknownBlock>());
      expect((blocks.single as UnknownBlock).type, 'embed');
    });

    test('quote object form (web shape) extracts text', () {
      final blocks = parseForumBody([
        {
          'type': 'quote',
          'value': {'quote_text': 'from object', 'attribution': 'x'},
        },
      ]);
      expect((blocks.single as QuoteBlock).text, 'from object');
    });

    test('non-list / malformed input yields empty list', () {
      expect(parseForumBody(null), isEmpty);
      expect(parseForumBody('nope'), isEmpty);
      expect(parseForumBody([42, 'x']), isEmpty);
    });
  });

  group('buildParagraphBody', () {
    test('wraps plain text as a single escaped paragraph block', () {
      final body = buildParagraphBody('a < b & c');
      expect(body, hasLength(1));
      expect(body.single['type'], 'paragraph');
      expect(body.single['value'], 'a &lt; b &amp; c');
    });

    test('maps newlines to <br>', () {
      final body = buildParagraphBody('line1\nline2');
      expect(body.single['value'], 'line1<br>line2');
    });

    test('blank input yields an empty body', () {
      expect(buildParagraphBody('   '), isEmpty);
    });
  });
}
