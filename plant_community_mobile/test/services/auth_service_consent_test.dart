import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/services/auth_service.dart';
import 'package:plant_community_mobile/services/push_registration_service.dart';

/// Sign-up consent through the token exchange (legal policies, Task 9).
///
/// The backend refuses to create a Django user from the exchange without
/// `accepted_terms: true` (428 `consent_required`). The app sends the flag
/// when this device holds the user's consent, and otherwise raises
/// [AuthState.consentRequired] so the root shows the consent sheet.
void main() {
  const storage = FlutterSecureStorage();

  ApiException consentRefusal() => ApiException(
    'Please accept the Privacy Policy and Terms of Service to create an '
    'account.',
    statusCode: 428,
    code: 'consent_required',
  );

  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  group('the exchange body', () {
    test('exchange sends accepted_terms when stored uid matches', () async {
      FlutterSecureStorage.setMockInitialValues({'accepted_terms_uid': 'u1'});
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      final body = h.api.exchangeBodies.single;
      expect(body['accepted_terms'], isA<bool>());
      expect(body['accepted_terms'], isTrue);
    });

    test('exchange omits accepted_terms for an existing user with no stored '
        'uid', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
      expect(h.state.isAuthenticated, isTrue);
    });

    test('a stored uid that is not the current user sends no flag', () async {
      FlutterSecureStorage.setMockInitialValues({'accepted_terms_uid': 'u2'});
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
    });

    test('a successful exchange deletes the stored consent', () async {
      FlutterSecureStorage.setMockInitialValues({'accepted_terms_uid': 'u1'});
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(await storage.read(key: 'accepted_terms_uid'), isNull);
    });

    test('a refused exchange keeps the stored consent for the retry', () async {
      // An email sign-up's first exchange is the unverified 403: the consent
      // must still be there once the email is verified.
      FlutterSecureStorage.setMockInitialValues({'accepted_terms_uid': 'u1'});
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(ApiException('Email not verified', statusCode: 403));
      h.read();

      await h.signIn(_FakeUser(uid: 'u1', emailVerified: false));

      expect(await storage.read(key: 'accepted_terms_uid'), 'u1');
    });
  });

  group('the 428 consent refusal', () {
    test('consent sheet shows on 428 and retry sends accepted_terms', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.state.consentRequired, isTrue);
      expect(h.state.isAuthenticated, isFalse);
      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);

      await h.notifier.acceptTermsAndRetry();

      expect(h.api.exchangeBodies, hasLength(2));
      expect(h.api.exchangeBodies.last['accepted_terms'], isA<bool>());
      expect(h.api.exchangeBodies.last['accepted_terms'], isTrue);
      expect(h.state.consentRequired, isFalse);
      expect(h.state.isAuthenticated, isTrue);
      expect(await storage.read(key: 'accepted_terms_uid'), isNull);
    });

    test('428 is not mistaken for unverified email', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.state.emailVerificationRequired, isFalse);
      expect(h.state.error, isNot(emailNotVerifiedMessage));
      // The sheet is the message: no SnackBar error under it.
      expect(h.state.error, isNull);
    });

    test('a retry already in flight sends no second exchange', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(_FakeUser(uid: 'u1'));

      final gate = Completer<void>();
      h.api.gate = gate;
      final first = h.notifier.acceptTermsAndRetry();
      await pumpEventQueue(); // parked in the request
      final second = h.notifier.acceptTermsAndRetry(); // a second tap
      await pumpEventQueue();
      gate.complete();
      await Future.wait([first, second]);

      expect(h.api.exchangeBodies, hasLength(2)); // the 428 + one retry
      expect(h.state.isAuthenticated, isTrue);
    });

    test('a 428 on the refresh exchange raises consentRequired', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(ApiException('server down', statusCode: 500));
      h.read();
      await h.signIn(_FakeUser(uid: 'u1'));
      expect(h.state.consentRequired, isFalse);

      h.api.errors.add(consentRefusal());
      await expectLater(h.api.refresher!(), throwsA(isA<ApiException>()));

      expect(h.state.consentRequired, isTrue);
      expect(h.state.firebaseUser?.uid, 'u1');
    });

    test('signing in again as the same user does not throw on a 428', () async {
      // The same-uid path runs the exchange itself; a 428 opens the sheet
      // rather than putting an error on the sign-in form.
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(uid: 'u1');
      h.firebaseAuth.signInUser = u1;
      h.api.errors.add(ApiException('server down', statusCode: 500));
      h.read();
      await h.signIn(u1);

      h.api.errors.add(consentRefusal());
      final needsVerification = await h.notifier.signInWithEmailPassword(
        'u1@example.com',
        'pw', // pragma: allowlist secret
      );

      expect(needsVerification, isFalse);
      expect(h.state.consentRequired, isTrue);
    });
  });

  group('a changed policy on an existing account', () {
    ApiException policyUpdateRefusal() => ApiException(
      'The Privacy Policy and Terms of Service have changed.',
      statusCode: 428,
      code: 'policy_update_required',
    );

    test('raises consentRequired with policyUpdate', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(policyUpdateRefusal());
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.state.consentRequired, isTrue);
      expect(h.state.policyUpdate, isTrue);
      expect(h.state.error, isNull);
    });

    test('declining signs out and never deletes the login', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(uid: 'u1', events: h.events);
      h.api.errors.add(policyUpdateRefusal());
      h.read();
      await h.signIn(u1);

      await h.notifier.declineTerms();

      expect(h.events, isNot(contains('user.delete')));
      expect(h.events, contains('firebase.signOut'));
      expect(h.state.consentRequired, isFalse);
    });

    test('accepting resends the exchange with accepted_terms', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(policyUpdateRefusal());
      h.read();
      await h.signIn(_FakeUser(uid: 'u1'));

      await h.notifier.acceptTermsAndRetry();

      expect(h.api.exchangeBodies.last['accepted_terms'], isTrue);
      expect(h.state.isAuthenticated, isTrue);
    });

    test('a new-account refusal is not a policy update', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();

      await h.signIn(_FakeUser(uid: 'u1'));

      expect(h.state.consentRequired, isTrue);
      expect(h.state.policyUpdate, isFalse);
    });
  });

  group('declineTerms', () {
    test('declineTerms deletes the firebase user and signs out', () async {
      FlutterSecureStorage.setMockInitialValues({'accepted_terms_uid': 'u1'});
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(uid: 'u1', events: h.events);
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(u1);

      await h.notifier.declineTerms();

      final order = h.events
          .where((e) => e == 'user.delete' || e == 'firebase.signOut')
          .toList();
      expect(order, ['user.delete', 'firebase.signOut']);
      expect(await storage.read(key: 'accepted_terms_uid'), isNull);
      expect(h.state.consentRequired, isFalse);
    });

    test('a current user other than the refused one is signed out, not '
        'deleted', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(uid: 'u1', events: h.events);
      final u2 = _FakeUser(uid: 'u2', events: h.events);
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(u1);
      expect(h.state.consentRequired, isTrue);

      h.firebaseAuth.currentUser = u2; // the account changed under the sheet
      await h.notifier.declineTerms();

      expect(h.events, isNot(contains('user.delete')));
      expect(h.events, contains('firebase.signOut'));
      expect(h.state.consentRequired, isFalse);
      expect(h.state.firebaseUser, isNull);
    });

    test('when delete throws, signOut still runs and nothing throws', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(
        uid: 'u1',
        events: h.events,
        deleteError: FirebaseAuthException(code: 'requires-recent-login'),
      );
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(u1);

      await h.notifier.declineTerms();

      expect(h.events, contains('user.delete'));
      expect(h.events, contains('firebase.signOut'));
    });
  });

  group('Google sign-in consent', () {
    test('google sign-in with acceptedTerms sends the flag on the first '
        'exchange', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      // The fake emits the auth-state event and lets the listener's exchange
      // finish BEFORE signInWithCredential returns, so it runs before the uid
      // is stored: only the in-memory pending flag can cover it.
      h.firebaseAuth.credentialUser = _FakeUser(uid: 'g1');

      await h.notifier.signInWithGoogle(acceptedTerms: true);
      await pumpEventQueue();

      final body = h.api.exchangeBodies.single;
      expect(body['accepted_terms'], isA<bool>());
      expect(body['accepted_terms'], isTrue);
    });

    test('an exchange that finishes before signInWithCredential returns '
        'keeps its JWT', () async {
      // The fake runs the listener's exchange to completion first.
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.credentialUser = _FakeUser(uid: 'g1');

      await h.notifier.signInWithGoogle();

      expect(h.state.isAuthenticated, isTrue);
      expect(h.state.isLoading, isFalse);
    });

    test('... and keeps its consent refusal for a new user', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();
      h.firebaseAuth.credentialUser = _FakeUser(uid: 'g1');

      await h.notifier.signInWithGoogle();

      expect(h.state.consentRequired, isTrue);
      expect(h.state.isLoading, isFalse);
    });

    test('google sign-in without acceptedTerms sends no flag', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.credentialUser = _FakeUser(uid: 'g1');

      await h.notifier.signInWithGoogle();
      await pumpEventQueue();

      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
    });

    test('a Google sign-in that throws leaves no pending consent', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.google.authenticateError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.unknownError,
        description: 'boom',
      );

      await expectLater(
        h.notifier.signInWithGoogle(acceptedTerms: true),
        throwsA(isA<AuthException>()),
      );

      // A later sign-in by anyone, with no consent given, sends no flag.
      await h.signIn(_FakeUser(uid: 'other'));
      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
    });
  });

  group('email registration consent', () {
    test('registering stores the consent for the new uid', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.createdUser = _FakeUser(uid: 'e1', emailVerified: false);

      await h.notifier.registerWithEmailPassword(
        email: 'e1@example.com',
        password: 'pw-123456', // pragma: allowlist secret
        displayName: 'E',
      );

      expect(await storage.read(key: 'accepted_terms_uid'), 'e1');
    });
  });
}

class _Harness {
  _Harness() {
    firebaseAuth = _FakeFirebaseAuth(events);
    api = _FakeApiService();
    google = _FakeGoogleSignIn();
    container = ProviderContainer(
      overrides: [
        apiServiceProvider.overrideWithValue(api),
        pushRegistrationServiceProvider.overrideWithValue(
          _NoopPushRegistrationService(api),
        ),
        authServiceProvider.overrideWith(
          () => _TestableAuthService(firebaseAuth, google),
        ),
      ],
    );
    _subscription = container.listen(
      authServiceProvider,
      (_, _) {},
      fireImmediately: true,
    );
  }

  final List<String> events = [];
  late final _FakeFirebaseAuth firebaseAuth;
  late final _FakeApiService api;
  late final _FakeGoogleSignIn google;
  late final ProviderContainer container;
  late final ProviderSubscription<AuthState> _subscription;

  AuthState read() => container.read(authServiceProvider);
  AuthState get state => read();
  AuthService get notifier => container.read(authServiceProvider.notifier);

  Future<void> signIn(User user) async {
    firebaseAuth.currentUser = user;
    firebaseAuth.authStateController.add(user);
    await pumpEventQueue();
  }

  void dispose() {
    _subscription.close();
    container.dispose();
    firebaseAuth.authStateController.close();
  }
}

class _TestableAuthService extends AuthService {
  _TestableAuthService(this._auth, this._google);

  final FirebaseAuth _auth;
  final GoogleSignIn _google;

  @override
  FirebaseAuth get firebaseAuth => _auth;

  @override
  GoogleSignIn get googleSignIn => _google;
}

class _NoopPushRegistrationService extends PushRegistrationService {
  _NoopPushRegistrationService(super.apiService);

  @override
  Future<void> syncAfterLogin() async {}

  @override
  Future<void> clearOnLogout() async {}

  @override
  void detach() {}
}

class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://fake.local', authToken: null);

  /// Each token-exchange body, in order.
  final List<Map<String, dynamic>> exchangeBodies = [];

  /// Thrown by the next exchanges, one each, in order.
  final List<Exception> errors = [];

  /// Holds the exchange open while set.
  Completer<void>? gate;

  Future<String?> Function()? refresher;

  @override
  void setAccessTokenRefresher(Future<String?> Function()? r) {
    refresher = r;
    super.setAccessTokenRefresher(r);
  }

  @override
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    void Function(int sent, int total)? onSendProgress,
    Duration? receiveTimeout,
  }) async {
    if (path == '/auth/firebase-token-exchange/') {
      exchangeBodies.add(Map<String, dynamic>.from(data as Map));
    }
    final g = gate;
    if (g != null) await g.future;
    if (errors.isNotEmpty) throw errors.removeAt(0);
    return Response<dynamic>(
      requestOptions: RequestOptions(path: path),
      data: {'access_token': 'django-jwt', 'refresh_token': 'django-refresh'},
    );
  }
}

class _FakeFirebaseAuth implements FirebaseAuth {
  _FakeFirebaseAuth(this._events);

  final List<String> _events;
  final authStateController = StreamController<User?>.broadcast();

  @override
  User? currentUser;

  User? signInUser;
  User? createdUser;

  /// The user `signInWithCredential` signs in. Emitted on the auth-state
  /// stream before the call returns.
  User? credentialUser;

  @override
  Stream<User?> authStateChanges() => authStateController.stream;

  @override
  Future<void> signOut() async {
    _events.add('firebase.signOut');
    currentUser = null;
  }

  @override
  Future<UserCredential> signInWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    currentUser = signInUser;
    return _FakeUserCredential(signInUser);
  }

  @override
  Future<UserCredential> createUserWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    currentUser = createdUser;
    return _FakeUserCredential(createdUser);
  }

  @override
  Future<UserCredential> signInWithCredential(AuthCredential credential) async {
    currentUser = credentialUser;
    authStateController.add(credentialUser);
    // Let the listener's whole exchange run before this call returns, so
    // nothing signInWithGoogle stores afterwards can have fed it.
    await pumpEventQueue();
    return _FakeUserCredential(credentialUser);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUserCredential implements UserCredential {
  _FakeUserCredential(this.user);

  @override
  final User? user;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUser implements User {
  _FakeUser({
    required this.uid,
    this.emailVerified = true,
    List<String>? events,
    this.deleteError,
  }) : _events = events ?? [];

  @override
  final String uid;

  @override
  bool emailVerified;

  final List<String> _events;
  final Exception? deleteError;

  @override
  String? get email => '$uid@example.com';

  @override
  Future<String?> getIdToken([bool forceRefresh = false]) async =>
      'firebase-id-token';

  @override
  Future<void> delete() async {
    _events.add('user.delete');
    final error = deleteError;
    if (error != null) throw error;
  }

  @override
  Future<void> reload() async {}

  @override
  Future<void> updateDisplayName(String? displayName) async {}

  @override
  Future<void> sendEmailVerification([ActionCodeSettings? settings]) async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeGoogleSignIn implements GoogleSignIn {
  GoogleSignInException? authenticateError;

  @override
  Future<void> initialize({
    String? clientId,
    String? serverClientId,
    String? nonce,
    String? hostedDomain,
  }) async {}

  @override
  Future<GoogleSignInAccount> authenticate({
    List<String> scopeHint = const <String>[],
  }) async {
    final error = authenticateError;
    if (error != null) throw error;
    return _FakeGoogleAccount();
  }

  @override
  Future<void> signOut() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeGoogleAccount implements GoogleSignInAccount {
  @override
  GoogleSignInAuthentication get authentication =>
      const GoogleSignInAuthentication(idToken: 'google-id-token');

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
