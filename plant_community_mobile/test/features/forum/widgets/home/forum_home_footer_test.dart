import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/features/forum/widgets/home/forum_home_footer.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  Brightness brightness = Brightness.dark,
  Size size = const Size(375, 812),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.build(brightness, AppTheme.defaultDensity),
      home: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: Scaffold(body: SingleChildScrollView(child: child)),
      ),
    ),
  );
}

void main() {
  group('ForumHomeFooter', () {
    testWidgets('brand, eyebrow and a clock-driven copyright year', (
      tester,
    ) async {
      await _pump(tester, ForumHomeFooter(now: DateTime(2027)));
      expect(find.byType(BrandMark), findsOneWidget);
      expect(find.text('Houseplant MD'), findsOneWidget);
      expect(find.text('THE PLANT CLINIC'), findsOneWidget);
      expect(find.text('© 2027 Houseplant MD'), findsOneWidget);
    });

    testWidgets('light theme still shows the brand mark', (tester) async {
      await _pump(
        tester,
        ForumHomeFooter(now: DateTime(2027)),
        brightness: Brightness.light,
      );
      expect(find.byType(BrandMark), findsOneWidget);
    });

    testWidgets('no overflow at 320x640, x2.0', (tester) async {
      await _pump(
        tester,
        ForumHomeFooter(now: DateTime(2027)),
        size: const Size(320, 640),
        textScale: 2.0,
      );
      expect(tester.takeException(), isNull);
    });
  });
}
