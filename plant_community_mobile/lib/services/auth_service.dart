import 'dart:async';

import 'package:dio/dio.dart' show Options, Response;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../core/utils/log_redaction.dart';
import 'api_service.dart';
import 'push_registration_service.dart';
import 'user_profile_service.dart';

part 'auth_service.g.dart';

/// Authentication state for the application
class AuthState {
  final User? firebaseUser;
  final String? jwtToken;
  final bool isLoading;
  final String? error;

  /// True when [error] is the token exchange's 409 with code
  /// `unverified_account`: a Django account holds this email but never
  /// verified it, so the sign-in cannot link to it. The one conflict the user
  /// can clear, so the error offers a password reset link. Cleared with
  /// [error].
  final bool unverifiedAccountConflict;

  /// True when the Firebase account's email is not verified yet, so the
  /// backend refuses the token exchange (403, todos 447/449/660). No screen
  /// watches it: the sign-in and register screens show the "Check your
  /// email" panel from their call's return value, and the launch exchange
  /// only shows [emailNotVerifiedMessage], which reads without it. Cleared
  /// by [copyWith], like [unverifiedAccountConflict]: a successful exchange
  /// or a new attempt ends it.
  final bool emailVerificationRequired;

  /// True when the token exchange answered 428 `consent_required`: this
  /// Firebase account has no Django account yet, and the server creates one
  /// only with `accepted_terms: true`. The app root shows the consent sheet
  /// for it ([AuthService.acceptTermsAndRetry], [AuthService.declineTerms]).
  /// Not the unverified-email 403: the server checks that first. Cleared by
  /// [copyWith], like the flags above.
  final bool consentRequired;

  /// True with [consentRequired] when the 428 was `policy_update_required`:
  /// the account exists and must accept a changed Privacy Policy and Terms.
  /// The sheet words it as an update, and declining signs out without
  /// deleting anything.
  final bool policyUpdate;

  const AuthState({
    this.firebaseUser,
    this.jwtToken,
    this.isLoading = false,
    this.error,
    this.unverifiedAccountConflict = false,
    this.emailVerificationRequired = false,
    this.consentRequired = false,
    this.policyUpdate = false,
  });

  bool get isAuthenticated => jwtToken != null;

  AuthState copyWith({
    User? firebaseUser,
    String? jwtToken,
    bool? isLoading,
    String? error,
  }) {
    return AuthState(
      firebaseUser: firebaseUser ?? this.firebaseUser,
      jwtToken: jwtToken ?? this.jwtToken,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Shown for the 409 `unverified_account`: the address was registered on the
/// web and never confirmed, so sign-in will not link to it until its holder
/// proves the inbox (todo 446). Resetting the password, signing in on the web
/// and confirming the email unblocks it.
const accountConflictMessage =
    'An account with this email already exists and could not be linked to '
    'this sign-in. If it is yours, reset its password, sign in on the web '
    'and confirm your email, then try again.';

/// Any other 409: the email is tied to another sign-in, or held by several
/// accounts. A password reset would not help, so no link is offered.
const accountLinkFailedMessage =
    'This sign-in could not be linked to the existing account for this '
    'email.';

/// The token exchange's 403 for an unverified email (todo 660): the account
/// exists, and opening the link in the verification mail finishes the
/// sign-in. Client-side wording, not the backend's, so a backend rewording
/// cannot change what the user reads.
const emailNotVerifiedMessage =
    'Verify your email to finish signing in: open the link in the email we '
    'sent you.';

/// "I've verified" was tapped, but Firebase still reports the email
/// unverified.
const emailStillUnverifiedMessage =
    'Your email is not verified yet. Open the link in the email we sent, '
    'then try again.';

/// How [AuthService.freshIdTokenAfterReauth] proves it is still the account
/// holder before an account deletion (Plan B task 10).
enum ReauthMethod { google, password }

/// The re-auth method for an account with these linked sign-in methods
/// (`User.providerData` provider ids): `google.com` wins over `password`
/// when both are linked, since it needs no typing and works for an account
/// whose password the user never set or forgot. `null` for anything else
/// (no other provider is offered by this app).
ReauthMethod? reauthMethodFor(Iterable<String> providerIds) {
  final ids = providerIds.toSet();
  if (ids.contains(GoogleAuthProvider.PROVIDER_ID)) return ReauthMethod.google;
  if (ids.contains(EmailAuthProvider.PROVIDER_ID)) return ReauthMethod.password;
  return null;
}

/// Re-auth refused: the password did not match.
const reauthWrongPasswordMessage =
    'Incorrect password. Please try again.'; // pragma: allowlist secret

/// Re-auth refused: the Google account picked is not this account's.
const reauthWrongAccountMessage =
    "That's a different account. Choose the account you're deleting.";

/// Re-auth refused for a reason that is not a wrong password, e.g. a Google
/// credential Firebase would not accept.
const reauthNotConfirmedMessage = "Couldn't confirm it's you. Try again.";

/// The signed-in account has no sign-in method re-auth supports.
const reauthUnsupportedMessage =
    "We couldn't confirm it's you for this sign-in method. Contact support "
    'to delete your account.';

/// Current Firebase user id, or `null` when signed out.
///
/// Firestore (offline persistence + sync) is scoped by the Firebase uid, which
/// is available as soon as the Firebase user exists — independent of the Django
/// JWT exchange that gates [AuthState.isAuthenticated]. Consumers that persist
/// or read user-scoped data should watch this rather than the full auth state.
final currentUserIdProvider = Provider<String?>(
  (ref) => ref.watch(authServiceProvider).firebaseUser?.uid,
);

/// Authentication service that handles Firebase Auth + Django JWT
///
/// This service manages the complete authentication flow:
/// 1. User signs in/up with Firebase (email/password, Google, Apple)
/// 2. Get Firebase ID token
/// 3. Exchange with Django backend → receive JWT
/// 4. Store JWT in secure storage
/// 5. Inject JWT into ApiService for all requests
///
/// Usage:
/// ```dart
/// final authService = ref.read(authServiceProvider.notifier);
///
/// // Sign in
/// await authService.signInWithEmailPassword('email@example.com', 'password');
///
/// // Check auth state
/// final authState = ref.watch(authServiceProvider);
/// if (authState.isAuthenticated) {
///   // User is logged in
/// }
/// ```
@riverpod
class AuthService extends _$AuthService {
  // Harness: test/services/auth_service_test.dart (todo 288, closed 2026-07-31)
  // pins this notifier's three push-registration wiring points —
  // syncAfterLogin() after a successful JWT exchange, clearOnLogout() in
  // signOut(), detach() on a signed-out auth state — plus their ORDER
  // (clearOnLogout must precede the Firebase sign-out that invalidates the
  // JWT it needs), the _authGeneration epoch guard, and the session-expiry
  // exemption for signOut()'s own FCM-clear PATCH (ApiService
  // .skipSessionExpiryKey, see _handleSessionExpired). Every one of those was
  // verified to fail the suite when removed, so treat a red test here as a
  // real regression, not harness noise.
  //
  // Protected getter allows test subclasses to inject a mock FirebaseAuth
  // without triggering Firebase.initializeApp() at construction time.
  @visibleForTesting
  FirebaseAuth get firebaseAuth => FirebaseAuth.instance;
  FirebaseAuth get _firebaseAuth => firebaseAuth;
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  static const String _jwtKey = 'django_jwt_token';
  static const String _refreshTokenKey = 'django_refresh_token';

  /// The Firebase uid whose owner ticked the sign-up consent box on this
  /// device. The exchange sends `accepted_terms: true` only for that uid, so
  /// an email sign-up verified days later still carries its consent. Deleted
  /// after a successful exchange and by [declineTerms]; never by [_clearJWT].
  static const String _acceptedTermsKey = 'accepted_terms_uid';

  /// Covers a consenting Google sign-in before its uid is known: the
  /// listener's exchange can start before [signInWithGoogle] stores it. Set
  /// for the duration of that call only.
  bool _acceptedTermsPending = false;

  /// The Firebase uid whose exchange the server refused with 428. Only that
  /// user's Firebase account is deleted by [declineTerms]: the signed-in user
  /// may have changed since the sheet opened.
  String? _consentRefusedUid;

  /// Whether that refusal was `policy_update_required`: an existing account,
  /// whose Firebase login [declineTerms] must never delete.
  bool _consentRefusedIsUpdate = false;

  /// [acceptTermsAndRetry] is running: a second tap sends nothing.
  bool _consentRetryInFlight = false;

  // Store StreamSubscription to prevent memory leak
  StreamSubscription<User?>? _authStateSubscription;
  String? _pendingSignedOutMessage;
  int _authGeneration = 0;

  /// The [_authGeneration] signOut() opened. A token refresh in that
  /// generation is serving the sign-out's own FCM clear, so it installs the
  /// token for the clear's re-send and does nothing else: no signed-in state,
  /// no push registration that would undo the clear (todo 500 finding 3,
  /// owner decision 2026-10-10: a generation, not a flag). The next sign-in's
  /// exchange bumps the generation past it, so it needs no reset.
  int _signOutGeneration = -1;

  /// The [_authGeneration] whose login already ran its one-time completion
  /// (push registration, the profile re-fetch). The launch exchange and a
  /// refresh that lands while it runs share a generation, and only the first
  /// of them completes the login (todo 500 finding 3).
  int _loginCompletedGeneration = -1;

  @override
  AuthState build() {
    // Initialize with current Firebase user
    final currentUser = _firebaseAuth.currentUser;
    final apiService = ref.read(apiServiceProvider);

    apiService.setSessionExpiredHandler(_handleSessionExpired);
    apiService.setAccessTokenRefresher(_refreshAccessToken);

    // Listen to Firebase auth state changes
    // Store subscription so we can cancel it on disposal
    _authStateSubscription = _firebaseAuth.authStateChanges().listen(
      (user) async {
        if (kDebugMode) {
          debugPrint(
            '[AUTH] Firebase auth state changed: ${redactEmail(user?.email)}',
          );
        }

        if (user != null) {
          // User signed in → exchange token
          await _exchangeFirebaseTokenForJWT(user);
        } else {
          // User signed out → clear JWT
          // Stop FCM token-rotation re-registration on every signed-out path
          // (covers session expiry and external sign-outs; idempotent after
          // signOut()'s own clearOnLogout). No network call (todo 253 slice 6).
          ref.read(pushRegistrationServiceProvider).detach();
          _authGeneration++;
          // Before the await, so the API session ends with the generation.
          ref.read(apiServiceProvider).setAuthToken(null);
          await _clearJWT();
          final signedOutMessage = _pendingSignedOutMessage;
          _pendingSignedOutMessage = null;
          // An external sign-out (a revoked token, a disabled account) ends
          // the session too, so it forgets whose account this was, in the
          // same frame as the auth flip (todo 558 finding 2).
          _clearAccountProfile();
          state = AuthState(error: signedOutMessage);
        }
      },
      // A platform error on the stream must not become an unhandled zone
      // error (todo 500 finding 11); the next event still arrives.
      onError: (Object error) {
        if (kDebugMode) {
          debugPrint('[AUTH ERROR] Firebase auth state stream error: $error');
        }
      },
    );

    // Cancel subscription when provider is disposed to prevent memory leak
    ref.onDispose(() {
      if (kDebugMode) {
        debugPrint('[AUTH] Cancelling auth state subscription');
      }
      _authStateSubscription?.cancel();
      apiService.setSessionExpiredHandler(null);
      apiService.setAccessTokenRefresher(null);
    });

    // If user is already signed in, exchange token
    if (currentUser != null) {
      _exchangeFirebaseTokenForJWT(currentUser);
    }

    return AuthState(firebaseUser: currentUser);
  }

  /// Sign in with email and password.
  ///
  /// Returns true when the account's email is not verified yet: the backend
  /// will refuse the token exchange, so the caller shows the "Check your
  /// email" panel instead of leaving the sign-in screen (todo 660).
  ///
  /// When this account was ALREADY the Firebase user (an earlier exchange
  /// failed, typically on the unverified-email 403, and left it signed in to
  /// Firebase), signing in again changes no uid, so `authStateChanges` fires
  /// nothing and the listener never retries. The exchange runs here instead,
  /// with a forced token refresh, so a cached `email_verified=false` token is
  /// not sent again (todo 660).
  ///
  /// Throws [AuthException] if sign in fails
  Future<bool> signInWithEmailPassword(String email, String password) async {
    try {
      state = state.copyWith(isLoading: true, error: null);

      if (kDebugMode) {
        debugPrint('[AUTH] Signing in with email: ${redactEmail(email)}');
      }

      final previousUid = _firebaseAuth.currentUser?.uid;
      final credential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      final user = credential.user;

      if (kDebugMode) {
        debugPrint(
          '[AUTH] Firebase sign in successful: ${redactEmail(user?.email)}',
        );
      }

      final needsVerification = user != null && !user.emailVerified;
      state = AuthState(
        firebaseUser: user,
        isLoading: false,
        emailVerificationRequired: needsVerification,
      );

      if (user != null && !needsVerification && previousUid == user.uid) {
        // Same uid: no auth-state event is coming, so exchange here.
        await _exchangeFirebaseTokenForJWT(user, forceRefresh: true);
        if (!state.isAuthenticated) {
          if (state.emailVerificationRequired) return true;
          // The root's consent sheet takes it from here.
          if (state.consentRequired) return false;
          // Otherwise the screen would dismiss onto a signed-out Profile
          // with the failure unseen (todo 660 review).
          throw AuthException(
            state.error ?? 'Sign in failed. Please try again.',
          );
        }
      }
      // Otherwise the auth state listener handles the token exchange.
      return needsVerification;
    } on AuthException {
      rethrow;
    } on FirebaseAuthException catch (e) {
      final errorMessage = _handleFirebaseAuthException(e);
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    } catch (e) {
      final errorMessage = 'Sign in failed: ${e.toString()}';
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    }
  }

  /// Sign in with Google.
  ///
  /// The backend (`firebase_auth_views.py`) refuses a Firebase token whose
  /// `email_verified` claim is false, whatever the provider (todo 447 item 8),
  /// with 403 "Email address must be verified before logging in.", even for a
  /// uid already bound to an account (todo 449). Firebase marks a Google email
  /// verified, so this path completes at once. An email/password account
  /// completes only after its holder opens the verification mail
  /// [registerWithEmailPassword] sends, then taps "I've verified"
  /// ([confirmEmailVerified]) or signs in again (todo 660).
  ///
  /// It also LINKS rather than duplicating: the exchange falls back to matching
  /// on email and backfills `firebase_uid` onto the existing Django user
  /// (`get_or_create_user_from_firebase`), so an account created by the web
  /// app's Google OAuth button keeps its data.
  ///
  /// No `clientId` is passed to [GoogleSignIn.initialize]: on iOS the plugin
  /// reads `GIDClientID` from `Info.plist`, which is populated from the
  /// committed `GoogleService-Info.plist`. Passing it here as well would
  /// duplicate a value that already has one home.
  ///
  /// [acceptedTerms] is true only from the register screen with the consent
  /// box ticked. It makes the first exchange send `accepted_terms: true`, so
  /// a new Google user gets an account without the consent sheet.
  Future<void> signInWithGoogle({bool acceptedTerms = false}) async {
    if (acceptedTerms) _acceptedTermsPending = true;
    try {
      state = state.copyWith(isLoading: true, error: null);

      // `initialize` must complete exactly once before any other call, and
      // calling it twice is explicitly undefined behaviour in google_sign_in
      // 7.x -- hence the latch rather than an unguarded call per sign-in.
      await _ensureGoogleInitialized();

      final account = await googleSignIn.authenticate();
      final idToken = account.authentication.idToken;

      // google_sign_in 7.x exposes ONLY idToken on GoogleSignInAuthentication
      // (accessToken moved to the authorization client). Firebase accepts an
      // idToken-only credential, but a null one would surface from
      // `signInWithCredential` as an opaque internal error, so name it here.
      if (idToken == null) {
        throw AuthException(
          'Google did not return an ID token. On Android this usually means '
          'the app\'s signing certificate is not registered with Firebase.',
        );
      }

      final credential = GoogleAuthProvider.credential(idToken: idToken);
      final result = await _firebaseAuth.signInWithCredential(credential);
      final signedIn = result.user;
      if (acceptedTerms && signedIn != null) {
        await _secureStorage.write(key: _acceptedTermsKey, value: signedIn.uid);
      }

      if (kDebugMode) {
        debugPrint(
          '[AUTH] Google sign in successful: '
          '${redactEmail(result.user?.email)}',
        );
      }

      // Auth state listener handles the token exchange, as for email/password.
      // It can finish before this line: then its JWT or its consent refusal
      // stands, and only the spinner goes.
      if (state.isAuthenticated || state.consentRequired) {
        state = _notLoading(state);
      } else {
        state = AuthState(firebaseUser: result.user, isLoading: false);
      }
    } on GoogleSignInException catch (e) {
      // A cancel is a normal outcome, not a failure: leaving an error on state
      // would surface a red banner via main.dart's root listener for a user who
      // simply changed their mind.
      if (e.code == GoogleSignInExceptionCode.canceled) {
        state = state.copyWith(isLoading: false, error: null);
        return;
      }
      final message = 'Google sign in failed: ${e.description ?? e.code.name}';
      state = state.copyWith(isLoading: false, error: message);
      throw AuthException(message);
    } on FirebaseAuthException catch (e) {
      final errorMessage = _handleFirebaseAuthException(e);
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    } on AuthException {
      state = state.copyWith(isLoading: false);
      rethrow;
    } catch (e) {
      final errorMessage = 'Google sign in failed: $e';
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    } finally {
      _acceptedTermsPending = false;
    }
  }

  /// How [freshIdTokenAfterReauth] will re-authenticate the current Firebase
  /// user, or `null` when signed out or no supported method is linked. The
  /// delete screen reads it first, to ask for a password only when one is
  /// needed.
  ReauthMethod? get reauthMethod {
    final user = _firebaseAuth.currentUser;
    if (user == null) return null;
    return reauthMethodFor(user.providerData.map((info) => info.providerId));
  }

  /// Re-authenticate the current Firebase user and return a FORCED fresh ID
  /// token, whose `auth_time` is now: the account-deletion endpoint accepts
  /// only a sign-in younger than 300 s (Plan B task 10).
  ///
  /// Picks the credential with [reauthMethod]: a fresh Google
  /// `authenticate()` when `google.com` is linked (preferred, [password]
  /// ignored), else `EmailAuthProvider.credential(email, password)`.
  ///
  /// Throws [ReauthCancelledException] when the user backs out (the Google
  /// sheet closed, no password given), and [AuthException] with a readable
  /// message for any other failure. It never touches [state]: the delete
  /// screen shows the error itself, and an error on state would also put up
  /// main.dart's root SnackBar. Re-authenticating keeps the uid, so no
  /// auth-state event fires and no token exchange runs.
  Future<String> freshIdTokenAfterReauth({String? password}) async {
    final user = _firebaseAuth.currentUser;
    if (user == null) {
      throw AuthException('Sign in again to delete your account.');
    }
    final method = reauthMethod;
    final AuthCredential credential;
    switch (method) {
      case ReauthMethod.google:
        credential = await _freshGoogleCredential();
      case ReauthMethod.password:
        final email = user.email;
        if (password == null || password.isEmpty) {
          throw ReauthCancelledException();
        }
        if (email == null) throw AuthException(reauthUnsupportedMessage);
        credential = EmailAuthProvider.credential(
          email: email,
          password: password,
        );
      case null:
        throw AuthException(reauthUnsupportedMessage);
    }

    try {
      await user.reauthenticateWithCredential(credential);
      final token = await user.getIdToken(true);
      if (token == null) {
        throw AuthException(
          'Could not confirm your sign-in. Please try again.',
        );
      }
      return token;
    } on FirebaseAuthException catch (e) {
      if (kDebugMode) debugPrint('[AUTH] Re-auth refused: ${e.code}');
      throw AuthException(switch (e.code) {
        'wrong-password' || 'invalid-credential'
            when method == ReauthMethod.password =>
          reauthWrongPasswordMessage,
        'wrong-password' || 'invalid-credential' => reauthNotConfirmedMessage,
        'user-mismatch' => reauthWrongAccountMessage,
        _ => _handleFirebaseAuthException(e),
      });
    }
  }

  /// A Google credential from a fresh account pick, reusing the sign-in's
  /// one-time `initialize`.
  Future<AuthCredential> _freshGoogleCredential() async {
    try {
      await _ensureGoogleInitialized();
      final account = await googleSignIn.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null) {
        throw AuthException('Google did not return an ID token.');
      }
      return GoogleAuthProvider.credential(idToken: idToken);
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        throw ReauthCancelledException();
      }
      throw AuthException(
        'Google sign in failed: ${e.description ?? e.code.name}',
      );
    }
  }

  /// Overridable for tests; the plugin exposes only a singleton.
  @visibleForTesting
  GoogleSignIn get googleSignIn => GoogleSignIn.instance;

  Future<void> _ensureGoogleInitialized() async {
    if (_googleInitialized) return;
    await googleSignIn.initialize();
    _googleInitialized = true;
  }

  bool _googleInitialized = false;

  /// Register new user with email and password, and send the verification
  /// mail.
  ///
  /// Returns true when the new account still has to verify its email, which
  /// is always the case for a fresh email/password account: the backend
  /// refuses its token until then (403), so the caller shows the "Check your
  /// email" panel rather than leaving the screen (todo 660). A failed send
  /// does not fail the registration (the account exists); the panel's Resend
  /// tries again.
  ///
  /// Throws [AuthException] if registration fails
  Future<bool> registerWithEmailPassword({
    required String email,
    required String password,
    required String displayName,
  }) async {
    try {
      state = state.copyWith(isLoading: true, error: null);

      if (kDebugMode) {
        debugPrint('[AUTH] Registering new user: ${redactEmail(email)}');
      }

      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      // The register screen calls this only with the consent box ticked.
      final created = credential.user;
      if (created != null) {
        await _secureStorage.write(key: _acceptedTermsKey, value: created.uid);
      }

      // Update display name
      await credential.user?.updateDisplayName(displayName);
      await credential.user?.reload();

      if (kDebugMode) {
        debugPrint(
          '[AUTH] User registered: ${redactEmail(credential.user?.email)}',
        );
      }

      final user = _firebaseAuth.currentUser ?? credential.user;
      final needsVerification = user != null && !user.emailVerified;
      if (user != null && needsVerification) {
        try {
          await user.sendEmailVerification();
        } catch (e) {
          if (kDebugMode) {
            debugPrint('[AUTH ERROR] Verification email not sent: $e');
          }
        }
      }

      // Auth state listener will handle token exchange (it is refused with
      // the 403 until the email is verified).
      state = AuthState(
        firebaseUser: user,
        isLoading: false,
        emailVerificationRequired: needsVerification,
      );
      return needsVerification;
    } on FirebaseAuthException catch (e) {
      final errorMessage = _handleFirebaseAuthException(e);
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    } catch (e) {
      final errorMessage = 'Registration failed: ${e.toString()}';
      state = state.copyWith(isLoading: false, error: errorMessage);
      throw AuthException(errorMessage);
    }
  }

  /// Send the verification mail again to the current Firebase user.
  ///
  /// Throws [AuthException] when there is no Firebase user or Firebase
  /// refuses (e.g. `too-many-requests`).
  Future<void> resendVerificationEmail() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) {
      throw AuthException('Sign in again to resend the verification email.');
    }
    try {
      await user.sendEmailVerification();
    } on FirebaseAuthException catch (e) {
      throw AuthException(_handleFirebaseAuthException(e));
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Resend failed: $e');
      throw AuthException(
        'Could not send the verification email. Please try again.',
      );
    }
  }

  /// "I've verified": reload the Firebase user and, once its email reads as
  /// verified, run the token exchange with a FORCED token refresh, so the
  /// cached `email_verified=false` ID token is not sent again (todo 660).
  ///
  /// Returns true when the exchange signed the user in. When Firebase still
  /// reports the email unverified, sets [emailStillUnverifiedMessage] and
  /// sends nothing to the backend. Throws [AuthException] only when the
  /// reload itself fails.
  Future<bool> confirmEmailVerified() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) {
      throw AuthException('Sign in again to finish verifying your email.');
    }
    try {
      await user.reload();
    } on FirebaseAuthException catch (e) {
      throw AuthException(_handleFirebaseAuthException(e));
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Reload failed: $e');
      throw AuthException(
        'Could not check your email status. Please try again.',
      );
    }
    // reload() refreshes the current user; read it again rather than trust
    // the instance held before the call.
    final refreshed = _firebaseAuth.currentUser;
    if (refreshed == null || refreshed.uid != user.uid) return false;
    if (!refreshed.emailVerified) {
      state = AuthState(
        firebaseUser: refreshed,
        error: emailStillUnverifiedMessage,
        emailVerificationRequired: true,
      );
      return false;
    }
    await _exchangeFirebaseTokenForJWT(refreshed, forceRefresh: true);
    return state.isAuthenticated;
  }

  /// Sign out current user
  Future<void> signOut() async {
    try {
      if (kDebugMode) {
        debugPrint('[AUTH] Signing out user');
      }

      // Bump FIRST: an in-flight token exchange must die at its next
      // generation check, or it could complete during the clear below and
      // fire a fresh push registration that undoes it (slice-6 review). The
      // new generation is the sign-out's own: a refresh the clear's 401
      // starts in it only re-sends the clear (todo 500 finding 3).
      _signOutGeneration = ++_authGeneration;
      // And end the API session now, not at the setAuthToken(null) below: a
      // refresh that finishes during the clear is overtaken by this sign-out
      // and must not report "Your session expired" (todo 498). The token
      // stays set, because the clear still needs it.
      ref.read(apiServiceProvider).endSession();

      // Clear the FCM token server-side BEFORE Firebase sign-out — the PATCH
      // needs the still-valid JWT. Best-effort with an internal timeout; it
      // never throws, so it cannot block or fail sign-out (todo 253 slice 6).
      await ref.read(pushRegistrationServiceProvider).clearOnLogout();

      await _firebaseAuth.signOut();
      await _clearJWT();

      // Clear API service token
      ref.read(apiServiceProvider).setAuthToken(null);

      state = const AuthState();

      if (kDebugMode) {
        debugPrint('[AUTH] Sign out successful');
      }
    } catch (e) {
      final errorMessage = 'Sign out failed: ${e.toString()}';
      state = state.copyWith(error: errorMessage);
      throw AuthException(errorMessage);
    }
  }

  /// Exchange Firebase ID token for Django JWT
  ///
  /// This is called automatically when user signs in.
  ///
  /// [forceRefresh] fetches a new Firebase ID token instead of the cached
  /// one. It is also forced whenever the user's email reads as unverified:
  /// the cached token would carry `email_verified=false` until it expires
  /// (about an hour) even after the link was opened, so a relaunch would get
  /// the same 403 again (todo 660).
  Future<void> _exchangeFirebaseTokenForJWT(
    User user, {
    bool forceRefresh = false,
  }) async {
    final exchangeGeneration = ++_authGeneration;
    final apiService = ref.read(apiServiceProvider);

    try {
      if (kDebugMode) {
        debugPrint('[AUTH] Exchanging Firebase token for Django JWT');
      }

      // Prevent a newly signed-in user from inheriting stale bearer tokens if
      // the exchange fails or is superseded by sign-out/user-switch events.
      apiService.setAuthToken(null);
      await _clearJWT();

      // Get Firebase ID token
      final firebaseToken = await user.getIdToken(
        forceRefresh || !user.emailVerified,
      );

      if (firebaseToken == null) {
        throw AuthException('Failed to get Firebase ID token');
      }

      final body = await _exchangeBody(user, firebaseToken);

      if (!_isCurrentExchange(user, exchangeGeneration)) {
        if (kDebugMode) {
          debugPrint('[AUTH] Ignoring token exchange after user changed');
        }
        return;
      }

      // Call Django backend to exchange token. Send ONLY the Firebase ID token
      // (plus the consent flag) — the backend derives email/display name from
      // the cryptographically verified token, never from client-supplied
      // fields.
      final response = await apiService.post(
        '/auth/firebase-token-exchange/',
        data: body,
        // A 401 here is the Firebase token being refused: refreshing would
        // only repeat this same exchange (todo 462).
        options: Options(extra: {ApiService.skipAuthRefreshKey: true}),
      );

      // Extract JWT tokens from response
      final jwtToken = response.data['access_token'] as String?;
      final refreshToken = response.data['refresh_token'] as String?;

      if (jwtToken == null) {
        throw AuthException('No JWT token in response');
      }

      if (!_isCurrentExchange(user, exchangeGeneration)) {
        if (kDebugMode) {
          debugPrint(
            '[AUTH] Ignoring token exchange for signed-out or changed user',
          );
        }
        return;
      }

      // Store tokens securely
      await _secureStorage.write(key: _jwtKey, value: jwtToken);
      if (refreshToken != null) {
        await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);
      }

      if (!_isCurrentExchange(user, exchangeGeneration)) {
        if (kDebugMode) {
          debugPrint('[AUTH] Clearing tokens from superseded token exchange');
        }
        await _clearJWTIfMatches(jwtToken, refreshToken);
        return;
      }

      // Update ApiService with new token. The setAuthToken(null) above
      // opened this user's session; the JWT completes it rather than starting
      // another, so a request sent in between still re-sends with it (todo
      // 498).
      apiService.replaceAuthToken(jwtToken);

      // Update state
      state = state.copyWith(firebaseUser: user, jwtToken: jwtToken);

      _completeLogin(exchangeGeneration);

      if (kDebugMode) {
        debugPrint('[AUTH] JWT token exchange successful');
      }
      // The account exists now; the consent has done its job.
      await _forgetAcceptedTerms();
    } on ApiException catch (e) {
      if (!_isCurrentExchange(user, exchangeGeneration)) {
        if (kDebugMode) {
          debugPrint(
            '[AUTH ERROR] Ignoring stale token exchange failure: ${e.message}',
          );
        }
        return;
      }

      if (kDebugMode) {
        debugPrint('[AUTH ERROR] Token exchange failed: ${e.message}');
      }

      // Re-checked after every await: once overtaken, a newer exchange may
      // already hold its own tokens, bearer and state (todo 607 item 2).
      if (!await _clearJWTWhileCurrent(user, exchangeGeneration)) return;
      apiService.setAuthToken(null);

      // Don't throw - allow user to stay signed in to Firebase. For the
      // unverified-email 403 that is what lets "I've verified" and a second
      // sign-in retry the exchange (todo 660).
      final unverified = e.statusCode == 409 && e.code == 'unverified_account';
      // An address blocked from sign-up (ruling R3): the server's own
      // message says so, and verifying the email would not help.
      final blocked =
          e.statusCode == 403 && e.code == 'signup_blocked' && !e.unstructured;
      // Any other view's own JSON 403 means an unverified email; a proxy's
      // HTML 403 says nothing about this account (todo 500 finding 8).
      final emailUnverified =
          e.statusCode == 403 && !e.unstructured && !blocked;
      // A new account without consent: the root's sheet asks for it, so no
      // error SnackBar goes under it.
      // An existing account asked to accept a changed policy opens the same
      // sheet, worded as an update.
      final policyUpdate = _isPolicyUpdateRefusal(e);
      final consent = _isConsentRefusal(e) || policyUpdate;
      if (consent) {
        _consentRefusedUid = user.uid;
        _consentRefusedIsUpdate = policyUpdate;
      }
      state = AuthState(
        firebaseUser: _firebaseAuth.currentUser,
        error: consent
            ? null
            : blocked
            ? e.message
            : emailUnverified
            ? emailNotVerifiedMessage
            : unverified
            ? accountConflictMessage
            : e.statusCode == 409
            ? accountLinkFailedMessage
            : 'Failed to connect to server. Some features may be unavailable.',
        unverifiedAccountConflict: unverified,
        emailVerificationRequired: emailUnverified,
        consentRequired: consent,
        policyUpdate: policyUpdate,
      );
    } catch (e) {
      if (!_isCurrentExchange(user, exchangeGeneration)) {
        if (kDebugMode) {
          debugPrint('[AUTH ERROR] Ignoring stale token exchange failure: $e');
        }
        return;
      }

      if (kDebugMode) {
        debugPrint('[AUTH ERROR] Token exchange failed: $e');
      }

      if (!await _clearJWTWhileCurrent(user, exchangeGeneration)) return;
      apiService.setAuthToken(null);

      state = AuthState(
        firebaseUser: _firebaseAuth.currentUser,
        error: 'Authentication error. Please try again.',
      );
    }
  }

  /// Once per login: register this device's FCM token with the forum
  /// profile, and fetch this account's profile, not the one a mounted screen
  /// still holds from before the sign-out (todo 520). A refresh that already
  /// completed this generation's login (a 401 while the launch exchange ran)
  /// has done both, and a second sync would PATCH twice (todo 500).
  void _completeLogin(int generation) {
    if (_loginCompletedGeneration == generation) return;
    _loginCompletedGeneration = generation;
    // Fire-and-forget: syncAfterLogin catches everything internally, so a
    // push-registration failure can never break login (todo 253 slice 6).
    unawaited(ref.read(pushRegistrationServiceProvider).syncAfterLogin());
    _refetchAccountProfile();
  }

  bool _isCurrentExchange(User user, int exchangeGeneration) {
    return _authGeneration == exchangeGeneration &&
        _firebaseAuth.currentUser?.uid == user.uid;
  }

  Future<void> _clearJWTIfMatches(
    String accessToken,
    String? refreshToken,
  ) async {
    final storedAccessToken = await _secureStorage.read(key: _jwtKey);
    if (storedAccessToken == accessToken) {
      await _secureStorage.delete(key: _jwtKey);
    }

    if (refreshToken != null) {
      final storedRefreshToken = await _secureStorage.read(
        key: _refreshTokenKey,
      );
      if (storedRefreshToken == refreshToken) {
        await _secureStorage.delete(key: _refreshTokenKey);
      }
    }
  }

  /// Firebase error codes that mean the account itself is gone or its
  /// sign-in revoked: signing in again is the only way on. Every other code
  /// (`network-request-failed`, `too-many-requests`, `internal-error`, ...)
  /// may pass, so it keeps the user signed in (todo 498).
  static const Set<String> _firebaseRefusalCodes = {
    'user-disabled',
    'user-not-found',
    'user-token-expired',
    'invalid-user-token',
  };

  /// Token-exchange statuses that refuse the session outright: an invalid,
  /// expired or unverified Firebase token (401/403), and only when the body
  /// is the view's own JSON (see [_refreshAccessToken]).
  ///
  /// Deliberately not here (todo 500):
  /// * 409, an account that cannot be linked. The launch exchange keeps the
  ///   user signed in to Firebase for it, with the conflict on screen, so a
  ///   refresh does the same rather than replace it with "session expired"
  ///   (owner decision 2026-10-10).
  /// * 400/404/405 and every 5xx/429: a client or deployment bug, or an
  ///   outage. Signing out would not fix any of them, so they stay
  ///   transient, and each 401 tries again.
  static const Set<int> _exchangeRefusalStatuses = {401, 403};

  /// Get a fresh Django access token after a 401, without signing out.
  ///
  /// Re-exchanges the current Firebase ID token, as launch does (owner
  /// decision on todo 462): `getIdToken()` hands back a refreshed Firebase
  /// token when the cached one has expired.
  ///
  /// Returns the new access token, or `null` only when the session is
  /// refused ([_firebaseRefusalCodes], [_exchangeRefusalStatuses]), which
  /// signs the user out. Throws [RefreshSupersededException] when it was
  /// overtaken (no Firebase user any more, a different one, or a newer
  /// generation): `null` there would sign out whoever is current, the new
  /// user B included (todo 500 finding 2). It THROWS anything else for a
  /// failure that may pass (offline, timeout, 5xx, 429, no Firebase token
  /// handed back, a 409 account conflict), which keeps the user signed in:
  /// "Users expect to stay logged in" (owner decision on todo 498).
  ///
  /// Deliberately NOT [_exchangeFirebaseTokenForJWT]: that one bumps
  /// [_authGeneration], clears the stored tokens and the bearer up front (so
  /// requests queued behind the refresh would go out anonymous) and re-runs
  /// push registration, which a token refresh does only when it is what
  /// completes the login (below).
  Future<String?> _refreshAccessToken() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) {
      // Signed out under the request: the auth-state listener is clearing
      // up, and there is no one left to sign out.
      throw const RefreshSupersededException();
    }
    final generation = _authGeneration;

    final String? firebaseToken;
    try {
      firebaseToken = await user.getIdToken();
    } on FirebaseAuthException catch (e) {
      // Overtaken first, as the exchange's ApiException branch below does: a
      // refusal for A after Firebase switched to B must not sign B out (todo
      // 567 finding 2).
      if (!_isCurrentExchange(user, generation)) {
        throw const RefreshSupersededException();
      }
      if (_firebaseRefusalCodes.contains(e.code)) {
        if (kDebugMode) {
          debugPrint('[AUTH] Access token refresh refused: ${e.code}');
        }
        return null;
      }
      rethrow;
    }
    if (!_isCurrentExchange(user, generation)) {
      throw const RefreshSupersededException();
    }
    if (firebaseToken == null) {
      throw AuthException('Firebase returned no ID token');
    }
    final body = await _exchangeBody(user, firebaseToken);
    if (!_isCurrentExchange(user, generation)) {
      throw const RefreshSupersededException();
    }

    final Response<dynamic> response;
    try {
      response = await ref
          .read(apiServiceProvider)
          .post(
            '/auth/firebase-token-exchange/',
            data: body,
            // The exchange IS the refresh: a 401 on it must neither refresh
            // again nor sign out on its own. The original request's refused
            // recovery signs out, exactly once. And it goes out with no
            // bearer: the view trusts only the Firebase token and runs no
            // authenticator, so the expired one would only ride along.
            options: Options(
              extra: {
                ApiService.skipAuthRefreshKey: true,
                ApiService.skipSessionExpiryKey: true,
                ApiService.omitAuthHeaderKey: true,
              },
            ),
          );
    } on ApiException catch (e) {
      if (!_isCurrentExchange(user, generation)) {
        throw const RefreshSupersededException();
      }
      // A refusal is the view's own JSON answer. A 401/403 page from a proxy
      // or a WAF says nothing about this account (todo 500 finding 8).
      if (_exchangeRefusalStatuses.contains(e.statusCode) && !e.unstructured) {
        if (kDebugMode) {
          debugPrint('[AUTH] Access token refresh refused: ${e.statusCode}');
        }
        return null;
      }
      if (e.statusCode == 409) {
        await _surfaceAccountConflict(user, generation, e);
      }
      final policyUpdate = _isPolicyUpdateRefusal(e);
      if (_isConsentRefusal(e) || policyUpdate) {
        // As for a 409: stay signed in to Firebase, and let the root's
        // consent sheet ask. Transient for the request that asked.
        if (await _clearJWTWhileCurrent(user, generation)) {
          _consentRefusedUid = user.uid;
          _consentRefusedIsUpdate = policyUpdate;
          state = AuthState(
            firebaseUser: user,
            consentRequired: true,
            policyUpdate: policyUpdate,
          );
        }
      }
      rethrow;
    }
    final data = response.data;
    final jwtToken = data is Map ? data['access_token'] : null;
    final refreshToken = data is Map ? data['refresh_token'] : null;
    if (!_isCurrentExchange(user, generation)) {
      throw const RefreshSupersededException();
    }
    if (jwtToken is! String) {
      throw AuthException('The sign-in server sent an unexpected response.');
    }

    final storedRefresh = refreshToken is String ? refreshToken : null;
    await _secureStorage.write(key: _jwtKey, value: jwtToken);
    if (storedRefresh != null) {
      await _secureStorage.write(key: _refreshTokenKey, value: storedRefresh);
    }
    if (!_isCurrentExchange(user, generation)) {
      await _clearJWTIfMatches(jwtToken, storedRefresh);
      throw const RefreshSupersededException();
    }

    // Same user, same session: the requests waiting on this refresh re-send
    // with it (todo 498).
    ref.read(apiServiceProvider).replaceAuthToken(jwtToken);
    if (generation == _signOutGeneration) {
      // signOut()'s FCM clear 401'd and this refresh serves its re-send.
      // Marking the user signed in, or registering push, would undo the
      // sign-out it serves (todo 500 finding 3).
      return jwtToken;
    }
    // The launch exchange failed (or is still running) and this refresh is
    // what signed the user in, so it is also the login that registers push
    // (todo 498) and fetches the account profile again (todo 520), once per
    // generation. A same-session refresh is neither: the profile a screen
    // holds is still this account's.
    final completesLogin = state.jwtToken == null;
    state = state.copyWith(firebaseUser: user, jwtToken: jwtToken);
    unawaited(_forgetAcceptedTerms());
    if (completesLogin) {
      _completeLogin(generation);
    }
    if (kDebugMode) {
      debugPrint('[AUTH] Access token refreshed');
    }
    return jwtToken;
  }

  /// The token-exchange body. `accepted_terms` (the JSON boolean `true`, the
  /// only value the server counts) goes only when this device holds the
  /// current user's consent: a consenting Google sign-in still in flight, or
  /// the stored uid matching. An existing user never needs it, and the server
  /// ignores it for one.
  Future<Map<String, dynamic>> _exchangeBody(User user, String token) async {
    // Read before the await: the Google sign-in clears it in `finally`.
    final pending = _acceptedTermsPending;
    String? storedUid;
    try {
      storedUid = await _secureStorage.read(key: _acceptedTermsKey);
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Consent read failed: $e');
    }
    final accepted = pending || _acceptedTermsPending || storedUid == user.uid;
    return {'firebase_token': token, if (accepted) 'accepted_terms': true};
  }

  /// [s] with `isLoading` false and every other field kept ([AuthState.copyWith]
  /// drops the flags and the error).
  static AuthState _notLoading(AuthState s) => AuthState(
    firebaseUser: s.firebaseUser,
    jwtToken: s.jwtToken,
    error: s.error,
    unverifiedAccountConflict: s.unverifiedAccountConflict,
    emailVerificationRequired: s.emailVerificationRequired,
    consentRequired: s.consentRequired,
  );

  static bool _isConsentRefusal(ApiException e) =>
      e.statusCode == 428 && e.code == 'consent_required';

  /// The 428 for an account that exists and has not accepted the current
  /// policy version. Its own code, so [declineTerms] can tell it apart.
  static bool _isPolicyUpdateRefusal(ApiException e) =>
      e.statusCode == 428 && e.code == 'policy_update_required';

  Future<void> _forgetAcceptedTerms() async {
    try {
      await _secureStorage.delete(key: _acceptedTermsKey);
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Consent delete failed: $e');
    }
  }

  /// "Continue" on the consent sheet: record the current user's consent and
  /// run the exchange again, now with `accepted_terms: true`. A call while
  /// one is still running sends nothing.
  Future<void> acceptTermsAndRetry() async {
    if (_consentRetryInFlight) return;
    final user = _firebaseAuth.currentUser;
    if (user == null) return;
    _consentRetryInFlight = true;
    try {
      await _secureStorage.write(key: _acceptedTermsKey, value: user.uid);
      state = AuthState(firebaseUser: user);
      await _exchangeFirebaseTokenForJWT(user);
    } catch (e) {
      // The exchange catches its own failures; this is the storage write.
      if (kDebugMode) debugPrint('[AUTH ERROR] Consent retry failed: $e');
      state = AuthState(
        firebaseUser: _firebaseAuth.currentUser,
        error: 'Something went wrong. Please try again.',
      );
    } finally {
      _consentRetryInFlight = false;
    }
  }

  /// "Cancel" on the consent sheet, or closing it any other way: no account
  /// is created, so the Firebase user made for it goes too. `delete()` can
  /// refuse (`requires-recent-login`, offline); the sign-out still runs.
  /// Never throws.
  Future<void> declineTerms() async {
    // An exchange still in flight must not sign this user in after all.
    _authGeneration++;
    final refusedUid = _consentRefusedUid;
    final existingAccount = _consentRefusedIsUpdate;
    _consentRefusedUid = null;
    _consentRefusedIsUpdate = false;
    try {
      // Only the user the 428 was for: never delete some other signed-in one.
      // And never an account that already exists: declining a changed policy
      // signs out and keeps the login.
      final current = _firebaseAuth.currentUser;
      if (!existingAccount &&
          current != null &&
          refusedUid != null &&
          current.uid == refusedUid) {
        await current.delete();
      }
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH] Consent declined; delete failed: $e');
    }
    try {
      await _firebaseAuth.signOut();
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Firebase sign-out failed: $e');
    }
    try {
      // google_sign_in 7.x: no call before `initialize`.
      if (_googleInitialized) await googleSignIn.signOut();
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Google sign-out failed: $e');
    }
    await _forgetAcceptedTerms();
    try {
      ref.read(apiServiceProvider).setAuthToken(null);
      await _clearJWT();
    } catch (e) {
      if (kDebugMode) debugPrint('[AUTH ERROR] Token clear failed: $e');
    }
    state = const AuthState();
  }

  /// A 409 on the refresh's exchange: keep the user signed in to Firebase
  /// and put the conflict on screen, as the launch exchange does, instead of
  /// signing out with "session expired" (todo 500 finding 1, owner decision
  /// 2026-10-10). The flag survives, so the sign-in screen still offers the
  /// password reset for `unverified_account`.
  ///
  /// Like the launch 409, the expired JWT goes too: it is deleted from
  /// storage and `jwtToken` is null, so `isAuthenticated` is false (todo 567
  /// finding 5). The bearer stays installed until a sign-out: clearing it
  /// here would end the API session under the refresh, and the request that
  /// asked for it would fail as "overtaken" instead of with the conflict.
  Future<void> _surfaceAccountConflict(
    User user,
    int generation,
    ApiException e,
  ) async {
    if (!await _clearJWTWhileCurrent(user, generation)) return;
    final unverified = e.code == 'unverified_account';
    state = AuthState(
      firebaseUser: user,
      error: unverified ? accountConflictMessage : accountLinkFailedMessage,
      unverifiedAccountConflict: unverified,
    );
  }

  /// Clear authentication state after an unrecoverable API 401 response.
  /// (signOut()'s own FCM-clear PATCH is exempt request-side via
  /// ApiService.skipSessionExpiryKey — a flag here couldn't cover a 401
  /// arriving after the clear's timeout abandoned the request.)
  Future<void> _handleSessionExpired() async {
    if (kDebugMode) {
      debugPrint('[AUTH] Session expired; signing out user');
    }

    const message = 'Your session expired. Please sign in again.';
    _pendingSignedOutMessage = message;
    _authGeneration++;
    // Before any await: clearing the token ends the API session, so a 401
    // that lands meanwhile sees the session over and does not start a second
    // sign-out (todo 498).
    ref.read(apiServiceProvider).setAuthToken(null);
    await _clearJWT();
    await _firebaseAuth.signOut();

    // After the awaits, in the same frame as the auth flip: clearing it
    // first left signed-in screens identity-less for those frames ("No
    // profile data available", every group message read as theirs) (todo
    // 558 finding 3). The Firebase listener's null branch clears it too.
    _clearAccountProfile();
    state = const AuthState(error: message);
  }

  /// Forget whose account this was, on every sign-out path but the
  /// profile-screen logout, which clears it itself: session expiry
  /// ([_handleSessionExpired]) and a sign-out Firebase reports (the
  /// listener's null branch, which also covers a revoked token or a disabled
  /// account) (todos 520, 558).
  ///
  /// A forum screen that is still mounted reads the account profile's
  /// `.value`, which keeps the last profile through a reload and a failed
  /// refresh by design (todo 507), so without this the previous user's
  /// username would attribute messages until that screen unmounted.
  /// `clear()`, not `invalidate()`: a rebuild keeps the old profile in
  /// `.value` while it re-fetches. Guarded, because reading an unwatched
  /// autoDispose provider would build it. A dirty one (an invalidate
  /// deferred under a paused watcher) is flushed by the `.notifier` read,
  /// and its build() returns null without a request now that the bearer is
  /// gone (todo 558 finding 1). The next completed sign-in fetches it again
  /// ([_refetchAccountProfile]).
  void _clearAccountProfile() {
    if (ref.exists(userProfileServiceProvider)) {
      ref.read(userProfileServiceProvider.notifier).clear();
    }
  }

  /// Fetch the account profile again for the account that just signed in,
  /// when a screen still holds the provider.
  ///
  /// A session-expiry sign-out leaves it at `AsyncData(null)`
  /// ([_handleSessionExpired]), and nothing else fetched it again. The
  /// provider is autoDispose, but a watcher on an OFFSTAGE tab keeps it
  /// alive: go_router wraps an inactive `StatefulShellRoute.indexedStack`
  /// branch in `TickerMode(enabled: false)`, flutter_riverpod pauses a
  /// widget's subscriptions under it, and Riverpod never disposes a provider
  /// that still has (paused) listeners. An expiry on a route that is not
  /// protected never redirects either, so the sign-in screen is PUSHED over
  /// the still-mounted shell — and after a re-login ProfileScreen read that
  /// null as "No profile data available", a data state with no Retry, until
  /// the process restarted (todo 520 review).
  ///
  /// Invalidate, not `clear()`: the rebuild fetches under the bearer just
  /// installed. Every sign-out path that ends a session cleared the last
  /// account's profile ([_clearAccountProfile], or the profile-screen
  /// logout), so the rebuild starts from no profile. Riverpod rebuilds an
  /// invalidated provider only when something actively listens, so with
  /// every watcher paused the rebuild waits for the next read —
  /// ProfileScreen's fresh watch, or the tab coming back on-screen. No
  /// `ref.exists` guard: invalidating a provider nothing holds is a no-op (it
  /// is not built), and a screen's first watch builds it under the new
  /// bearer when it is wanted.
  ///
  /// As a reload, not a refresh (todo 558 finding 4): a refresh over the
  /// cleared AsyncData(null) stays a data value, so ProfileScreen's `when()`
  /// showed "No profile data available" for the whole GET instead of its
  /// spinner, and Riverpod's retry counter was not reset.
  void _refetchAccountProfile() {
    ref.invalidate(userProfileServiceProvider, asReload: true);
  }

  /// Delete the stored tokens, each only while this exchange is still
  /// current: once it is overtaken, a newer exchange may already have stored
  /// its own tokens, and deleting them would sign that user out (todos 587
  /// item 2, 607 item 2). True when the exchange is still current after the
  /// last delete, so the caller may go on to clear the bearer and set state.
  Future<bool> _clearJWTWhileCurrent(User user, int generation) async {
    for (final key in const [_jwtKey, _refreshTokenKey]) {
      if (!_isCurrentExchange(user, generation)) return false;
      await _secureStorage.delete(key: key);
    }
    return _isCurrentExchange(user, generation);
  }

  /// Clear stored JWT tokens
  Future<void> _clearJWT() async {
    await _secureStorage.delete(key: _jwtKey);
    await _secureStorage.delete(key: _refreshTokenKey);
  }

  /// Convert Firebase Auth exception to user-friendly message
  String _handleFirebaseAuthException(FirebaseAuthException e) {
    switch (e.code) {
      case 'user-not-found':
        return 'No account found with this email. Please sign up.';
      case 'wrong-password':
        return 'Incorrect password. Please try again.';
      case 'invalid-credential':
        // Email-enumeration protection: Firebase answers a wrong password
        // and an unknown (or deleted) account alike with this code.
        return 'Incorrect email or password. Please try again.';
      case 'invalid-email':
        return 'Please enter a valid email address.';
      case 'user-disabled':
        return 'This account has been disabled. Please contact support.';
      case 'email-already-in-use':
        return 'An account already exists with this email.';
      case 'weak-password':
        return 'Password is too weak. Use at least 6 characters.';
      case 'operation-not-allowed':
        // Reached by BOTH paths now. Naming only email/password sent someone
        // hunting the wrong console toggle when Google is the one disabled.
        return 'That sign-in method is not enabled for this app.';
      case 'too-many-requests':
        return 'Too many failed attempts. Please try again later.';
      case 'network-request-failed':
        return 'Network error. Please check your internet connection.';
      default:
        return 'Authentication failed: ${e.message ?? e.code}';
    }
  }
}

/// Custom exception for authentication errors
class AuthException implements Exception {
  final String message;

  AuthException(this.message);

  @override
  String toString() => 'AuthException: $message';
}

/// The user backed out of [AuthService.freshIdTokenAfterReauth]: closed the
/// Google sheet or gave no password. Not an error to show.
class ReauthCancelledException extends AuthException {
  ReauthCancelledException() : super('Cancelled.');
}
