import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/models/models.dart';
import 'package:plant_community_mobile/features/forum/widgets/author_identity.dart';
import 'package:plant_community_mobile/features/forum/widgets/trust_badge.dart';

import '../support/forum_test_support.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) {
    return tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  group('AuthorIdentity', () {
    testWidgets('renders the name and trust badge', (tester) async {
      await pump(
        tester,
        AuthorIdentity(author: author(username: 'alice', trustLevel: 3)),
      );

      expect(find.text('alice'), findsOneWidget);
      expect(find.byType(TrustBadge), findsOneWidget);
    });

    testWidgets(
      'wraps in a tappable InkWell and fires onTap for a real author',
      (tester) async {
        var tapped = false;
        await pump(
          tester,
          AuthorIdentity(
            author: author(username: 'alice'),
            onTap: () => tapped = true,
          ),
        );

        expect(find.byType(InkWell), findsOneWidget);
        await tester.tap(find.byType(InkWell));
        await tester.pump();
        expect(tapped, isTrue);
      },
    );

    testWidgets('renders with no InkWell at all when onTap is null', (
      tester,
    ) async {
      await pump(tester, AuthorIdentity(author: author(username: 'alice')));

      expect(find.byType(InkWell), findsNothing);
    });

    testWidgets(
      'renders with no InkWell at all for a deleted author, even with onTap set',
      (tester) async {
        var tapped = false;
        await pump(
          tester,
          AuthorIdentity(
            author: author(
              username: ForumAuthor.deletedUsername,
              trustLevel: null,
            ),
            onTap: () => tapped = true,
          ),
        );

        expect(find.byType(InkWell), findsNothing);
        expect(tapped, isFalse);
      },
    );
  });

  group('AuthorAvatar (rounded square)', () {
    Future<void> pumpAvatar(
      WidgetTester tester,
      Widget child, {
      Brightness brightness = Brightness.dark,
      double textScale = 1.0,
      Size size = const Size(375, 812),
    }) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.build(brightness, AppTheme.defaultDensity),
          home: MediaQuery.withClampedTextScaling(
            minScaleFactor: textScale,
            maxScaleFactor: textScale,
            child: Scaffold(body: Center(child: child)),
          ),
        ),
      );
    }

    BoxDecoration decorationOf(WidgetTester tester, Finder avatar) {
      return tester
              .widget<DecoratedBox>(
                find.descendant(
                  of: avatar,
                  matching: find.byType(DecoratedBox),
                ),
              )
              .decoration
          as BoxDecoration;
    }

    test('forumAvatarRadius is 30% of the side', () {
      expect(forumAvatarRadius(34), BorderRadius.circular(34 * 0.3));
      expect(forumAvatarRadius(40), BorderRadius.circular(12));
    });

    testWidgets('an initial avatar is a rounded square, not a CircleAvatar', (
      tester,
    ) async {
      await pumpAvatar(
        tester,
        AuthorAvatar(author: author(username: 'alice'), radius: 17),
      );

      expect(find.byType(CircleAvatar), findsNothing);
      expect(find.byType(ClipOval), findsNothing);
      final avatar = find.byType(AuthorAvatar);
      expect(tester.getSize(avatar), const Size(34, 34));
      final decoration = decorationOf(tester, avatar);
      expect(decoration.shape, BoxShape.rectangle);
      expect(decoration.borderRadius, forumAvatarRadius(34));
      expect(find.text('A'), findsOneWidget);
    });

    testWidgets('an image avatar is clipped to the same square, cover-fit', (
      tester,
    ) async {
      await pumpAvatar(
        tester,
        const AuthorAvatar(
          author: ForumAuthor(
            username: 'alice',
            displayName: 'alice',
            avatar: 'https://cdn.example.test/a.jpg',
          ),
          radius: 20,
        ),
      );

      expect(find.byType(CircleAvatar), findsNothing);
      final avatar = find.byType(AuthorAvatar);
      expect(tester.getSize(avatar), const Size(40, 40));
      final decoration = decorationOf(tester, avatar);
      expect(decoration.borderRadius, forumAvatarRadius(40));
      expect(decoration.image?.fit, BoxFit.cover);
      final image = decoration.image?.image;
      expect(image, isA<CachedNetworkImageProvider>());
      expect(
        (image! as CachedNetworkImageProvider).url,
        'https://cdn.example.test/a.jpg',
      );
      // No letter over a photo.
      expect(find.byType(Text), findsNothing);
    });

    testWidgets('the fill is a stable accent tone per username', (
      tester,
    ) async {
      await pumpAvatar(
        tester,
        Column(
          children: [
            AuthorAvatar(
              key: const Key('a1'),
              author: author(username: 'alice'),
            ),
            AuthorAvatar(
              key: const Key('a2'),
              author: author(username: 'alice'),
            ),
          ],
        ),
      );
      final first = decorationOf(tester, find.byKey(const Key('a1'))).color;
      final second = decorationOf(tester, find.byKey(const Key('a2'))).color;
      expect(first, second);

      final canopy = tester.element(find.byKey(const Key('a1'))).canopy;
      expect(first, isNot(canopy.surface3));
      // Opaque: clusters overlap avatars.
      expect(first!.a, 1.0);
      final tones = [
        for (final accent in [
          canopy.leaf,
          canopy.clay,
          canopy.berry,
          canopy.sky,
        ])
          Color.alphaBlend(accent.withValues(alpha: 0.22), canopy.surface3),
      ];
      expect(tones, contains(first));
    });

    testWidgets('usernames spread over more than one tone', (tester) async {
      const names = ['alice', 'bob', 'carol', 'dave', 'erin', 'frank'];
      await pumpAvatar(
        tester,
        Column(
          children: [
            for (final n in names)
              AuthorAvatar(
                key: Key(n),
                author: author(username: n),
              ),
          ],
        ),
      );
      final fills = {
        for (final n in names) decorationOf(tester, find.byKey(Key(n))).color,
      };
      expect(fills.length, greaterThan(1));
    });

    testWidgets('a deleted author keeps the neutral surface3 fill', (
      tester,
    ) async {
      await pumpAvatar(
        tester,
        AuthorAvatar(
          author: author(
            username: ForumAuthor.deletedUsername,
            trustLevel: null,
          ),
        ),
      );
      final avatar = find.byType(AuthorAvatar);
      expect(
        decorationOf(tester, avatar).color,
        tester.element(avatar).canopy.surface3,
      );
    });

    for (final brightness in Brightness.values) {
      for (final textScale in [1.0, 2.0]) {
        for (final size in const [Size(320, 640), Size(375, 812)]) {
          testWidgets(
            'fits and stays readable: ${brightness.name}, ${textScale}x, '
            '${size.width.toInt()}pt',
            (tester) async {
              await pumpAvatar(
                tester,
                Wrap(
                  children: [
                    for (final n in ['alice', 'bob', 'carol', 'dave'])
                      for (final r in [10.0, 14.0, 20.0])
                        AuthorAvatar(
                          author: author(username: n),
                          radius: r,
                        ),
                  ],
                ),
                brightness: brightness,
                textScale: textScale,
                size: size,
              );

              expect(tester.takeException(), isNull);
              // The square never grows with text scale.
              final smallest = find.byType(AuthorAvatar).first;
              expect(tester.getSize(smallest), const Size(20, 20));
              await expectLater(tester, meetsGuideline(textContrastGuideline));
            },
          );
        }
      }
    }
  });
}
