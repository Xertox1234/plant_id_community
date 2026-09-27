import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/onboarding/onboarding_checklist_card.dart';
import 'package:plant_community_mobile/features/onboarding/onboarding_checklist_service.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

/// Todo 412: the home checklist, driven by the server's derived steps.
///
/// Presence is anchored on the "Dismiss" button: the header is a
/// CanopyLabel, which upper-cases its text, so a `find.text` on the header's
/// source string would pass vacuously when checking for absence.

Map<String, dynamic> _checklist({
  bool identify = false,
  bool forum = false,
  bool profile = false,
  bool dismissed = false,
}) => {
  'steps': [
    {'key': 'identify_plant', 'done': identify},
    {'key': 'forum_post', 'done': forum},
    {'key': 'profile', 'done': profile},
  ],
  'complete': identify && forum && profile,
  'dismissed': dismissed,
};

class _FakeApi extends ApiService {
  _FakeApi(this.checklist, {this.failPatch = false})
    : super(baseUrl: 'https://api.example.test/api/v1');

  Map<String, dynamic> checklist;
  final bool failPatch;
  final patches = <Object?>[];

  Response<dynamic> _ok(String path) => Response(
    requestOptions: RequestOptions(path: path),
    statusCode: 200,
    data: {'checklist': checklist},
  );

  @override
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async => _ok(path);

  @override
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    patches.add(data);
    if (failPatch) throw ApiException('Server error');
    checklist = {...checklist, 'dismissed': true};
    return _ok(path);
  }
}

class _Auth extends AuthService {
  _Auth(this.signedIn);
  final bool signedIn;

  @override
  AuthState build() => AuthState(jwtToken: signedIn ? 'jwt' : null);
}

Future<void> _pump(
  WidgetTester tester,
  _FakeApi api, {
  bool signedIn = true,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiServiceProvider.overrideWithValue(api),
        authServiceProvider.overrideWith(() => _Auth(signedIn)),
      ],
      child: const MaterialApp(home: Scaffold(body: OnboardingChecklistCard())),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows the three steps and how many are done', (tester) async {
    await _pump(tester, _FakeApi(_checklist(forum: true)));

    expect(find.text('1 of 3 done'), findsOneWidget);
    expect(find.text('Identify your first plant'), findsOneWidget);
    expect(find.text('Say hello in the forum'), findsOneWidget);
    expect(find.text('Add a photo or a short bio'), findsOneWidget);
  });

  testWidgets('a done step is announced as done and is not a button', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await _pump(tester, _FakeApi(_checklist(forum: true)));

    final done = tester
        .getSemantics(find.bySemanticsLabel('Done: Say hello in the forum'))
        .getSemanticsData();
    expect(done.flagsCollection.isButton, isFalse);
    expect(done.hasAction(SemanticsAction.tap), isFalse);
    final open = tester
        .getSemantics(find.bySemanticsLabel('Identify your first plant'))
        .getSemanticsData();
    expect(open.flagsCollection.isButton, isTrue);
    expect(open.hasAction(SemanticsAction.tap), isTrue);
    handle.dispose();
  });

  testWidgets('shows nothing when every step is done', (tester) async {
    await _pump(
      tester,
      _FakeApi(_checklist(identify: true, forum: true, profile: true)),
    );

    expect(find.text('Dismiss'), findsNothing);
  });

  testWidgets('shows nothing once dismissed', (tester) async {
    await _pump(tester, _FakeApi(_checklist(dismissed: true)));

    expect(find.text('Dismiss'), findsNothing);
  });

  testWidgets('shows nothing when signed out, and never calls the API', (
    tester,
  ) async {
    final api = _FakeApi(_checklist());
    await _pump(tester, api, signedIn: false);

    expect(find.text('Dismiss'), findsNothing);
  });

  testWidgets('Dismiss hides the card and tells the server', (tester) async {
    final api = _FakeApi(_checklist());
    await _pump(tester, api);

    await tester.tap(find.text('Dismiss'));
    await tester.pumpAndSettle();

    expect(find.text('Dismiss'), findsNothing);
    expect(api.patches, [
      {'completed_checklist': true},
    ]);
  });

  testWidgets('a refused dismiss brings the card back', (tester) async {
    await _pump(tester, _FakeApi(_checklist(), failPatch: true));

    await tester.tap(find.text('Dismiss'));
    await tester.pumpAndSettle();

    expect(find.text('Dismiss'), findsOneWidget);
  });

  test('an unknown step key from a newer server is skipped', () {
    final checklist = OnboardingChecklist.fromJson({
      'steps': [
        {'key': 'identify_plant', 'done': false},
        {'key': 'future_step', 'done': false},
      ],
      'complete': false,
      'dismissed': false,
    });
    expect(
      checklist.steps.where((s) => onboardingSteps.containsKey(s.key)),
      hasLength(1),
    );
  });
}
