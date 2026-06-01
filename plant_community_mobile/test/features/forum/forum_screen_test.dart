import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(
    AppPaletteChoice.loam,
    Brightness.light,
    AppDensity.cozy,
  ),
  home: child,
);

void main() {
  testWidgets('renders 3 sample posts', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.textContaining('Monstera'), findsOneWidget);
    expect(find.textContaining('succulent'), findsOneWidget);
    expect(find.textContaining('fern'), findsOneWidget);
  });

  testWidgets('ClayButton New Post present', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.byType(ClayButton), findsOneWidget);
    expect(find.text('+ New Post'), findsOneWidget);
  });

  testWidgets('coming soon notice present', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.textContaining('coming soon'), findsOneWidget);
  });

  testWidgets('no crashes on pump', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(tester.takeException(), isNull);
  });
}
