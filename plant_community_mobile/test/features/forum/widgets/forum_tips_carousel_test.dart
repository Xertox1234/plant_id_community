import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/widgets/forum_tips_carousel.dart';

List<String> _ids(List<ForumTip> tips) => [for (final t in tips) t.id];

/// The card on show: the one whose opacity is 1.
String _shown(WidgetTester tester) {
  final shown = <String>[];
  for (final e in find.byType(AnimatedOpacity).evaluate()) {
    final w = e.widget as AnimatedOpacity;
    if (w.opacity != 1) continue;
    final key = w.child!.key;
    shown.add(key is ValueKey<String> ? key.value : 'intro');
  }
  expect(shown, hasLength(1));
  return shown.single;
}

void main() {
  group('forumTipsFor', () {
    test('a guest is asked to sign in, and gets no member-only tips', () {
      final ids = _ids(forumTipsFor(signedIn: false));
      expect(ids.first, 'sign-in');
      expect(ids, isNot(contains('add-avatar')));
      expect(ids, isNot(contains('premium-checks')));
      expect(ids, isNot(contains('bookmarks')));
    });

    test('a member with no avatar is asked to add one, first', () {
      final ids = _ids(forumTipsFor(signedIn: true, hasAvatar: false));
      expect(ids.first, 'add-avatar');
      expect(ids, isNot(contains('sign-in')));
    });

    test('a member with an avatar, or an unknown one, is not asked', () {
      expect(
        _ids(forumTipsFor(signedIn: true, hasAvatar: true)),
        isNot(contains('add-avatar')),
      );
      expect(_ids(forumTipsFor(signedIn: true)), isNot(contains('add-avatar')));
    });

    test('premium is offered only to a known non-premium member, with the '
        'server\'s number', () {
      final tips = forumTipsFor(
        signedIn: true,
        isPremium: false,
        premiumDailyChecks: 3,
      );
      final premium = tips.singleWhere((t) => t.id == 'premium-checks');
      expect(premium.body, contains('3 plant health checks'));

      expect(
        _ids(
          forumTipsFor(signedIn: true, isPremium: true, premiumDailyChecks: 3),
        ),
        isNot(contains('premium-checks')),
      );
      expect(
        _ids(forumTipsFor(signedIn: true)),
        isNot(contains('premium-checks')),
      );
    });

    test('an action always has both its words and its route', () {
      for (final tip in [
        ...forumTipsFor(signedIn: false),
        ...forumTipsFor(
          signedIn: true,
          hasAvatar: false,
          isPremium: false,
          premiumDailyChecks: 3,
        ),
      ]) {
        expect(tip.actionLabel == null, tip.routeName == null, reason: tip.id);
      }
    });
  });

  group('ForumTipsCarousel', () {
    final tips = forumTipsFor(signedIn: true, hasAvatar: false);

    Widget host({
      Widget? intro = const Text('About this forum'),
      List<ForumTip>? only,
      void Function(String)? onAction,
      bool reduceMotion = false,
      Brightness? brightness,
      double scale = 1,
    }) => MaterialApp(
      theme: brightness == null
          ? null
          : AppTheme.build(brightness, AppDensity.cozy),
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(
            disableAnimations: reduceMotion,
            textScaler: TextScaler.linear(scale),
          ),
          child: Scaffold(
            body: SingleChildScrollView(
              child: ForumTipsCarousel(
                intro: intro,
                tips: only ?? tips,
                onAction: onAction ?? (_) {},
              ),
            ),
          ),
        ),
      ),
    );

    testWidgets('starts on the intro and turns by itself', (tester) async {
      await tester.pumpWidget(host());
      expect(_shown(tester), 'intro');

      await tester.pump(const Duration(seconds: 7));
      await tester.pump(const Duration(milliseconds: 300));
      expect(_shown(tester), 'add-avatar');
    });

    testWidgets('a dot picks a card, and the carousel then holds still', (
      tester,
    ) async {
      await tester.pumpWidget(host());
      await tester.tap(find.bySemanticsLabel('Card 3 of ${tips.length + 1}'));
      await tester.pump(const Duration(milliseconds: 300));
      final picked = _shown(tester);
      expect(picked, tips[1].id);

      await tester.pump(const Duration(seconds: 30));
      expect(_shown(tester), picked);
    });

    testWidgets('a swipe moves one card each way', (tester) async {
      await tester.pumpWidget(host());
      await tester.fling(
        find.byType(ForumTipsCarousel),
        const Offset(-200, 0),
        800,
      );
      await tester.pump(const Duration(milliseconds: 300));
      expect(_shown(tester), 'add-avatar');

      await tester.fling(
        find.byType(ForumTipsCarousel),
        const Offset(200, 0),
        800,
      );
      await tester.pump(const Duration(milliseconds: 300));
      expect(_shown(tester), 'intro');
    });

    testWidgets('with reduced motion it never turns by itself', (tester) async {
      await tester.pumpWidget(host(reduceMotion: true));
      await tester.pump(const Duration(seconds: 30));
      expect(_shown(tester), 'intro');
    });

    testWidgets('only the card on show can be tapped, and its action names '
        'its route', (tester) async {
      final opened = <String>[];
      await tester.pumpWidget(host(onAction: opened.add));
      // The avatar tip is laid out but hidden behind the intro.
      await tester.tap(find.text('Edit profile'), warnIfMissed: false);
      expect(opened, isEmpty);

      await tester.tap(find.bySemanticsLabel('Card 2 of ${tips.length + 1}'));
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.text('Edit profile'));
      expect(opened, ['editProfile']);
    });

    testWidgets('the height does not change as the cards turn', (tester) async {
      await tester.pumpWidget(host());
      final before = tester.getSize(find.byType(ForumTipsCarousel));
      for (var i = 0; i < tips.length; i++) {
        await tester.pump(const Duration(seconds: 7));
        await tester.pump(const Duration(milliseconds: 300));
        expect(tester.getSize(find.byType(ForumTipsCarousel)), before);
      }
    });

    testWidgets('one card shows no dots; none shows nothing', (tester) async {
      await tester.pumpWidget(host(only: const []));
      expect(find.bySemanticsLabel(RegExp('^Card ')), findsNothing);
      expect(find.text('About this forum'), findsOneWidget);

      await tester.pumpWidget(host(intro: null, only: const []));
      expect(tester.getSize(find.byType(ForumTipsCarousel)).height, 0);
    });

    for (final brightness in Brightness.values) {
      for (final (w, scale) in [(320.0, 2.0), (375.0, 1.0)]) {
        testWidgets('every tip fits and is readable at ${w}pt @$scale '
            '(${brightness.name})', (tester) async {
          tester.view.physicalSize = Size(w, 800);
          tester.view.devicePixelRatio = 1.0;
          addTearDown(tester.view.reset);
          final handle = tester.ensureSemantics();
          final all = [
            ...forumTipsFor(signedIn: false),
            ...forumTipsFor(
              signedIn: true,
              hasAvatar: false,
              isPremium: false,
              premiumDailyChecks: 3,
            ),
          ];
          for (final tip in all) {
            await tester.pumpWidget(
              host(
                intro: null,
                only: [tip],
                brightness: brightness,
                scale: scale,
              ),
            );
            await tester.pump();
            expect(tester.takeException(), isNull, reason: tip.id);
            await expectLater(
              tester,
              meetsGuideline(textContrastGuideline),
              reason: tip.id,
            );
            await expectLater(
              tester,
              meetsGuideline(androidTapTargetGuideline),
              reason: tip.id,
            );
          }
          handle.dispose();
        });
      }
    }
  });
}
