import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';

void main() {
  test('parses a category with forums and links', () {
    final c = ForumCategory.fromJson({
      'id': 17,
      'title': 'Community',
      'slug': 'community',
      'description': '',
      'icon': '🌱',
      'colour': 'bloom',
      'has_unread': true,
      'forums': [
        {
          'id': 15,
          'title': 'Show & tell',
          'slug': 'show-tell',
          'description': 'd',
          'topic_count': 3,
          'post_count': 9,
          'last_post_at': '2026-11-17T10:00:00Z',
          'has_unread': true,
          'is_locked': false,
          'is_closed': true,
          'can_post': false,
          'icon': '📷',
          'colour': 'sage',
        },
      ],
      'links': [
        {
          'id': 20,
          'title': 'Seed swap',
          'slug': 'seed-swap',
          'description': '',
          'link_url': 'https://example.org',
          'track_clicks': true,
          'click_count': 4,
        },
      ],
    });
    expect(c.forums.single.lastPostAt, DateTime.utc(2026, 11, 17, 10));
    expect(c.forums.single.isClosed, isTrue);
    expect(c.links.single.clickCount, 4);
  });

  test('missing and null fields take defaults', () {
    final c = ForumCategory.fromJson({'id': 1});
    expect(c.title, '');
    expect(c.forums, isEmpty);
    expect(c.links, isEmpty);
    final b = ForumBoard.fromJson({
      'id': 2,
      'last_post_at': null,
      'icon': null,
    });
    expect(b.icon, '');
    expect(b.lastPostAt, isNull);
    expect(b.isLocked, isFalse);
  });

  test('rows that are not JSON objects are skipped', () {
    final c = ForumCategory.fromJson({
      'id': 1,
      'forums': [1, 'x', null],
    });
    expect(c.forums, isEmpty);
  });
}
