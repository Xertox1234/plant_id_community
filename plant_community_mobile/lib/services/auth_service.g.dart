// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'auth_service.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
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

@ProviderFor(AuthService)
const authServiceProvider = AuthServiceProvider._();

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
final class AuthServiceProvider
    extends $NotifierProvider<AuthService, AuthState> {
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
  const AuthServiceProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'authServiceProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$authServiceHash();

  @$internal
  @override
  AuthService create() => AuthService();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AuthState value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AuthState>(value),
    );
  }
}

String _$authServiceHash() => r'd75532301182928f10320f8cb9455b6b8f96b10c';

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

abstract class _$AuthService extends $Notifier<AuthState> {
  AuthState build();
  @$mustCallSuper
  @override
  void runBuild() {
    final created = build();
    final ref = this.ref as $Ref<AuthState, AuthState>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AuthState, AuthState>,
              AuthState,
              Object?,
              Object?
            >;
    element.handleValue(ref, created);
  }
}
