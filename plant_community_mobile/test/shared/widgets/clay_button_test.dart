import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: Scaffold(body: Center(child: child)),
    );

GreenThumbExtension get _ext =>
    AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
        .extension<GreenThumbExtension>()!;

void main() {
  testWidgets('renders label', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'Tap me')));
    expect(find.text('Tap me'), findsOneWidget);
  });

  testWidgets('primary variant uses clay background', (tester) async {
    await tester.pumpWidget(
        _wrap(ClayButton(label: 'X', onPressed: () {})));
    final ext = _ext;
    final hasClay = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == ext.clay);
    expect(hasClay, isTrue);
  });

  testWidgets('secondary variant uses colorScheme.primary', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'X',
      variant: ClayButtonVariant.secondary,
      onPressed: () {},
    )));
    final primary = AppTheme.build(
            AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
        .colorScheme
        .primary;
    final hasPrimary = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == primary);
    expect(hasPrimary, isTrue);
  });

  testWidgets('outline variant has transparent background', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'X',
      variant: ClayButtonVariant.outline,
      onPressed: () {},
    )));
    final hasTransparent = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == Colors.transparent);
    expect(hasTransparent, isTrue);
  });

  testWidgets('disabled: InkWell.onTap is null', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'X')));
    final inkWell = tester.widget<InkWell>(find.byType(InkWell));
    expect(inkWell.onTap, isNull);
  });

  testWidgets('fullWidth wraps in SizedBox with infinite width', (tester) async {
    await tester.pumpWidget(
        _wrap(const ClayButton(label: 'X', fullWidth: true)));
    expect(
      find.byWidgetPredicate(
          (w) => w is SizedBox && w.width == double.infinity),
      findsOneWidget,
    );
  });

  testWidgets('icon renders when provided', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'Go',
      icon: Icons.arrow_forward,
      onPressed: () {},
    )));
    expect(find.byIcon(Icons.arrow_forward), findsOneWidget);
  });
}
