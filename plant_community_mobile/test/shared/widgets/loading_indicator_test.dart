import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/shared/widgets/loading_indicator.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
  theme: AppTheme.build(
    AppPaletteChoice.loam,
    Brightness.light,
    AppDensity.cozy,
  ),
  home: Scaffold(body: Center(child: child)),
);

void main() {
  testWidgets('renders circular progress by default', (tester) async {
    await tester.pumpWidget(_wrap(const LoadingIndicator()));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('uses theme primary color by default', (tester) async {
    await tester.pumpWidget(_wrap(const LoadingIndicator()));
    final primary = AppTheme.build(
      AppPaletteChoice.loam,
      Brightness.light,
      AppDensity.cozy,
    ).colorScheme.primary;
    final progressIndicator = tester.widget<CircularProgressIndicator>(
      find.byType(CircularProgressIndicator),
    );
    expect(progressIndicator.valueColor?.value, equals(primary));
  });

  testWidgets('uses custom color when provided', (tester) async {
    await tester.pumpWidget(_wrap(const LoadingIndicator(color: Colors.red)));
    final progressIndicator = tester.widget<CircularProgressIndicator>(
      find.byType(CircularProgressIndicator),
    );
    expect(progressIndicator.valueColor?.value, equals(Colors.red));
  });

  testWidgets('renders linear indicator when type is linear', (tester) async {
    await tester.pumpWidget(_wrap(const LoadingIndicator.linear()));
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('displays message when provided', (tester) async {
    await tester.pumpWidget(
      _wrap(const LoadingIndicator.withMessage(message: 'Loading...')),
    );
    expect(find.text('Loading...'), findsOneWidget);
  });

  testWidgets('overlay shows dark background', (tester) async {
    await tester.pumpWidget(_wrap(const LoadingIndicator.overlay()));
    final containers = tester.widgetList<Container>(find.byType(Container));
    final hasDarkBackground = containers.any(
      (c) => c.color == Colors.black.withValues(alpha: 0.5),
    );
    expect(hasDarkBackground, isTrue);
  });
}
