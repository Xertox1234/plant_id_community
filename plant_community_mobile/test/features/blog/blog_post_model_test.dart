import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/blog/models/blog_post.dart';

void main() {
  group('BlogPostPage.fromJson (the LIST shape)', () {
    test('parses rows, total_count and the thumbnail rendition', () {
      final page = BlogPostPage.fromJson({
        'meta': {'total_count': 42},
        'items': [
          {
            'id': 7,
            'slug': 'pothos-care-guide',
            'title': 'Pothos Care Guide',
            'excerpt': 'Easy and forgiving.',
            'author': {'username': 'ed', 'display_name': 'Editor'},
            'publish_date': '2026-09-27',
            'reading_time': 4,
            'tags': ['care-guide'],
            'featured_image_thumb': {
              'url': '/media/images/p.fill-300x200.jpg',
              'full_url': 'https://api.example.com/media/images/p.jpg',
              'width': 300,
              'height': 200,
              'alt': 'A pothos',
            },
          },
        ],
      });

      expect(page.totalCount, 42);
      final post = page.items.single;
      expect(post.slug, 'pothos-care-guide');
      expect(post.authorName, 'Editor');
      expect(post.publishDate, DateTime(2026, 9, 27));
      expect(post.readingTime, 4);
      expect(post.tags, ['care-guide']);
      // full_url wins over the relative url.
      expect(post.thumbnail!.url, 'https://api.example.com/media/images/p.jpg');
      expect(post.thumbnail!.alt, 'A pothos');
    });

    test('drops a row with no slug: it could not be opened', () {
      final page = BlogPostPage.fromJson({
        'meta': {'total_count': 2},
        'items': [
          {'id': 1, 'title': 'No slug'},
          {'id': 2, 'slug': 'ok', 'title': 'Ok'},
        ],
      });
      expect(page.items.map((p) => p.slug), ['ok']);
      // The dropped row still counts toward the server offset.
      expect(page.rowCount, 2);
    });

    test('tolerates wrong types and missing fields', () {
      final page = BlogPostPage.fromJson({
        'items': [
          {
            'id': '3',
            'slug': 'x',
            'title': null,
            'author': 'nope',
            'tags': 'nope',
            'reading_time': '4',
            'featured_image_thumb': {'url': ''},
          },
        ],
      });
      final post = page.items.single;
      expect(post.id, 0);
      expect(post.title, '');
      expect(post.authorName, '');
      expect(post.tags, isEmpty);
      expect(post.readingTime, isNull);
      expect(post.thumbnail, isNull);
      // No meta: fall back to the rows we have.
      expect(page.totalCount, 1);
    });
  });

  group('BlogPost.fromJson (the DETAIL shape)', () {
    test('parses every block type and skips unknown or empty ones', () {
      final post = BlogPost.fromJson({
        'id': 9,
        'slug': 's',
        'title': 'T',
        'introduction': '<p>Intro</p>',
        'content_blocks': [
          {'type': 'heading', 'value': 'Watering'},
          {'type': 'paragraph', 'value': '<p>Soak, then drain.</p>'},
          {
            'type': 'quote',
            'value': {'quote_text': '<p>Less is more.</p>', 'attribution': 'A'},
          },
          {'type': 'quote', 'value': 'Legacy string quote'},
          {
            'type': 'code',
            'value': {'language': 'bash', 'code': 'echo hi'},
          },
          {
            'type': 'plant_spotlight',
            'value': {
              'plant_name': 'Pothos',
              'scientific_name': 'Epipremnum aureum',
              'description': '<p>Trails.</p>',
              'care_difficulty': 'easy',
              'image': {'url': 'https://cdn.example.com/p.webp', 'alt': 'P'},
              'image_credit': ' Photo by Jane on Unsplash ',
              'image_credit_url': 'https://unsplash.com/@jane',
            },
          },
          {
            'type': 'call_to_action',
            'value': {
              'cta_title': 'Join',
              'cta_description': '<p>Come in.</p>',
              'button_text': 'Go',
              'button_url': 'https://example.com',
            },
          },
          {'type': 'video_embed', 'value': 'https://example.com/v'},
          {'type': 'heading', 'value': ''},
          {'type': 'paragraph', 'value': null},
          {
            'type': 'plant_spotlight',
            'value': {'plant_name': ''},
          },
          'not a map',
        ],
      });

      expect(post.introduction, '<p>Intro</p>');
      expect(post.blocks.map((b) => b.runtimeType), [
        BlogHeadingBlock,
        BlogParagraphBlock,
        BlogQuoteBlock,
        BlogQuoteBlock,
        BlogCodeBlock,
        BlogPlantSpotlightBlock,
        BlogCallToActionBlock,
      ]);
      final quote = post.blocks[2] as BlogQuoteBlock;
      expect(quote.attribution, 'A');
      expect((post.blocks[3] as BlogQuoteBlock).html, 'Legacy string quote');
      final spotlight = post.blocks[5] as BlogPlantSpotlightBlock;
      expect(spotlight.image!.url, 'https://cdn.example.com/p.webp');
      expect(spotlight.imageCredit, 'Photo by Jane on Unsplash');
      expect(spotlight.imageCreditUrl, 'https://unsplash.com/@jane');
    });
  });

  group('resolveBlogMediaUrl', () {
    const base = 'https://api.houseplant-md.com/api/v1';

    test('a relative path goes onto the API origin, not /api/v1', () {
      expect(
        resolveBlogMediaUrl('/media/images/a.jpg', base),
        'https://api.houseplant-md.com/media/images/a.jpg',
      );
    });

    test('an absolute /media/ URL is re-based onto the API origin', () {
      // The host a /media/ URL names has been wrong before (todo 308).
      expect(
        resolveBlogMediaUrl('http://localhost/media/images/a.jpg?v=2', base),
        'https://api.houseplant-md.com/media/images/a.jpg?v=2',
      );
    });

    test('an R2/CDN URL passes through unchanged', () {
      const cdn = 'https://media.houseplant-md.com/images/a.fill-800x400.webp';
      expect(resolveBlogMediaUrl(cdn, base), cdn);
      const lookalike = 'https://cdn.example.com/social-media/cover.webp';
      expect(resolveBlogMediaUrl(lookalike, base), lookalike);
    });

    test('keeps a local dev port', () {
      expect(
        resolveBlogMediaUrl('/media/a.jpg', 'http://localhost:8000/api/v1'),
        'http://localhost:8000/media/a.jpg',
      );
    });
  });
}
