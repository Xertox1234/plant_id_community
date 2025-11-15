import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'api_service.dart';

part 'auth_service.g.dart';

/// Authentication state for the application
class AuthState {
  final User? firebaseUser;
  final String? jwtToken;
  final bool isLoading;
  final String? error;

  const AuthState({
    this.firebaseUser,
    this.jwtToken,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => firebaseUser != null && jwtToken != null;

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
  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  static const String _jwtKey = 'django_jwt_token';
  static const String _refreshTokenKey = 'django_refresh_token';

  // Store StreamSubscription to prevent memory leak
  StreamSubscription<User?>? _authStateSubscription;

  @override
  AuthState build() {
    // Initialize with current Firebase user
    final currentUser = _firebaseAuth.currentUser;

    // Listen to Firebase auth state changes
    // Store subscription so we can cancel it on disposal
    _authStateSubscription = _firebaseAuth.authStateChanges().listen((user) async {
      if (kDebugMode) {
        debugPrint('[AUTH] Firebase auth state changed: ${user?.email}');
      }

      if (user != null) {
        // User signed in → exchange token
        await _exchangeFirebaseTokenForJWT(user);
      } else {
        // User signed out → clear JWT
        await _clearJWT();
        state = const AuthState();
      }
    });

    // Cancel subscription when provider is disposed to prevent memory leak
    ref.onDispose(() {
      if (kDebugMode) {
        debugPrint('[AUTH] Cancelling auth state subscription');
      }
      _authStateSubscription?.cancel();
    });

    // If user is already signed in, exchange token
    if (currentUser != null) {
      _exchangeFirebaseTokenForJWT(currentUser);
    }

    return AuthState(firebaseUser: currentUser);
  }

  /// Sign in with email and password
  ///
  /// Throws [AuthException] if sign in fails
  Future<void> signInWithEmailPassword(String email, String password) async {
    try {
      state = state.copyWith(isLoading: true, error: null);

      if (kDebugMode) {
        debugPrint('[AUTH] Signing in with email: $email');
      }

      final credential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      if (kDebugMode) {
        debugPrint('[AUTH] Firebase sign in successful: ${credential.user?.email}');
      }

      // Auth state listener will handle token exchange
      state = state.copyWith(
        firebaseUser: credential.user,
        isLoading: false,
      );
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

  /// Register new user with email and password
  ///
  /// Throws [AuthException] if registration fails
  Future<void> registerWithEmailPassword({
    required String email,
    required String password,
    required String displayName,
  }) async {
    try {
      state = state.copyWith(isLoading: true, error: null);

      if (kDebugMode) {
        debugPrint('[AUTH] Registering new user: $email');
      }

      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );

      // Update display name
      await credential.user?.updateDisplayName(displayName);
      await credential.user?.reload();

      if (kDebugMode) {
        debugPrint('[AUTH] User registered: ${credential.user?.email}');
      }

      // Auth state listener will handle token exchange
      state = state.copyWith(
        firebaseUser: _firebaseAuth.currentUser,
        isLoading: false,
      );
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

  /// Sign out current user
  Future<void> signOut() async {
    try {
      if (kDebugMode) {
        debugPrint('[AUTH] Signing out user');
      }

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
  /// This is called automatically when user signs in
  Future<void> _exchangeFirebaseTokenForJWT(User user) async {
    try {
      if (kDebugMode) {
        debugPrint('[AUTH] Exchanging Firebase token for Django JWT');
      }

      // Get Firebase ID token
      final firebaseToken = await user.getIdToken();

      if (firebaseToken == null) {
        throw AuthException('Failed to get Firebase ID token');
      }

      // Call Django backend to exchange token
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.post(
        '/auth/firebase-token-exchange/',
        data: {
          'firebase_token': firebaseToken,
          'email': user.email,
          'display_name': user.displayName,
        },
      );

      // Extract JWT tokens from response
      final jwtToken = response.data['access_token'] as String?;
      final refreshToken = response.data['refresh_token'] as String?;

      if (jwtToken == null) {
        throw AuthException('No JWT token in response');
      }

      // Store tokens securely
      await _secureStorage.write(key: _jwtKey, value: jwtToken);
      if (refreshToken != null) {
        await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);
      }

      // Update ApiService with new token
      apiService.setAuthToken(jwtToken);

      // Update state
      state = state.copyWith(
        firebaseUser: user,
        jwtToken: jwtToken,
      );

      if (kDebugMode) {
        debugPrint('[AUTH] JWT token exchange successful');
      }
    } on ApiException catch (e) {
      if (kDebugMode) {
        debugPrint('[AUTH ERROR] Token exchange failed: ${e.message}');
      }

      // Don't throw - allow user to stay signed in to Firebase
      // They can retry later or we can implement retry logic
      state = state.copyWith(
        error: 'Failed to connect to server. Some features may be unavailable.',
      );
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[AUTH ERROR] Token exchange failed: $e');
      }

      state = state.copyWith(
        error: 'Authentication error. Please try again.',
      );
    }
  }

  /// Refresh JWT token
  ///
  /// Call this when API returns 401 Unauthorized
  Future<bool> refreshToken() async {
    try {
      if (kDebugMode) {
        debugPrint('[AUTH] Refreshing JWT token');
      }

      final refreshToken = await _secureStorage.read(key: _refreshTokenKey);

      if (refreshToken == null) {
        if (kDebugMode) {
          debugPrint('[AUTH] No refresh token available');
        }
        return false;
      }

      // Call Django refresh endpoint
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.post(
        '/auth/token/refresh/',
        data: {'refresh': refreshToken},
      );

      final newAccessToken = response.data['access'] as String?;

      if (newAccessToken == null) {
        if (kDebugMode) {
          debugPrint('[AUTH] No access token in refresh response');
        }
        return false;
      }

      // Store new access token
      await _secureStorage.write(key: _jwtKey, value: newAccessToken);

      // Update ApiService
      apiService.setAuthToken(newAccessToken);

      // Update state
      state = state.copyWith(jwtToken: newAccessToken);

      if (kDebugMode) {
        debugPrint('[AUTH] Token refresh successful');
      }

      return true;
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[AUTH ERROR] Token refresh failed: $e');
      }
      return false;
    }
  }

  /// Get stored JWT token
  Future<String?> getJWT() async {
    return await _secureStorage.read(key: _jwtKey);
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
      case 'invalid-email':
        return 'Please enter a valid email address.';
      case 'user-disabled':
        return 'This account has been disabled. Please contact support.';
      case 'email-already-in-use':
        return 'An account already exists with this email.';
      case 'weak-password':
        return 'Password is too weak. Use at least 6 characters.';
      case 'operation-not-allowed':
        return 'Email/password sign in is not enabled.';
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
