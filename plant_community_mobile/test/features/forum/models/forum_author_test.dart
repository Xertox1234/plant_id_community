import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

void main() {
  group('ForumAuthor.fromJson title', () {
    test('parses a non-empty title', () {
      final author = ForumAuthor.fromJson({
        'username': 'alice',
        'display_name': 'Alice',
        'avatar': null,
        'trust_level': 2,
        'title': 'Plant Whisperer',
      });

      expect(author.title, 'Plant Whisperer');
    });

    test('defaults to empty string when title is absent', () {
      final author = ForumAuthor.fromJson({
        'username': 'alice',
        'display_name': 'Alice',
        'avatar': null,
        'trust_level': 2,
      });

      expect(author.title, '');
    });

    test(
      'the deleted-author sentinel sends an empty title, matching the default',
      () {
        final author = ForumAuthor.fromJson({
          'username': '[deleted]',
          'display_name': '[deleted]',
          'avatar': null,
          'trust_level': null,
          'title': '',
        });

        expect(author.title, '');
      },
    );
  });
}
