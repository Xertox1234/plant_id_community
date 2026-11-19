import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
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

    test('L9: a delete that throws once is retried, then the user is signed '
        'out (todo 704)', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(
        uid: 'u1',
        events: h.events,
        deleteError: FirebaseAuthException(code: 'network-request-failed'),
        deleteFailures: 1,
      );
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(u1);

      await h.notifier.declineTerms();

      final order = h.events
          .where((e) => e == 'user.delete' || e == 'firebase.signOut')
          .toList();
      // The second try succeeds; the sign-out follows it.
      expect(order, ['user.delete', 'user.delete', 'firebase.signOut']);
      expect(u1.deleteFailures, 0);
      expect(h.firebaseAuth.currentUser, isNull);
      expect(h.state.firebaseUser, isNull);
    });

    test('L9: a delete that keeps throwing is tried a bounded number of '
        'times, and the user is still not left signed in (todo 704)', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      final u1 = _FakeUser(
        uid: 'u1',
        events: h.events,
        deleteError: FirebaseAuthException(code: 'network-request-failed'),
      );
      h.api.errors.add(consentRefusal());
      h.read();
      await h.signIn(u1);

      await h.notifier.declineTerms();

      final order = h.events
          .where((e) => e == 'user.delete' || e == 'firebase.signOut')
          .toList();
      expect(order, [
        'user.delete',
        'user.delete',
        'user.delete',
        'firebase.signOut',
      ]);
      expect(h.firebaseAuth.currentUser, isNull);
      expect(h.state.firebaseUser, isNull);
      expect(h.state.isAuthenticated, isFalse);
      expect(h.state.consentRequired, isFalse);
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

  group('Apple sign-in (todo 717)', () {
    test('asks Apple for the email and the name, and with acceptedTerms '
        'sends the flag on the first exchange', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      final user = _FakeUser(uid: 'a1');
      h.firebaseAuth.providerUser = user;

      final signedIn = await h.notifier.signInWithApple(acceptedTerms: true);
      await pumpEventQueue();

      expect(signedIn, isTrue);
      final provider = h.firebaseAuth.providers.single as AppleAuthProvider;
      expect(provider.providerId, 'apple.com');
      expect(provider.scopes, containsAll(['email', 'name']));
      final body = h.api.exchangeBodies.single;
      expect(body['accepted_terms'], isA<bool>());
      expect(body['accepted_terms'], isTrue);
      expect(h.state.isAuthenticated, isTrue);
    });

    test('the exchange forces a token refresh, so the name Apple sent on '
        'the first sign-in reaches the backend', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      final user = _FakeUser(uid: 'a1');
      h.firebaseAuth.providerUser = user;

      await h.notifier.signInWithApple();
      await pumpEventQueue();

      expect(user.idTokenForceRefresh, [true]);
      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
      // The 428's consent retry needs no second refresh.
    });

    test(
      '... also when the auth-state event comes after the call returned',
      () async {
        final h = _Harness();
        addTearDown(h.dispose);
        h.read();
        final user = _FakeUser(uid: 'a1');
        h.firebaseAuth.providerUser = user;
        h.firebaseAuth.emitProviderUserLate = true;

        await h.notifier.signInWithApple();
        expect(h.api.exchangeBodies, isEmpty);
        h.firebaseAuth.authStateController.add(user);
        await pumpEventQueue();

        expect(user.idTokenForceRefresh, [true]);
        // Only that first exchange: a later one uses the cached token.
        await h.signIn(user);
        expect(user.idTokenForceRefresh, [true, false]);
      },
    );

    test('a new Apple user without consent gets the consent sheet', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.api.errors.add(consentRefusal());
      h.read();
      h.firebaseAuth.providerUser = _FakeUser(uid: 'a1');

      await h.notifier.signInWithApple();

      expect(h.state.consentRequired, isTrue);
      expect(h.state.isLoading, isFalse);
      expect(h.state.error, isNull);
    });

    test('closing the Apple sheet is a cancel, not an error', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.providerError = FirebaseAuthException(code: 'canceled');

      final signedIn = await h.notifier.signInWithApple(acceptedTerms: true);

      expect(signedIn, isFalse);
      expect(h.state.error, isNull);
      expect(h.state.isLoading, isFalse);
      // No consent left pending for whoever signs in next.
      await h.signIn(_FakeUser(uid: 'other'));
      expect(h.api.exchangeBodies.single.containsKey('accepted_terms'), false);
    });

    test('an email that already signs in another way says so', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.providerError = FirebaseAuthException(
        code: 'account-exists-with-different-credential',
      );

      await expectLater(
        h.notifier.signInWithApple(),
        throwsA(
          isA<AuthException>().having(
            (e) => e.message,
            'message',
            appleAccountExistsMessage,
          ),
        ),
      );
    });

    test('an Apple failure throws a fixed message', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      h.read();
      h.firebaseAuth.providerError = FirebaseAuthException(code: 'failed');

      await expectLater(
        h.notifier.signInWithApple(),
        throwsA(
          isA<AuthException>().having(
            (e) => e.message,
            'message',
            appleSignInFailedMessage,
          ),
        ),
      );
      expect(h.state.error, appleSignInFailedMessage);
    });
  });

  group('deleting an Apple-linked account revokes its Apple tokens '
      '(todo 717)', () {
    setUp(() => debugDefaultTargetPlatformOverride = TargetPlatform.iOS);
    tearDown(() => debugDefaultTargetPlatformOverride = null);

    test('apple.com re-authenticates with Apple on iOS only', () {
      expect(
        reauthMethodFor(['apple.com'], platform: TargetPlatform.iOS),
        ReauthMethod.apple,
      );
      expect(
        reauthMethodFor([
          'google.com',
          'apple.com',
          'password',
        ], platform: TargetPlatform.iOS),
        ReauthMethod.apple,
      );
      expect(
        reauthMethodFor(['apple.com'], platform: TargetPlatform.android),
        isNull,
      );
    });

    Future<(_Harness, _FakeUser)> appleUser() async {
      final h = _Harness();
      addTearDown(h.dispose);
      final user = _FakeUser(uid: 'a1', providerIds: ['apple.com']);
      await h.signIn(user);
      return (h, user);
    }

    test('the re-auth signs in with Apple again and keeps the code, which '
        'revokeAppleSignIn hands to Firebase once', () async {
      final (h, user) = await appleUser();
      user.idTokenForceRefresh.clear();

      expect(h.notifier.reauthMethod, ReauthMethod.apple);
      final token = await h.notifier.freshIdTokenAfterReauth();

      expect(token, 'firebase-id-token');
      expect(user.idTokenForceRefresh, [true]);
      final provider = user.reauthProviders.single as AppleAuthProvider;
      expect(provider.scopes, containsAll(['email', 'name']));
      expect(h.firebaseAuth.revokedCodes, isEmpty, reason: 'not before');

      await h.notifier.revokeAppleSignIn();
      await h.notifier.revokeAppleSignIn();

      expect(h.firebaseAuth.revokedCodes, [_FakeUser.appleAuthCode]);
    });

    test('a revoke failure is logged, never thrown', () async {
      final (h, _) = await appleUser();
      h.firebaseAuth.revokeError = FirebaseAuthException(code: 'internal');
      await h.notifier.freshIdTokenAfterReauth();

      await h.notifier.revokeAppleSignIn();

      expect(h.firebaseAuth.revokedCodes, [_FakeUser.appleAuthCode]);
    });

    test(
      'no revoke for another account than the one re-authenticated',
      () async {
        final (h, _) = await appleUser();
        await h.notifier.freshIdTokenAfterReauth();
        await h.signIn(_FakeUser(uid: 'b2', providerIds: ['apple.com']));

        await h.notifier.revokeAppleSignIn();

        expect(h.firebaseAuth.revokedCodes, isEmpty);
      },
    );

    test('a Google or password account has nothing to revoke', () async {
      final h = _Harness();
      addTearDown(h.dispose);
      await h.signIn(_FakeUser(uid: 'p1'));
      await h.notifier.freshIdTokenAfterReauth(
        password: 'pw-123456', // pragma: allowlist secret
      );

      await h.notifier.revokeAppleSignIn();

      expect(h.firebaseAuth.revokedCodes, isEmpty);
    });

    test('closing the Apple sheet during the re-auth is a cancel', () async {
      final (h, user) = await appleUser();
      user.reauthError = FirebaseAuthException(code: 'canceled');

      await expectLater(
        h.notifier.freshIdTokenAfterReauth(),
        throwsA(isA<ReauthCancelledException>()),
      );
      await h.notifier.revokeAppleSignIn();
      expect(h.firebaseAuth.revokedCodes, isEmpty);
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

  /// The real retry count, without the real waits.
  @override
  List<Duration> get declineDeleteRetryDelays => const [
    Duration.zero,
    Duration.zero,
  ];
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

  /// The user `signInWithProvider` (Apple) signs in, emitted on the
  /// auth-state stream before the call returns unless [emitProviderUserLate];
  /// or [providerError], thrown instead. [providers] records each provider.
  User? providerUser;
  bool emitProviderUserLate = false;
  FirebaseAuthException? providerError;
  final List<AuthProvider> providers = [];

  /// Every code `revokeTokenWithAuthorizationCode` was given, and what it
  /// throws.
  final List<String> revokedCodes = [];
  FirebaseAuthException? revokeError;

  @override
  Future<UserCredential> signInWithProvider(AuthProvider provider) async {
    providers.add(provider);
    final error = providerError;
    if (error != null) throw error;
    currentUser = providerUser;
    if (!emitProviderUserLate) {
      authStateController.add(providerUser);
      await pumpEventQueue();
    }
    return _FakeUserCredential(providerUser);
  }

  @override
  Future<void> revokeTokenWithAuthorizationCode(String code) async {
    revokedCodes.add(code);
    final error = revokeError;
    if (error != null) throw error;
  }

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
  _FakeUserCredential(this.user, {this.additionalUserInfo});

  @override
  final User? user;

  @override
  final AdditionalUserInfo? additionalUserInfo;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUser implements User {
  _FakeUser({
    required this.uid,
    this.emailVerified = true,
    List<String>? events,
    this.deleteError,
    this.deleteFailures,
    this.providerIds = const ['password'],
  }) : _events = events ?? [];

  @override
  final String uid;

  /// The sign-in methods linked to the account, as `providerData` lists them.
  final List<String> providerIds;

  @override
  List<UserInfo> get providerData => [
    for (final id in providerIds) _FakeUserInfo(id),
  ];

  /// The code an Apple re-auth hands back.
  static const appleAuthCode = 'apple-authorization-code';

  /// Every provider `reauthenticateWithProvider` was given, and what it
  /// throws.
  final List<AuthProvider> reauthProviders = [];
  FirebaseAuthException? reauthError;

  @override
  Future<UserCredential> reauthenticateWithProvider(
    AuthProvider provider,
  ) async {
    reauthProviders.add(provider);
    final error = reauthError;
    if (error != null) throw error;
    return _FakeUserCredential(
      this,
      // ignore: invalid_use_of_protected_member
      additionalUserInfo: AdditionalUserInfo(
        isNewUser: false,
        providerId: 'apple.com',
        authorizationCode: appleAuthCode,
      ),
    );
  }

  @override
  Future<UserCredential> reauthenticateWithCredential(
    AuthCredential credential,
  ) async => _FakeUserCredential(this);

  /// Each `getIdToken` call's `forceRefresh` argument, in order.
  final List<bool> idTokenForceRefresh = [];

  @override
  bool emailVerified;

  final List<String> _events;
  final Exception? deleteError;

  /// How many `delete()` calls throw [deleteError]; null = every one.
  int? deleteFailures;

  @override
  String? get email => '$uid@example.com';

  @override
  Future<String?> getIdToken([bool forceRefresh = false]) async {
    idTokenForceRefresh.add(forceRefresh);
    return 'firebase-id-token';
  }

  @override
  Future<void> delete() async {
    _events.add('user.delete');
    final error = deleteError;
    final left = deleteFailures;
    if (error != null && (left == null || left > 0)) {
      if (left != null) deleteFailures = left - 1;
      throw error;
    }
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

class _FakeUserInfo implements UserInfo {
  _FakeUserInfo(this.providerId);

  @override
  final String providerId;

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
