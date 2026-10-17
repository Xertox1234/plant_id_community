// The Dart video matcher and the composer's card-link rule (todo 654).
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/utils/forum_embed_url.dart';

void main() {
  group('forumVideoUrlOf agrees with the web providerVideoUrl', () {
    // The SAME table file web/src/utils/forumBody.test.ts reads, so the two
    // matchers cannot drift apart.
    final table =
        jsonDecode(
              File(
                'test/features/forum/support/video_url_cases.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>;
    final cases = (table['cases'] as List<dynamic>).cast<List<dynamic>>();

    test('the table is not empty', () => expect(cases.length, greaterThan(10)));

    for (final entry in cases) {
      final text = entry[0] as String;
      final expected = entry[1] as String?;
      test('${jsonEncode(text)} embeds as ${jsonEncode(expected)}', () {
        expect(forumVideoUrlOf(text), expected);
      });
    }
  });

  group('forumComposerCardLinks mirrors the server split (todo 655)', () {
    test('a link on its own line between text is a card link', () {
      expect(forumComposerCardLinks('Intro\nhttps://example.com/a\nOutro'), [
        'https://example.com/a',
      ]);
    });

    test('a link in prose, a list item, inline code or a [text](url) link '
        'is not', () {
      expect(
        forumComposerCardLinks(
          [
            'Read https://example.com/a first.',
            '- https://example.com/b',
            '`https://example.com/c`',
            '[my page](https://example.com/d)',
            'not a link',
          ].join('\n'),
        ),
        isEmpty,
      );
    });

    test('a video line is not a card link and is not counted', () {
      expect(
        forumComposerCardLinks(
          'https://youtu.be/dQw4w9WgXcQ\nhttps://example.com/a',
        ),
        ['https://example.com/a'],
      );
    });

    test('links are distinct, in order, trimmed of sentence punctuation, and '
        'capped at the server ceiling', () {
      final lines = [
        'https://site0.example/.',
        'https://site0.example/',
        for (var n = 1; n < 8; n++) 'https://site$n.example/',
      ];
      final links = forumComposerCardLinks(lines.join('\n'));
      expect(links, [
        for (var n = 0; n < kForumMaxLinkCardsPerPost; n++)
          'https://site$n.example/',
      ]);
      expect(kForumMaxLinkCardsPerPost, 5);
    });

    test('a URL the server could never card is not counted', () {
      expect(
        forumComposerCardLinks('mailto:a@b.example\nhttps://u:p@x.example/'),
        isEmpty,
      );
    });
  });
}
