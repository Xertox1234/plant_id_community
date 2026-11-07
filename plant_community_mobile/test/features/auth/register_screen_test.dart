import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/auth/consent_checkbox.dart';
import 'package:plant_community_mobile/features/auth/register_screen.dart';
import 'package:plant_community_mobile/features/legal/legal_links.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

const _copy =
    'I am 13 or older, and I have read and accept the Privacy Policy and '
    'Terms of Service.';

/// The recognizer behind the [TextSpan] whose text is [label].
GestureRecognizer? _recognizerFor(WidgetTester tester, String label) {
  GestureRecognizer? found;
  final rich = tester.widget<RichText>(
    find.descendant(
      of: find.byType(ConsentCheckbox),
      matching: find.byType(RichText),
    ),
  );
  rich.text.visitChildren((span) {
    if (span is TextSpan && span.text == label) found = span.recognizer;
    return true;
  });
  return found;
}

void main() {
  Future<void> pumpRegister(WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authServiceProvider.overrideWith(
            () => FakeAuthService(loggedIn: false),
          ),
        ],
        child: const MaterialApp(home: RegisterScreen()),
      ),
    );
  }

  Finder createButton() => find.widgetWithText(FilledButton, 'Create account');
  Finder googleButton() =>
      find.widgetWithText(OutlinedButton, 'Continue with Google');

  testWidgets('both sign-up buttons start disabled', (tester) async {
    await pumpRegister(tester);
    expect(tester.widget<FilledButton>(createButton()).onPressed, isNull);
    expect(tester.widget<OutlinedButton>(googleButton()).onPressed, isNull);
    expect(tester.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
  });

  testWidgets('ticking the box enables both; unticking disables again', (
    tester,
  ) async {
    await pumpRegister(tester);
    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    expect(tester.widget<FilledButton>(createButton()).onPressed, isNotNull);
    expect(tester.widget<OutlinedButton>(googleButton()).onPressed, isNotNull);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    expect(tester.widget<FilledButton>(createButton()).onPressed, isNull);
  });

  testWidgets('shows the exact consent copy and a 48 dp tap target', (
    tester,
  ) async {
    await pumpRegister(tester);
    expect(find.textContaining(_copy, findRichText: true), findsOneWidget);
    expect(
      tester.getSize(find.byType(ConsentCheckbox)).height,
      greaterThanOrEqualTo(48),
    );
    expect(find.bySemanticsLabel(RegExp(RegExp.escape(_copy))), findsOneWidget);
  });

  testWidgets('tapping a link opens that document and does not toggle', (
    tester,
  ) async {
    final opened = <LegalDoc>[];
    var value = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) => ConsentCheckbox(
              value: value,
              onChanged: (v) => setState(() => value = v),
              onOpenDoc: (doc) async => opened.add(doc),
            ),
          ),
        ),
      ),
    );
    (_recognizerFor(tester, 'Privacy Policy') as TapGestureRecognizer).onTap!();
    (_recognizerFor(tester, 'Terms of Service') as TapGestureRecognizer)
        .onTap!();
    await tester.pump();
    expect(opened, [LegalDoc.privacy, LegalDoc.terms]);
    expect(value, isFalse);
  });
}
