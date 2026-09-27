import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/blog/models/blog_post.dart';
import 'package:plant_community_mobile/features/blog/providers/blog_providers.dart';
import 'package:plant_community_mobile/features/blog/screens/blog_list_screen.dart';
import 'package:plant_community_mobile/features/blog/screens/blog_post_screen.dart';
import 'package:plant_community_mobile/features/blog/services/blog_api.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';

import 'support/fake_blog_api.dart';

Widget _wrap(Widget child, FakeBlogApi api, {List<String>? opened}) =>
    ProviderScope(
      overrides: [
        blogApiProvider.overrideWithValue(api),
        forumLinkLauncherProvider.overrideWithValue((uri) async {
          opened?.add(uri.toString());
          return true;
        }),
      ],
      child: MaterialApp(home: child),
    );

List<BlogPostSummary> _rows(int from, int count) => [
  for (var i = from; i < from + count; i++) summary(i),
];

void main() {
  group('BlogPosts provider', () {
    test('loadMore asks for the next offset and appends', () async {
      final api = FakeBlogApi(
        pages: [
          BlogPostPage(items: _rows(0, blogPageSize), totalCount: 25),
          BlogPostPage(items: _rows(blogPageSize, 5), totalCount: 25),
        ],
      );
      final container = ProviderContainer(
        overrides: [blogApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final sub = container.listen(blogPostsProvider('care-guide'), (_, _) {});
      addTearDown(sub.close);

      final first = await container.read(
        blogPostsProvider('care-guide').future,
      );
      expect(first.hasMore, isTrue);

      await container.read(blogPostsProvider('care-guide').notifier).loadMore();

      expect(api.calls, [('care-guide', 0), ('care-guide', blogPageSize)]);
      final feed = container.read(blogPostsProvider('care-guide')).value!;
      expect(feed.items, hasLength(25));
      expect(feed.hasMore, isFalse);
    });

    test('a row repeated across pages is kept once, and a short page ends '
        'the list even when total_count says more', () async {
      final api = FakeBlogApi(
        pages: [
          BlogPostPage(items: _rows(0, blogPageSize), totalCount: 100),
          // A post published between the two requests shifts the window by
          // one: the last row of page 1 comes back as the first of page 2.
          BlogPostPage(items: _rows(blogPageSize - 1, 3), totalCount: 100),
        ],
      );
      final container = ProviderContainer(
        overrides: [blogApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final sub = container.listen(blogPostsProvider(null), (_, _) {});
      addTearDown(sub.close);
      await container.read(blogPostsProvider(null).future);

      await container.read(blogPostsProvider(null).notifier).loadMore();

      final feed = container.read(blogPostsProvider(null)).value!;
      expect(feed.items.map((p) => p.id).toSet(), hasLength(feed.items.length));
      expect(feed.items, hasLength(blogPageSize + 2));
      expect(feed.hasMore, isFalse);
    });
  });

  test('after a page with a duplicate, the next request asks for the SERVER '
      'offset, not the deduped length (PR #856 review)', () async {
    // The server caches list pages by offset // limit: offset 39 is served
    // the cached page at 20, all duplicates, and Load more never advances.
    final api = FakeBlogApi(
      pages: [
        BlogPostPage(items: _rows(0, blogPageSize), totalCount: 100),
        BlogPostPage(
          items: _rows(blogPageSize - 1, blogPageSize),
          totalCount: 100,
        ),
        BlogPostPage(
          items: _rows(2 * blogPageSize, blogPageSize),
          totalCount: 100,
        ),
      ],
    );
    final container = ProviderContainer(
      overrides: [blogApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    final sub = container.listen(blogPostsProvider(null), (_, _) {});
    addTearDown(sub.close);
    await container.read(blogPostsProvider(null).future);

    final notifier = container.read(blogPostsProvider(null).notifier);
    await notifier.loadMore();
    await notifier.loadMore();

    expect(api.calls.map((c) => c.$2), [0, blogPageSize, 2 * blogPageSize]);
    final feed = container.read(blogPostsProvider(null)).value!;
    expect(feed.items, hasLength(3 * blogPageSize - 1));
    expect(feed.hasMore, isTrue);
  });

  group('BlogListScreen', () {
    testWidgets('lists posts for its tag and offers Load more', (tester) async {
      final api = FakeBlogApi(
        pages: [BlogPostPage(items: _rows(1, blogPageSize), totalCount: 30)],
      );
      await tester.pumpWidget(
        _wrap(const BlogListScreen(tag: 'care-guide', title: 'Care'), api),
      );
      await tester.pumpAndSettle();

      expect(api.calls.single, ('care-guide', 0));
      expect(find.text('Care'), findsOneWidget);
      expect(find.text('Post 1'), findsOneWidget);
      expect(find.text('Excerpt 2'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Load more'), 400);
      expect(find.text('Load more'), findsOneWidget);
    });

    testWidgets('an empty list says so', (tester) async {
      await tester.pumpWidget(_wrap(const BlogListScreen(), FakeBlogApi()));
      await tester.pumpAndSettle();
      expect(find.text('No posts yet.'), findsOneWidget);
      expect(find.text('Load more'), findsNothing);
    });

    testWidgets('a failed load offers Retry', (tester) async {
      final api = FakeBlogApi()..postsError = Exception('offline');
      await tester.pumpWidget(_wrap(const BlogListScreen(), api));
      await tester.pumpAndSettle();
      expect(find.text('Could not load posts.'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });

  group('BlogPostScreen', () {
    const post = BlogPost(
      id: 1,
      slug: 'pothos',
      title: 'Pothos Care Guide',
      introduction: '<p>Easy and forgiving.</p>',
      authorName: 'Editor',
      readingTime: 4,
      blocks: [
        BlogHeadingBlock('Watering'),
        BlogParagraphBlock(
          '<p>See <a href="https://example.com/soil">soil</a> and '
          '<a href="/blog/snake-plant/">snake plants</a>.</p>',
        ),
        BlogPlantSpotlightBlock(
          plantName: 'Pothos',
          scientificName: 'Epipremnum aureum',
          careDifficulty: 'easy',
          imageCredit: 'Photo by Jane on Unsplash',
          imageCreditUrl: 'https://unsplash.com/@jane',
          image: BlogImage(url: 'https://cdn.example.com/p.webp'),
        ),
      ],
    );

    testWidgets('renders the intro, headings, text and the spotlight with its '
        'photo credit', (tester) async {
      final api = FakeBlogApi(posts: {'pothos': post});
      await tester.pumpWidget(_wrap(const BlogPostScreen(slug: 'pothos'), api));
      await tester.pump();
      await tester.pump();

      expect(find.text('Pothos Care Guide'), findsWidgets);
      expect(find.textContaining('Easy and forgiving.'), findsOneWidget);
      expect(find.text('Watering'), findsOneWidget);
      expect(find.text('Epipremnum aureum'), findsOneWidget);
      expect(find.text('Care difficulty: Easy'), findsOneWidget);
      // Unsplash requires the credit wherever the photo is shown (todo 376).
      expect(find.text('Photo by Jane on Unsplash'), findsOneWidget);
      expect(find.textContaining('Editor'), findsOneWidget);
    });

    testWidgets('an external link opens in the in-app browser', (tester) async {
      final opened = <String>[];
      final api = FakeBlogApi(posts: {'pothos': post});
      await tester.pumpWidget(
        _wrap(const BlogPostScreen(slug: 'pothos'), api, opened: opened),
      );
      await tester.pump();
      await tester.pump();

      await tester.tapOnText(find.textRange.ofSubstring('soil'));
      await tester.pump();

      expect(opened, ['https://example.com/soil']);
    });

    testWidgets('the photo credit link opens its source', (tester) async {
      final opened = <String>[];
      final api = FakeBlogApi(posts: {'pothos': post});
      await tester.pumpWidget(
        _wrap(const BlogPostScreen(slug: 'pothos'), api, opened: opened),
      );
      await tester.pump();
      await tester.pump();

      await tester.ensureVisible(find.text('Photo by Jane on Unsplash'));
      await tester.pump();
      await tester.tap(find.text('Photo by Jane on Unsplash'));
      await tester.pump();

      expect(opened, ['https://unsplash.com/@jane']);
    });

    testWidgets('a missing post says it is gone, not a generic error', (
      tester,
    ) async {
      await tester.pumpWidget(
        _wrap(const BlogPostScreen(slug: 'gone'), FakeBlogApi()),
      );
      await tester.pump();
      await tester.pump();
      expect(find.text('This post is no longer available.'), findsOneWidget);
    });
  });
}
