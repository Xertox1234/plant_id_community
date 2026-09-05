import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/forum_body_block.dart';

void main() {
  group('parseForumBody', () {
    test('parses an embed envelope, and a bare URL from an older client', () {
      final blocks = parseForumBody([
        {
          'type': 'embed',
          'value': {
            'url': 'https://youtu.be/dQw4w9WgXcQ',
            'provider_name': 'YouTube',
            'title': 'Repotting',
            'thumbnail_url': 'https://i/t.jpg',
            'embed_url': 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
          },
        },
        {'type': 'embed', 'value': 'https://vimeo.com/148751763'},
      ]);

      expect(blocks[0], isA<EmbedBlock>());
      final first = blocks[0] as EmbedBlock;
      expect(first.url, 'https://youtu.be/dQw4w9WgXcQ');
      expect(first.providerName, 'YouTube');
      expect(first.title, 'Repotting');
      expect(first.thumbnailUrl, 'https://i/t.jpg');
      final second = blocks[1] as EmbedBlock;
      expect(second.url, 'https://vimeo.com/148751763');
      expect(second.title, '');
    });

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
        {'type': 'gallery', 'value': 'whatever'},
      ]);
      expect(blocks.single, isA<UnknownBlock>());
      expect((blocks.single as UnknownBlock).type, 'gallery');
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

    test('post_quote: the read envelope, available and gone (todo 342)', () {
      final blocks = parseForumBody([
        {
          'type': 'post_quote',
          'value': {
            'text': 'Water it less.',
            'post_id': 42,
            'available': true,
            'topic_id': 7,
            'author': {
              'username': 'bob',
              'display_name': 'Bob B',
              'avatar': null,
              'trust_level': 2,
            },
          },
        },
        {
          'type': 'post_quote',
          'value': {
            'text': 'Gone now',
            'post_id': 43,
            'available': false,
            'topic_id': null,
            'author': null,
          },
        },
        {'type': 'post_quote', 'value': null},
      ]);

      final live = blocks[0] as PostQuoteBlock;
      expect(live.text, 'Water it less.');
      expect(live.postId, 42);
      expect(live.available, isTrue);
      expect(live.topicId, 7);
      expect(live.author?.name, 'Bob B');
      expect(live.author?.trustLevel, 2);

      final gone = blocks[1] as PostQuoteBlock;
      expect(gone.text, 'Gone now');
      expect(gone.postId, 43);
      expect(gone.available, isFalse);
      expect(gone.topicId, isNull);
      expect(gone.author, isNull);

      // A malformed envelope is a quote with nothing in it, never a crash.
      final blank = blocks[2] as PostQuoteBlock;
      expect(blank.text, '');
      expect(blank.postId, isNull);
      expect(blank.available, isFalse);
    });

    test('post_quote: is_blocked / is_muted parse, and default to false when '
        'absent (older envelopes, anonymous viewers)', () {
      final blocks = parseForumBody([
        {
          'type': 'post_quote',
          'value': {
            'text': 'x',
            'post_id': 1,
            'available': true,
            'is_blocked': true,
            'is_muted': true,
          },
        },
        {
          'type': 'post_quote',
          'value': {'text': 'y', 'post_id': 2, 'available': true},
        },
        {
          'type': 'post_quote',
          'value': {
            'text': 'z',
            'post_id': 3,
            'available': true,
            'is_blocked': null,
            'is_muted': false,
          },
        },
      ]);

      final both = blocks[0] as PostQuoteBlock;
      expect(both.isBlocked, isTrue);
      expect(both.isMuted, isTrue);

      final absent = blocks[1] as PostQuoteBlock;
      expect(absent.isBlocked, isFalse);
      expect(absent.isMuted, isFalse);

      final nulled = blocks[2] as PostQuoteBlock;
      expect(nulled.isBlocked, isFalse);
      expect(nulled.isMuted, isFalse);
    });
  });

  group('buildPostQuoteBlockBody (todo 342)', () {
    test('emits the write shape: the quoted id and verbatim plain text', () {
      expect(buildPostQuoteBlockBody(42, '  <b>raw</b> & "quoted"  '), {
        'type': 'post_quote',
        'value': {'post': 42, 'text': '<b>raw</b> & "quoted"'},
      });
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

  group('isSingleEditableParagraph (todo 292)', () {
    test('true for exactly one paragraph block', () {
      expect(isSingleEditableParagraph(const [ParagraphBlock('hi')]), isTrue);
    });

    test('false for multiple blocks, even all paragraphs', () {
      expect(
        isSingleEditableParagraph(const [
          ParagraphBlock('one'),
          ParagraphBlock('two'),
        ]),
        isFalse,
      );
    });

    test('false for a single non-paragraph block', () {
      expect(isSingleEditableParagraph(const [HeadingBlock('h')]), isFalse);
      expect(
        isSingleEditableParagraph(const [
          ForumImageBlock(id: 1, url: 'x', alt: ''),
        ]),
        isFalse,
      );
    });

    test('false for an empty body', () {
      expect(isSingleEditableParagraph(const []), isFalse);
    });

    test(
      'true for mobile-composer-shaped HTML: escaped text plus a real <br> tag',
      () {
        // Exactly buildParagraphBody's own output shape.
        expect(
          isSingleEditableParagraph(const [
            ParagraphBlock('a &lt; b &amp; c<br>line2'),
          ]),
          isTrue,
        );
        // A user who literally typed the text "<br>" gets it fully escaped
        // to &lt;br&gt; (no raw angle brackets at all) — still safe, still
        // true; plainTextFromParagraphHtml correctly reconstructs it as the
        // literal text "<br>", not a newline.
        expect(
          isSingleEditableParagraph(const [
            ParagraphBlock('a &lt; b &amp; c&lt;br&gt;line2'),
          ]),
          isTrue,
        );
      },
    );

    test(
      'false for a single paragraph carrying REAL markup — a web-authored '
      'post using only inline marks (bold/italic/link) also collapses to '
      'one paragraph block, but block SHAPE alone cannot tell it apart from '
      'mobile-composer output (code review — a real, reproduced gap: '
      'without this check the markup silently renders as literal escaped '
      'tag text in the edit field with no warning, and saving burns it in)',
      () {
        expect(
          isSingleEditableParagraph(const [
            ParagraphBlock('Check out <strong>this</strong> plant'),
          ]),
          isFalse,
        );
        expect(
          isSingleEditableParagraph(const [
            ParagraphBlock('<a href="https://example.com">a link</a>'),
          ]),
          isFalse,
        );
      },
    );
  });

  group('plainTextFromParagraphHtml (todo 292)', () {
    test('round-trips through buildParagraphBody for plain text', () {
      const original = 'line1\nline2 & <tag> "quoted" it\'s';
      final html = buildParagraphBody(original).single['value'] as String;
      expect(plainTextFromParagraphHtml(html), original);
    });

    test('reverses <br> back to newlines', () {
      expect(plainTextFromParagraphHtml('a<br>b'), 'a\nb');
    });

    test('reverses entity escaping without double-unescaping &amp;', () {
      // The literal text "&lt;" typed by a user becomes "&amp;lt;" on write
      // (the `&` escapes to `&amp;`, and `_escapeHtml` never re-scans its
      // own output). Reversing must yield the original "&lt;" back, not the
      // wrong "<" a naive single-pass unescape (or resolving &amp; first)
      // would produce.
      expect(plainTextFromParagraphHtml('&amp;lt;'), '&lt;');
    });
  });
}
