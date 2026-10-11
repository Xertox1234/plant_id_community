import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:plant_community_mobile/features/blog/models/blog_post.dart';
import 'package:plant_community_mobile/features/blog/providers/blog_providers.dart';
import 'package:plant_community_mobile/features/blog/screens/blog_list_screen.dart';
import 'package:plant_community_mobile/features/blog/screens/blog_post_screen.dart';
import 'package:plant_community_mobile/features/blog/services/blog_api.dart';
import 'package:plant_community_mobile/features/blog/widgets/blog_block_view.dart';
import 'package:plant_community_mobile/features/forum/services/forum_link_launcher.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_html_text.dart';
import 'package:plant_community_mobile/services/api_service.dart';

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

  group('todo 460', () {
    /// The production route names under a minimal router, so a link's push
    /// and a Back can be asserted by location.
    Future<GoRouter> pumpRouted(
      WidgetTester tester,
      FakeBlogApi api, {
      String initial = '/blog/pothos',
      List<String>? opened,
    }) async {
      final router = GoRouter(
        initialLocation: initial,
        routes: [
          GoRoute(
            path: '/blog',
            name: 'blog',
            builder: (context, state) => const BlogListScreen(),
            routes: [
              GoRoute(
                path: ':slug',
                name: 'blogPost',
                builder: (context, state) => BlogPostScreen(
                  slug: state.pathParameters['slug']!,
                  initialTitle: state.extra is String
                      ? state.extra as String
                      : null,
                ),
              ),
            ],
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            blogApiProvider.overrideWithValue(api),
            forumLinkLauncherProvider.overrideWithValue((uri) async {
              opened?.add(uri.toString());
              return true;
            }),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pump();
      await tester.pump();
      return router;
    }

    /// The top route's location: `uri` names the base of a pushed stack.
    String location(GoRouter router) =>
        router.routerDelegate.currentConfiguration.last.matchedLocation;

    BlogPost postWith(String slug, String html, {String title = 'Pothos'}) =>
        BlogPost(
          id: 1,
          slug: slug,
          title: title,
          blocks: [BlogParagraphBlock(html)],
        );

    testWidgets('pull to refresh keeps spinning until the reload is back', (
      tester,
    ) async {
      final api = FakeBlogApi(
        pages: [
          BlogPostPage(items: _rows(1, 2), totalCount: 2),
          BlogPostPage(items: _rows(1, 3), totalCount: 3),
        ],
      );
      await tester.pumpWidget(_wrap(const BlogListScreen(), api));
      await tester.pump();
      await tester.pump();
      final gate = Completer<void>();
      api.listGate = gate;

      var done = false;
      final refresh = tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh()
          .then((_) => done = true);
      await tester.pump();
      expect(api.calls, hasLength(2), reason: 'the refresh did not reload');
      expect(done, isFalse, reason: 'onRefresh returned before the data');

      gate.complete();
      await refresh;
      await tester.pump();
      expect(done, isTrue);
      expect(find.text('Post 3'), findsOneWidget);
    });

    testWidgets('a refresh that fails does not throw out of the indicator', (
      tester,
    ) async {
      final api = FakeBlogApi(
        pages: [BlogPostPage(items: _rows(1, 2), totalCount: 2)],
      );
      await tester.pumpWidget(_wrap(const BlogListScreen(), api));
      await tester.pump();
      await tester.pump();
      api.postsError = ApiException('gone', statusCode: 404);

      await tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh();
      await tester.pump();
      expect(find.text('Could not load posts.'), findsOneWidget);
    });

    test('a page that lands after a refresh is dropped, not appended to the '
        'new feed', () async {
      final api = FakeBlogApi(
        pages: [
          BlogPostPage(items: _rows(0, blogPageSize), totalCount: 50),
          BlogPostPage(
            items: _rows(blogPageSize, blogPageSize),
            totalCount: 50,
          ),
          BlogPostPage(items: _rows(100, blogPageSize), totalCount: 50),
        ],
      );
      final container = ProviderContainer(
        overrides: [blogApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final sub = container.listen(blogPostsProvider(null), (_, _) {});
      addTearDown(sub.close);
      await container.read(blogPostsProvider(null).future);
      final gate = Completer<void>();
      api.moreGate = gate;

      final more = container.read(blogPostsProvider(null).notifier).loadMore();
      await Future<void>.delayed(Duration.zero);
      // The refresh lands while the page is still in flight.
      await container.refresh(blogPostsProvider(null).future);
      gate.complete();

      await expectLater(more, completes);
      final feed = container.read(blogPostsProvider(null)).value!;
      expect(feed.items.first.id, 100, reason: 'the fresh build is kept');
      expect(feed.items, hasLength(blogPageSize));
      expect(feed.nextOffset, blogPageSize);
      expect(feed.isLoadingMore, isFalse);
    });

    test('loadMore after the feed is disposed neither throws nor reports a '
        'failure', () async {
      for (final fail in [false, true]) {
        final api = FakeBlogApi(
          pages: [
            BlogPostPage(items: _rows(0, blogPageSize), totalCount: 50),
            BlogPostPage(items: _rows(blogPageSize, 5), totalCount: 50),
          ],
        );
        final container = ProviderContainer(
          overrides: [blogApiProvider.overrideWithValue(api)],
        );
        addTearDown(container.dispose);
        final sub = container.listen(blogPostsProvider('t'), (_, _) {});
        await container.read(blogPostsProvider('t').future);
        final gate = Completer<void>();
        api.moreGate = gate;

        final more = container.read(blogPostsProvider('t').notifier).loadMore();
        await Future<void>.delayed(Duration.zero);
        sub.close(); // the screen is left: the autoDispose feed goes
        await Future<void>.delayed(Duration.zero);
        expect(container.exists(blogPostsProvider('t')), isFalse);
        if (fail) api.postsError = ApiException('offline');
        gate.complete();

        await expectLater(more, completes, reason: 'fail=$fail');
      }
    });

    testWidgets('a failed load fails at once on a 4xx and Retry reloads', (
      tester,
    ) async {
      // One page per call: the first call fails, the Retry gets the second.
      final page = BlogPostPage(items: _rows(1, 1), totalCount: 1);
      final api = FakeBlogApi(pages: [page, page])
        ..postsError = ApiException('bad', statusCode: 400);
      await tester.pumpWidget(_wrap(const BlogListScreen(), api));
      await tester.pump();
      await tester.pump();
      expect(find.text('Could not load posts.'), findsOneWidget);
      expect(api.calls, hasLength(1), reason: 'a 4xx was retried');

      api.postsError = null;
      await tester.tap(find.text('Retry'));
      await tester.pump();
      await tester.pump();

      expect(find.text('Post 1'), findsOneWidget);
      expect(find.text('Could not load posts.'), findsNothing);
    });

    testWidgets("a post's Retry reloads it", (tester) async {
      final api = FakeBlogApi();
      await tester.pumpWidget(_wrap(const BlogPostScreen(slug: 'late'), api));
      await tester.pump();
      await tester.pump();
      expect(find.text('This post is no longer available.'), findsOneWidget);

      api.posts['late'] = const BlogPost(
        id: 9,
        slug: 'late',
        title: 'Published late',
      );
      await tester.tap(find.text('Retry'));
      await tester.pump();
      await tester.pump();

      expect(find.text('Published late'), findsWidgets);
    });

    testWidgets('the list is called "Plant Journal", like the Home card', (
      tester,
    ) async {
      await tester.pumpWidget(_wrap(const BlogListScreen(), FakeBlogApi()));
      await tester.pump();
      expect(find.text('Plant Journal'), findsOneWidget);
      expect(find.text('Blog'), findsNothing);
    });

    testWidgets('a /blog/<slug> link opens that post, and Back returns', (
      tester,
    ) async {
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>See <a href="/blog/snake-plant/">snake plants</a>.</p>',
          ),
          'snake-plant': const BlogPost(
            id: 2,
            slug: 'snake-plant',
            title: 'Snake Plant',
          ),
        },
      );
      final router = await pumpRouted(tester, api);

      await tester.tapOnText(find.textRange.ofSubstring('snake plants'));
      await tester.pump();
      await tester.pump();
      expect(location(router), '/blog/snake-plant');
      expect(find.text('Snake Plant'), findsWidgets);

      router.pop();
      await tester.pump();
      await tester.pump();
      expect(location(router), '/blog/pothos');
    });

    testWidgets('a link to the post itself pushes nothing', (tester) async {
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>Back to <a href="/blog/pothos/">the top</a>.</p>',
          ),
        },
      );
      final router = await pumpRouted(tester, api);

      await tester.tapOnText(find.textRange.ofSubstring('the top'));
      await tester.pump();
      await tester.pump();

      expect(location(router), '/blog/pothos');
      expect(
        find.byType(BlogPostScreen, skipOffstage: false),
        findsOneWidget,
        reason: 'a duplicate screen was pushed',
      );
    });

    testWidgets('a unicode slug opens in the app, not the browser', (
      tester,
    ) async {
      final opened = <String>[];
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>Read <a href="/blog/çay-bitkisi/">çay</a>.</p>',
          ),
          'çay-bitkisi': const BlogPost(
            id: 3,
            slug: 'çay-bitkisi',
            title: 'Çay bitkisi',
          ),
        },
      );
      await pumpRouted(tester, api, opened: opened);

      await tester.tapOnText(find.textRange.ofSubstring('çay'));
      await tester.pump();
      await tester.pump();

      expect(opened, isEmpty);
      expect(find.text('Çay bitkisi'), findsWidgets);
      expect(internalBlogSlug('/blog/%C3%A7ay-bitkisi'), 'çay-bitkisi');
      expect(internalBlogSlug('/blog/'), isNull);
      expect(internalBlogSlug('https://example.com/blog/a/'), isNull);
      expect(internalBlogSlug('/forum/a/'), isNull);
    });

    testWidgets('an internal page link to a blog post opens it in the app '
        'with its title in the bar before the post loads', (tester) async {
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>See <a linktype="page" id="42">snake plants</a>.</p>',
          ),
        },
      );
      api.pagesById[42] = const BlogPageRef(
        id: 42,
        type: blogPostPageType,
        slug: 'snake-plant',
        title: 'Snake Plant Care',
        htmlUrl: 'https://houseplant-md.com/blog/snake-plant/',
      );
      final router = await pumpRouted(tester, api);

      await tester.tapOnText(find.textRange.ofSubstring('snake plants'));
      await tester.pump();
      await tester.pump();

      expect(location(router), '/blog/snake-plant');
      // The post 404s in this fake, so the title can only be the link's.
      expect(find.text('Snake Plant Care'), findsOneWidget);
    });

    testWidgets('an internal page link to any other page opens its web URL', (
      tester,
    ) async {
      final opened = <String>[];
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>Read <a linktype="page" id="5">about us</a>.</p>',
          ),
        },
      );
      api.pagesById[5] = const BlogPageRef(
        id: 5,
        type: 'home.HomePage',
        slug: 'about',
        htmlUrl: 'https://houseplant-md.com/about/',
      );
      final router = await pumpRouted(tester, api, opened: opened);

      await tester.tapOnText(find.textRange.ofSubstring('about us'));
      await tester.pump();
      await tester.pump();

      expect(opened, ['https://houseplant-md.com/about/']);
      expect(location(router), '/blog/pothos');
    });

    testWidgets('an unresolvable page link says so, never fails silently', (
      tester,
    ) async {
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>See <a linktype="page" id="404">gone</a>.</p>',
          ),
        },
      );
      await pumpRouted(tester, api);

      await tester.tapOnText(find.textRange.ofSubstring('gone'));
      await tester.pump();
      await tester.pump();

      expect(find.text("Couldn't open this link."), findsOneWidget);
    });

    testWidgets('headings inside a paragraph block start their own line', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ForumHtmlText(
              '<p>Intro text.</p><h2>Watering</h2><p>Weekly.</p>'
              '<h3>Light</h3><p>Bright.</p>',
            ),
          ),
        ),
      );
      final text = tester.widget<RichText>(find.byType(RichText).first);
      expect(
        text.text.toPlainText(),
        'Intro text.\n\nWatering\n\nWeekly.\n\nLight\n\nBright.',
      );
    });

    test('an inline image that 404s fails at once, not after ten retries '
        '(todo 567 finding 3)', () async {
      final api = FakeBlogApi();
      api.imageErrors[9] = ApiException('Not found', statusCode: 404);
      final container = ProviderContainer(
        overrides: [blogApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final sub = container.listen(blogInlineImageUrlProvider(9), (_, _) {});
      addTearDown(sub.close);

      await expectLater(
        container.read(blogInlineImageUrlProvider(9).future),
        throwsA(isA<ApiException>()),
      );
      // Riverpod's default first retry comes after 200 ms.
      await Future<void>.delayed(const Duration(milliseconds: 600));

      expect(api.imageLookups, [9]);
    });

    test('an inline image that fails with a 5xx is still retried', () async {
      final api = FakeBlogApi();
      api.imageErrors[9] = ApiException('Server error', statusCode: 503);
      final container = ProviderContainer(
        overrides: [blogApiProvider.overrideWithValue(api)],
      );
      addTearDown(container.dispose);
      final sub = container.listen(blogInlineImageUrlProvider(9), (_, _) {});
      addTearDown(sub.close);

      await Future<void>.delayed(const Duration(milliseconds: 600));

      expect(api.imageLookups.length, greaterThan(1));
    });

    testWidgets('an inline image embed is looked up by id and shown', (
      tester,
    ) async {
      final api = FakeBlogApi(
        posts: {
          'pothos': postWith(
            'pothos',
            '<p>Before.</p><embed alt="A pothos leaf" embedtype="image" '
                'format="fullwidth" id="3"/><p>After.</p>',
          ),
        },
      );
      api.imageUrls[3] = 'https://cdn.example.com/leaf.jpg';
      await pumpRouted(tester, api);
      await tester.pump();

      expect(api.imageLookups, [3]);
      expect(
        find.byWidgetPredicate(
          (w) =>
              w is CachedNetworkImage &&
              w.imageUrl == 'https://cdn.example.com/leaf.jpg',
        ),
        findsOneWidget,
      );
      expect(find.byType(BlogInlineImage), findsOneWidget);
    });

    group('spotlight', () {
      const lead = BlogPlantSpotlightBlock(
        plantName: 'Pothos',
        image: BlogImage(url: 'https://cdn.example.com/p.webp'),
        imageCredit: 'Photo by Jane on Unsplash',
        imageCreditUrl: 'https://unsplash.com/@jane',
        creditLead: 'Photo by Jane',
        unsplashHref: 'https://unsplash.com/?utm_source=plant_community',
      );

      Future<List<String>> pumpBlock(
        WidgetTester tester,
        BlogBlock block,
      ) async {
        final opened = <String>[];
        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              home: Scaffold(
                body: ListView(
                  children: [
                    BlogBlockView(
                      block: block,
                      mediaUrl: (u) => u,
                      onOpenLink: opened.add,
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
        return opened;
      }

      testWidgets('an Unsplash credit links the photographer and Unsplash '
          'separately', (tester) async {
        final opened = await pumpBlock(tester, lead);

        await tester.tap(find.text('Photo by Jane'));
        await tester.tap(find.text('Unsplash'));

        expect(opened, [
          'https://unsplash.com/@jane',
          'https://unsplash.com/?utm_source=plant_community',
        ]);
        expect(find.text('Photo by Jane on Unsplash'), findsNothing);
      });

      testWidgets('each credit link is ONE labelled link node with the tap '
          '(todo 567 finding 7)', (tester) async {
        final handle = tester.ensureSemantics();
        try {
          final opened = await pumpBlock(tester, lead);
          for (final label in ['Photo by Jane', 'Unsplash']) {
            final node = tester.getSemantics(
              find
                  .ancestor(
                    of: find.text(label),
                    matching: find.byType(Semantics),
                  )
                  .first,
            );
            final data = node.getSemanticsData();
            expect(data.label, label);
            expect(data.flagsCollection.isLink, isTrue);
            expect(data.hasAction(SemanticsAction.tap), isTrue);
            // No unlabelled InkWell tap node underneath.
            expect(node.childrenCount, 0, reason: '"$label" has child nodes');
          }

          tester.semantics.tap(find.semantics.byLabel('Unsplash'));
          expect(opened, ['https://unsplash.com/?utm_source=plant_community']);
        } finally {
          handle.dispose();
        }
      });

      testWidgets('each credit link is a full-size tap target', (tester) async {
        await pumpBlock(tester, lead);
        for (final label in ['Photo by Jane', 'Unsplash']) {
          final target = find.ancestor(
            of: find.text(label),
            matching: find.byType(InkWell),
          );
          expect(
            tester.getSize(target).height,
            greaterThanOrEqualTo(kMinInteractiveDimension),
            reason: '"$label" is too small to tap',
          );
        }
      });

      testWidgets('a photo that fails to load leaves no empty 2:1 box', (
        tester,
      ) async {
        await pumpBlock(tester, lead);
        final image = tester.widget<CachedNetworkImage>(
          find.byType(CachedNetworkImage),
        );
        final context = tester.element(find.byType(CachedNetworkImage));

        final failed = image.errorWidget!(context, 'x', Exception('404'));
        await tester.pumpWidget(MaterialApp(home: Center(child: failed)));
        expect(find.byType(AspectRatio), findsNothing);
        expect(tester.getSize(find.byWidget(failed)), Size.zero);

        // While it loads, the frame is held so the card does not jump.
        expect(image.placeholder!(context, 'x'), isA<AspectRatio>());
      });
    });
  });
}
