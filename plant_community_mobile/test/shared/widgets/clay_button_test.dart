import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(Brightness.dark, AppDensity.cozy),
  home: Scaffold(body: Center(child: child)),
);

GreenThumbExtension get _ext => AppTheme.build(
  Brightness.dark,
  AppDensity.cozy,
).extension<GreenThumbExtension>()!;

/// The decorations ClayButton paints, innermost first.
Iterable<BoxDecoration> _decorations(WidgetTester tester) => tester
    .widgetList<DecoratedBox>(
      find.descendant(
        of: find.byType(ClayButton),
        matching: find.byType(DecoratedBox),
      ),
    )
    .map((d) => d.decoration)
    .whereType<BoxDecoration>();

void main() {
  testWidgets('renders label', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'Tap me')));
    expect(find.text('Tap me'), findsOneWidget);
  });

  testWidgets('primary is the Canopy gradient CTA, not a flat fill', (
    tester,
  ) async {
    // The web's primary is `canopy-cta` — a mint→sage gradient. It used to be
    // a flat clay (orange) fill here, which is not a Canopy button at all.
    await tester.pumpWidget(_wrap(ClayButton(label: 'X', onPressed: () {})));
    final decoration = _decorations(tester).firstWhere(
      (d) => d.gradient != null,
      orElse: () => const BoxDecoration(),
    );
    expect(
      decoration.gradient,
      isNotNull,
      reason: 'primary must be a gradient',
    );
    expect((decoration.gradient! as LinearGradient).colors, _ext.gradCta);
  });

  testWidgets('secondary uses the surface-2 fill and a line border', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ClayButton(
          label: 'X',
          variant: ClayButtonVariant.secondary,
          onPressed: () {},
        ),
      ),
    );
    final decoration = _decorations(tester).first;
    expect(decoration.color, _ext.surface2);
    expect(decoration.border, isNotNull);
  });

  testWidgets('outline is transparent with the brighter line-2 border', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ClayButton(
          label: 'X',
          variant: ClayButtonVariant.outline,
          onPressed: () {},
        ),
      ),
    );
    final decoration = _decorations(tester).first;
    expect(decoration.color, Colors.transparent);
    expect(decoration.border!.top.color, _ext.line2);
  });

  testWidgets('ghost has no fill and no border, and uses ink-2 text', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ClayButton(
          label: 'X',
          variant: ClayButtonVariant.ghost,
          onPressed: () {},
        ),
      ),
    );
    final decoration = _decorations(tester).first;
    expect(decoration.color, Colors.transparent);
    expect(decoration.border, isNull);
    expect(tester.widget<Text>(find.text('X')).style!.color, _ext.ink2);
  });

  testWidgets('every variant is a pill', (tester) async {
    for (final variant in ClayButtonVariant.values) {
      await tester.pumpWidget(
        _wrap(ClayButton(label: 'X', variant: variant, onPressed: () {})),
      );
      final radius = _decorations(tester).first.borderRadius! as BorderRadius;
      expect(radius.topLeft.x, 999.0, reason: '${variant.name} must be a pill');
    }
  });

  testWidgets('disabled: no tap, halved opacity, no shadow', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'X')));
    expect(tester.widget<InkWell>(find.byType(InkWell)).onTap, isNull);
    // The web disables with `opacity-50` on the whole control, so the gradient,
    // border and label fade together rather than each picking its own colour.
    expect(
      tester
          .widgetList<Opacity>(
            find.descendant(
              of: find.byType(ClayButton),
              matching: find.byType(Opacity),
            ),
          )
          .any((o) => o.opacity == 0.5),
      isTrue,
    );
    expect(_decorations(tester).first.boxShadow, isEmpty);
  });

  testWidgets('loading disables the button and shows a spinner', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(ClayButton(label: 'Post', loading: true, onPressed: () {})),
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.widget<InkWell>(find.byType(InkWell)).onTap, isNull);
  });

  testWidgets('loadingLabel swaps the visible label while busy', (
    tester,
  ) async {
    // A visible label swap is the most reliable "busy" signal for a screen
    // reader — matching the web's `loadingText`.
    await tester.pumpWidget(
      _wrap(
        ClayButton(
          label: 'Post',
          loading: true,
          loadingLabel: 'Posting…',
          onPressed: () {},
        ),
      ),
    );
    expect(find.text('Posting…'), findsOneWidget);
    expect(find.text('Post'), findsNothing);
  });

  testWidgets('fullWidth wraps in SizedBox with infinite width', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(const ClayButton(label: 'X', fullWidth: true)),
    );
    expect(
      find.byWidgetPredicate(
        (w) => w is SizedBox && w.width == double.infinity,
      ),
      findsOneWidget,
    );
  });

  testWidgets('icon renders when provided, but not while loading', (
    tester,
  ) async {
    await tester.pumpWidget(
      _wrap(
        ClayButton(label: 'Go', icon: LucideIcons.arrowRight, onPressed: () {}),
      ),
    );
    expect(find.byIcon(LucideIcons.arrowRight), findsOneWidget);

    await tester.pumpWidget(
      _wrap(
        ClayButton(
          label: 'Go',
          icon: LucideIcons.arrowRight,
          loading: true,
          onPressed: () {},
        ),
      ),
    );
    expect(find.byIcon(LucideIcons.arrowRight), findsNothing);
  });
}
