import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
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

  Future<({List<LegalDoc> opened, bool Function() value})> pumpCheckbox(
    WidgetTester tester,
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
    return (opened: opened, value: () => value);
  }

  /// Centre of the first occurrence of [needle] in the rendered paragraph.
  Offset spanCentre(WidgetTester tester, String needle) {
    final render = tester.renderObject<RenderParagraph>(
      find.descendant(
        of: find.byType(ConsentCheckbox),
        matching: find.byType(RichText),
      ),
    );
    final start = render.text.toPlainText().indexOf(needle);
    final boxes = render.getBoxesForSelection(
      TextSelection(baseOffset: start, extentOffset: start + needle.length),
    );
    return render.localToGlobal(boxes.first.toRect().center);
  }

  testWidgets('a real tap on a link opens the document and does not toggle', (
    tester,
  ) async {
    final h = await pumpCheckbox(tester);
    await tester.tapAt(spanCentre(tester, 'Privacy Policy'));
    await tester.pump();
    await tester.tapAt(spanCentre(tester, 'Terms of Service'));
    await tester.pump();
    expect(h.opened, [LegalDoc.privacy, LegalDoc.terms]);
    expect(h.value(), isFalse);
  });

  testWidgets('a real tap on the plain text toggles once', (tester) async {
    final h = await pumpCheckbox(tester);
    await tester.tapAt(spanCentre(tester, 'I am 13'));
    await tester.pump();
    expect(h.value(), isTrue);
    expect(h.opened, isEmpty);
  });

  testWidgets('screen readers get actions to open each document', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final h = await pumpCheckbox(tester);
    final node = tester.getSemantics(
      find.bySemanticsLabel(RegExp(RegExp.escape(_copy))),
    );
    final data = node.getSemanticsData();
    final actions = data.customSemanticsActionIds!
        .map(CustomSemanticsAction.getAction)
        .map((a) => a!.label)
        .toList();
    expect(
      actions,
      containsAll(['Open Privacy Policy', 'Open Terms of Service']),
    );

    final id = data.customSemanticsActionIds!.firstWhere(
      (i) =>
          CustomSemanticsAction.getAction(i)!.label == 'Open Terms of Service',
    );
    tester.semantics.performAction(
      find.semantics.byLabel(RegExp(RegExp.escape(_copy))),
      SemanticsAction.customAction,
      args: id,
    );
    await tester.pump();
    expect(h.opened, [LegalDoc.terms]);
    expect(h.value(), isFalse);
    handle.dispose();
  });

  testWidgets('keyboard submit with the box unticked registers nobody', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [authServiceProvider.overrideWith(_CountingAuth.new)],
        child: const MaterialApp(home: RegisterScreen()),
      ),
    );
    _CountingAuth.registered = 0;
    for (final e in {
      'Display name': 'Ada',
      'Email': 'ada@example.com',
      'Password': 'secret1', // pragma: allowlist secret
      'Confirm password': 'secret1', // pragma: allowlist secret
    }.entries) {
      await tester.enterText(
        find.widgetWithText(TextFormField, e.key),
        e.value,
      );
    }
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(_CountingAuth.registered, 0);

    // Positive control: with the box ticked the same action registers.
    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    await tester.tap(find.widgetWithText(TextFormField, 'Confirm password'));
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(_CountingAuth.registered, 1);
  });
}

class _CountingAuth extends FakeAuthService {
  _CountingAuth() : super(loggedIn: false);
  static int registered = 0;

  @override
  Future<bool> registerWithEmailPassword({
    required String email,
    required String password,
    required String displayName,
  }) async {
    registered++;
    return true;
  }
}
