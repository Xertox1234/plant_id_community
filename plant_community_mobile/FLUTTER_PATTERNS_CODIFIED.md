# Flutter Mobile Development Patterns - Codified

**Status**: Active Reference (November 15, 2025)
**Scope**: Flutter 3.27 + Dart SDK 3.9.x + Riverpod 3.x
**Purpose**: Codified patterns for Plant ID Community mobile app development

---

## Table of Contents

1. [API Service Layer Patterns](#1-api-service-layer-patterns)
2. [Firebase Authentication Patterns](#2-firebase-authentication-patterns)
3. [Riverpod State Management Patterns](#3-riverpod-state-management-patterns)
4. [Memory Leak Prevention Patterns](#4-memory-leak-prevention-patterns)
5. [Secure Storage Patterns](#5-secure-storage-patterns)
6. [Error Handling Patterns](#6-error-handling-patterns)
7. [Code Generation Patterns](#7-code-generation-patterns)
8. [File Organization Patterns](#8-file-organization-patterns)
9. [Material Design 3 Patterns](#9-material-design-3-patterns)
10. [Null Safety Patterns](#10-null-safety-patterns)
11. [**Firestore Offline Sync Patterns** ✅ NEW](#11-firestore-offline-sync-patterns)

**Comprehensive Documentation**:
- **Firestore Patterns**: See `docs/FIRESTORE_PATTERNS.md` (10 patterns, 400+ lines)
- **Security Rules**: See `docs/FIRESTORE_SECURITY_RULES.md` (comprehensive guide)

---

## 1. API Service Layer Patterns

### Pattern 1.1: Centralized HTTP Client with Dio

**Problem**: Need centralized API communication with automatic authentication and error handling.

**Solution**: Single `ApiService` class with Dio interceptors.

**Implementation**:
```dart
// lib/services/api_service.dart
import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class ApiService {
  late final Dio _dio;

  ApiService() {
    final baseUrl = dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ));

    // Add interceptors for logging and auth
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (kDebugMode) {
            debugPrint('[API] ${options.method} ${options.path}');
          }
          return handler.next(options);
        },
        onResponse: (response, handler) {
          if (kDebugMode) {
            debugPrint('[API] ${response.statusCode} ${response.requestOptions.path}');
          }
          return handler.next(response);
        },
      ),
    );
  }

  // HTTP methods
  Future<Response> get(String path, {Map<String, dynamic>? queryParameters}) async {
    try {
      return await _dio.get(path, queryParameters: queryParameters);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // ... other methods
}
```

**Why This Works**:
- Single source of truth for API configuration
- Automatic request/response logging in debug mode
- Consistent error transformation
- Easy to add authentication tokens via interceptors

**Reference**: `lib/services/api_service.dart` (362 lines, 15 tests)

---

### Pattern 1.2: Environment-Based Configuration

**Problem**: Need different API URLs for dev/staging/production.

**Solution**: Use flutter_dotenv with .env files.

**Implementation**:
```dart
// .env.example
API_BASE_URL=http://localhost:8000
FIREBASE_API_KEY=your-api-key-here

// lib/main.dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

void main() async {
  await dotenv.load(fileName: '.env');
  runApp(const MyApp());
}

// Usage
final baseUrl = dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';
```

**Why This Works**:
- Secrets never committed to git (.env in .gitignore)
- Easy environment switching
- Fallback defaults for development

**Critical**: ALWAYS add `.env` to `.gitignore`, commit `.env.example` with placeholders

---

### Pattern 1.3: Typed Error Handling with ApiException

**Problem**: DioException contains too much implementation detail for UI.

**Solution**: Transform to custom ApiException with user-friendly messages.

**Implementation**:
```dart
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final String? retryAfter;

  ApiException(this.message, {this.statusCode, this.retryAfter});

  @override
  String toString() => 'ApiException: $message';
}

ApiException _handleError(DioException e) {
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
      return ApiException(
        'Connection timeout. Please check your internet connection.',
        statusCode: null,
      );

    case DioExceptionType.receiveTimeout:
      return ApiException(
        'Server took too long to respond. Please try again.',
        statusCode: null,
      );

    case DioExceptionType.badResponse:
      final statusCode = e.response?.statusCode;

      if (statusCode == 401) {
        return ApiException(
          'Your session has expired. Please sign in again.',
          statusCode: 401,
        );
      }

      if (statusCode == 429) {
        final retryAfter = e.response?.headers['Retry-After']?.first;
        return ApiException(
          'Too many requests. Please try again later.',
          statusCode: 429,
          retryAfter: retryAfter,
        );
      }

      // Extract backend error message if available
      final errorMessage = e.response?.data?['error'] ??
                          e.response?.data?['detail'] ??
                          'An error occurred';

      return ApiException(errorMessage, statusCode: statusCode);

    default:
      if (e.error is SocketException) {
        return ApiException(
          'No internet connection. Please check your network.',
          statusCode: null,
        );
      }
      return ApiException('An unexpected error occurred');
  }
}
```

**Why This Works**:
- User-friendly error messages
- Special handling for 401 (expired token), 429 (rate limit)
- Network errors detected via SocketException
- Backend error messages preserved when available

---

## 2. Firebase Authentication Patterns

### Pattern 2.1: Firebase → Django JWT Token Exchange

**Problem**: Mobile app uses Firebase Auth, but Django backend requires JWT tokens.

**Solution**: Exchange Firebase ID token for Django JWT via dedicated endpoint.

**Implementation**:
```dart
// lib/services/auth_service.dart
Future<void> _exchangeFirebaseTokenForJWT(User firebaseUser) async {
  try {
    // Get Firebase ID token
    final idToken = await firebaseUser.getIdToken();

    if (idToken == null) {
      throw Exception('Failed to get Firebase ID token');
    }

    // Exchange for Django JWT
    final response = await _apiService.post(
      '/api/v1/auth/firebase-token-exchange/',
      data: {
        'firebase_token': idToken,
        'email': firebaseUser.email,
        'display_name': firebaseUser.displayName,
      },
    );

    // Store JWT tokens securely
    final accessToken = response.data['access_token'];
    final refreshToken = response.data['refresh_token'];

    await _secureStorage.write(key: _jwtKey, value: accessToken);
    await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);

    // Inject token into ApiService
    _apiService.setAuthToken(accessToken);

    if (kDebugMode) {
      debugPrint('[AUTH] JWT tokens exchanged and stored');
    }

    // Update state with authenticated user
    state = AuthState(
      firebaseUser: firebaseUser,
      isAuthenticated: true,
    );
  } catch (e) {
    if (kDebugMode) {
      debugPrint('[AUTH ERROR] Token exchange failed: $e');
    }
    throw ApiException('Authentication failed: ${e.toString()}');
  }
}
```

**Backend Endpoint** (`/api/v1/auth/firebase-token-exchange/`):
- Validates Firebase ID token with firebase-admin SDK
- Creates/retrieves Django user
- Generates JWT access + refresh tokens
- Returns tokens + user data

**Why This Works**:
- Secure: Firebase validates the user, Django controls API access
- Single source of truth: Firebase for authentication, Django for authorization
- Offline-ready: JWT tokens can be cached and work without Firebase connection

**Reference**:
- Flutter: `lib/services/auth_service.dart`
- Backend: `backend/apps/users/firebase_auth_views.py` (17 tests)

---

### Pattern 2.2: Secure Token Storage with flutter_secure_storage

**Problem**: JWTs must persist across app restarts but NEVER in plain text.

**Solution**: Use flutter_secure_storage (encrypted keychain/keystore).

**Implementation**:
```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  static const String _jwtKey = 'django_jwt_token';
  static const String _refreshTokenKey = 'django_refresh_token';

  // Store tokens
  Future<void> _storeTokens(String accessToken, String refreshToken) async {
    await _secureStorage.write(key: _jwtKey, value: accessToken);
    await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);
  }

  // Retrieve tokens
  Future<String?> getAccessToken() async {
    return await _secureStorage.read(key: _jwtKey);
  }

  // Clear tokens (sign out)
  Future<void> _clearTokens() async {
    await _secureStorage.delete(key: _jwtKey);
    await _secureStorage.delete(key: _refreshTokenKey);
  }
}
```

**Why This Works**:
- iOS: Stores in Keychain (encrypted by default)
- Android: Stores in EncryptedSharedPreferences (AES encryption)
- Safe from app uninstall → reinstall (tokens cleared automatically)
- No risk of XSS (unlike web localStorage)

**CRITICAL**: NEVER use SharedPreferences for tokens (plain text, vulnerable)

---

### Pattern 2.3: Email Redaction for GDPR Compliance

**Problem**: Backend logs contain PII (email addresses) violating GDPR/CCPA.

**Solution**: Redact emails in logs on both frontend and backend.

**Backend Implementation**:
```python
# backend/apps/users/firebase_auth_views.py
def redact_email(email: str) -> str:
    """
    Redact email for GDPR-compliant logging.
    Shows first 2 characters of local part + domain.
    Example: john.doe@example.com -> jo***@example.com
    """
    if not email or '@' not in email:
        return '***'

    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f"{'*' * len(local)}@{domain}"

    return f"{local[:2]}***@{domain}"

# Usage in logs
logger.info(f"[FIREBASE AUTH] Token validated for {redact_email(firebase_email)}")
```

**Flutter Implementation**:
```dart
String redactEmail(String email) {
  if (!email.contains('@')) return '***';

  final parts = email.split('@');
  final local = parts[0];
  final domain = parts[1];

  if (local.length <= 2) return '${'*' * local.length}@$domain';

  return '${local.substring(0, 2)}***@$domain';
}

// Usage
debugPrint('[AUTH] User signed in: ${redactEmail(user.email!)}');
```

**Why This Works**:
- Shows enough for debugging (first 2 chars + domain)
- Complies with GDPR (PII minimization)
- Prevents accidental email exposure in logs

---

## 3. Riverpod State Management Patterns

### Pattern 3.1: Riverpod 3.x Code Generation with @riverpod

**Problem**: Need type-safe, boilerplate-free state management.

**Solution**: Use Riverpod 3.x with code generation (@riverpod annotation).

**Implementation**:
```dart
// lib/services/auth_service.dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'auth_service.g.dart';

@riverpod
class AuthService extends _$AuthService {
  @override
  AuthState build() {
    final currentUser = _firebaseAuth.currentUser;

    // Listen to Firebase auth state
    _authStateSubscription = _firebaseAuth.authStateChanges().listen((user) async {
      // Handle auth state changes
    });

    // Cleanup on dispose
    ref.onDispose(() {
      _authStateSubscription?.cancel();
    });

    return AuthState(firebaseUser: currentUser);
  }

  // Methods
  Future<void> signInWithEmailPassword(String email, String password) async {
    state = state.copyWith(isLoading: true);

    try {
      await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
      rethrow;
    } finally {
      state = state.copyWith(isLoading: false);
    }
  }
}

// Provider (auto-generated)
final authServiceProvider = AuthServiceProvider();
```

**Code Generation Command**:
```bash
flutter pub run build_runner build --delete-conflicting-outputs
flutter pub run build_runner watch  # Auto-rebuild on changes
```

**Why This Works**:
- No manual provider boilerplate
- Type-safe provider access
- Automatic dependency tracking
- ref.onDispose() for cleanup

**Migration from Riverpod 2.x**:
- Replace `StateNotifier` with `Notifier`
- Use `@riverpod` annotation instead of manual providers
- `build()` method replaces constructor

---

### Pattern 3.2: Provider Access Patterns

**Problem**: Need to read and watch providers correctly.

**Solution**: Use `ref.read()` for one-time access, `ref.watch()` for reactive updates.

**Implementation**:
```dart
// In a StatelessWidget with ConsumerWidget
class MyWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Watch for reactive updates (rebuilds on state change)
    final authState = ref.watch(authServiceProvider);

    // Read for one-time access (no rebuild)
    final authService = ref.read(authServiceProvider.notifier);

    return Column(
      children: [
        Text(authState.isAuthenticated ? 'Signed In' : 'Signed Out'),

        ElevatedButton(
          onPressed: () {
            // Use .notifier to call methods
            authService.signInWithEmailPassword(email, password);
          },
          child: Text('Sign In'),
        ),
      ],
    );
  }
}

// In a StatefulWidget with ConsumerStatefulWidget
class MyStatefulWidget extends ConsumerStatefulWidget {
  @override
  ConsumerState<MyStatefulWidget> createState() => _MyStatefulWidgetState();
}

class _MyStatefulWidgetState extends ConsumerState<MyStatefulWidget> {
  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authServiceProvider);

    return Text(authState.isAuthenticated ? 'Authenticated' : 'Not Authenticated');
  }

  void _onButtonPressed() {
    // Access notifier in event handlers
    ref.read(authServiceProvider.notifier).signOut();
  }
}
```

**Why This Works**:
- `ref.watch()` rebuilds widget on state changes (reactive)
- `ref.read()` gets current value without subscription (one-time)
- `.notifier` accesses the Notifier instance for method calls

---

## 4. Memory Leak Prevention Patterns

### Pattern 4.1: StreamSubscription Cleanup with ref.onDispose()

**Problem**: StreamSubscriptions accumulate listeners if not cancelled (memory leak).

**Solution**: Store subscription and cancel in `ref.onDispose()`.

**Implementation**:
```dart
@riverpod
class AuthService extends _$AuthService {
  // Store subscription as field
  StreamSubscription<User?>? _authStateSubscription;

  @override
  AuthState build() {
    // Listen to Firebase auth state
    _authStateSubscription = _firebaseAuth.authStateChanges().listen((user) async {
      if (kDebugMode) {
        debugPrint('[AUTH] Firebase auth state changed: ${user?.email}');
      }

      if (user != null) {
        await _exchangeFirebaseTokenForJWT(user);
      } else {
        await _clearJWT();
        state = const AuthState();
      }
    });

    // CRITICAL: Cancel subscription when provider is disposed
    ref.onDispose(() {
      if (kDebugMode) {
        debugPrint('[AUTH] Cancelling auth state subscription');
      }
      _authStateSubscription?.cancel();
    });

    return AuthState(firebaseUser: _firebaseAuth.currentUser);
  }
}
```

**Why This Works**:
- Subscription stored as field (not state variable)
- `ref.onDispose()` called automatically when provider unmounts
- Prevents listener accumulation (1 listener per provider instance)

**Common Mistakes**:
- ❌ Storing subscription in state: `state = state.copyWith(subscription: sub)` → triggers rebuild
- ❌ Not storing subscription: `stream.listen(...)` → can't cancel later
- ❌ Using `setState()` in dispose: State mutation after disposal

---

### Pattern 4.2: Timer Cleanup with useRef (React Hooks Style)

**Problem**: Debounce timers in state cause unnecessary re-renders and memory leaks.

**Solution**: Use `useRef` pattern (store timer as field, not state).

**Implementation**:
```dart
class SearchWidget extends ConsumerStatefulWidget {
  @override
  ConsumerState<SearchWidget> createState() => _SearchWidgetState();
}

class _SearchWidgetState extends ConsumerState<SearchWidget> {
  Timer? _debounceTimer;  // Field, NOT state

  @override
  void dispose() {
    _debounceTimer?.cancel();  // Cancel on dispose
    super.dispose();
  }

  void _onSearchChanged(String query) {
    // Cancel previous timer
    _debounceTimer?.cancel();

    // Start new timer
    _debounceTimer = Timer(const Duration(milliseconds: 500), () {
      // Perform search
      ref.read(searchServiceProvider.notifier).search(query);
    });
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      onChanged: _onSearchChanged,
    );
  }
}
```

**Why useRef Pattern Works**:
- Timer stored as field (no re-render on update)
- Cancelled in `dispose()` lifecycle method
- Stable reference (no callback recreation)

**Comparison to useState**:
- ❌ `useState`: Triggers rebuild, unstable reference
- ✅ `useRef`: No rebuild, stable reference

---

## 5. Secure Storage Patterns

### Pattern 5.1: NEVER Use SharedPreferences for Secrets

**Problem**: SharedPreferences stores data in plain text (XML on Android, plist on iOS).

**Solution**: Use flutter_secure_storage for tokens, passwords, API keys.

**Implementation**:
```dart
// ❌ BAD - Plain text storage
final prefs = await SharedPreferences.getInstance();
await prefs.setString('jwt_token', token);  // INSECURE!

// ✅ GOOD - Encrypted storage
final secureStorage = const FlutterSecureStorage();
await secureStorage.write(key: 'jwt_token', value: token);  // SECURE
```

**What flutter_secure_storage Does**:
- **iOS**: Stores in Keychain (hardware-backed encryption on newer devices)
- **Android**: Uses EncryptedSharedPreferences (AES-256-GCM encryption)
- **Automatically cleared** on app uninstall

**When to Use Each**:
- **flutter_secure_storage**: JWT tokens, Firebase tokens, API keys, passwords
- **SharedPreferences**: User preferences, theme settings, language choice

---

## 6. Error Handling Patterns

### Pattern 6.1: Centralized Error Transformation

**Problem**: Backend errors, network errors, and timeout errors all need user-friendly messages.

**Solution**: Transform all errors in ApiService._handleError().

**Implementation**: See Pattern 1.3 (Typed Error Handling with ApiException)

---

### Pattern 6.2: Error State in Riverpod Providers

**Problem**: Need to show errors in UI while preserving previous data.

**Solution**: Include error field in state model.

**Implementation**:
```dart
class AuthState {
  final User? firebaseUser;
  final bool isAuthenticated;
  final bool isLoading;
  final String? error;

  const AuthState({
    this.firebaseUser,
    this.isAuthenticated = false,
    this.isLoading = false,
    this.error,
  });

  AuthState copyWith({
    User? firebaseUser,
    bool? isAuthenticated,
    bool? isLoading,
    String? error,
  }) {
    return AuthState(
      firebaseUser: firebaseUser ?? this.firebaseUser,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      error: error,  // Allow null to clear error
    );
  }
}

// Usage in UI
if (authState.error != null) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(authState.error!)),
  );
}
```

**Why This Works**:
- Error persists in state (can be shown in UI)
- Error can be cleared by setting to null
- Loading and error can coexist (e.g., retry in progress)

---

## 7. Code Generation Patterns

### Pattern 7.1: build_runner Workflow

**Problem**: Manual code generation is error-prone and slow.

**Solution**: Use build_runner with watch mode during development.

**Commands**:
```bash
# One-time build (clean previous)
flutter pub run build_runner build --delete-conflicting-outputs

# Watch mode (auto-rebuild on file save)
flutter pub run build_runner watch

# Clean generated files
flutter pub run build_runner clean
```

**What Gets Generated**:
- Riverpod providers (*.g.dart files)
- go_router routes (*.g.dart files)
- Freezed models (*.freezed.dart files)
- JSON serialization (*.g.dart files)

**Best Practices**:
- Run `build_runner watch` at start of dev session
- Commit generated files to git (team consistency)
- Run `build` before committing (ensure no conflicts)

---

### Pattern 7.2: Part Files Pattern

**Problem**: Code generation requires `part` directive.

**Solution**: Add `part 'filename.g.dart';` to all files using code generation.

**Implementation**:
```dart
// lib/services/auth_service.dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'auth_service.g.dart';  // REQUIRED for @riverpod

@riverpod
class AuthService extends _$AuthService {
  // ...
}
```

**Why This Works**:
- `part` directive tells Dart where to find generated code
- Generated file has access to private members
- Single file per service (not scattered across multiple files)

---

## 8. File Organization Patterns

### Pattern 8.1: Feature-First Directory Structure

**Problem**: Need scalable, maintainable file organization.

**Solution**: Organize by feature, not by type.

**Implementation**:
```
lib/
├── core/
│   ├── routing/
│   │   └── app_router.dart
│   ├── theme/
│   │   └── app_theme.dart
│   └── constants/
│       └── api_constants.dart
├── features/
│   ├── auth/
│   │   ├── models/
│   │   │   └── auth_state.dart
│   │   ├── services/
│   │   │   └── auth_service.dart
│   │   └── screens/
│   │       ├── login_screen.dart
│   │       └── register_screen.dart
│   ├── plant_identification/
│   │   ├── models/
│   │   ├── services/
│   │   └── screens/
│   └── garden/
│       ├── models/
│       ├── services/
│       └── screens/
├── services/
│   ├── api_service.dart
│   └── README.md
└── main.dart
```

**Why This Works**:
- Features self-contained (easy to find related files)
- Shared services in top-level `services/`
- Core utilities (routing, theme) separated
- Scalable (add features without refactoring)

---

## 9. Material Design 3 Patterns

### Pattern 9.1: Material 3 Migration Patterns

**Problem**: Material 2 APIs deprecated in Flutter 3.x.

**Solution**: Use Material 3 equivalents.

**Common Migrations**:
```dart
// ❌ Material 2 (deprecated)
Theme(
  data: ThemeData(
    cardTheme: CardTheme(
      elevation: 4,
      color: Colors.white.withOpacity(0.9),
    ),
  ),
)

// ✅ Material 3
Theme(
  data: ThemeData(
    cardTheme: CardThemeData(  // CardThemeData not CardTheme
      elevation: 4,
      color: Colors.white.withValues(alpha: 0.9),  // withValues not withOpacity
    ),
  ),
)
```

**Other Material 3 Changes**:
- `useMaterial3: true` in ThemeData
- `ColorScheme.fromSeed()` for color generation
- `NavigationBar` replaces `BottomNavigationBar`
- `NavigationRail` for desktop/tablet

---

### Pattern 9.2: Dark Mode Support

**Problem**: Need to support both light and dark themes.

**Solution**: Use `Theme.of(context).brightness` to detect theme.

**Implementation**:
```dart
Widget build(BuildContext context) {
  final isDarkMode = Theme.of(context).brightness == Brightness.dark;

  return Container(
    color: isDarkMode
        ? Colors.grey[900]
        : Colors.white,
    child: Text(
      'Hello',
      style: TextStyle(
        color: isDarkMode ? Colors.white : Colors.black,
      ),
    ),
  );
}
```

**Why This Works**:
- Automatically updates when system theme changes
- No manual state management needed
- Respects user's system preference

---

## 10. Null Safety Patterns

### Pattern 10.1: Null-Safe Error Messages

**Problem**: ApiException.message might be nullable in some implementations.

**Solution**: Make message field non-nullable with required constructor.

**Implementation**:
```dart
class ApiException implements Exception {
  final String message;  // NOT String? (nullable)
  final int? statusCode;  // OK to be nullable

  ApiException(this.message, {this.statusCode});  // message required

  @override
  String toString() => 'ApiException: $message';  // Safe to use
}
```

**Why This Works**:
- Compile-time guarantee that message exists
- No need for `message ?? 'Unknown error'` checks
- Safe string interpolation

---

### Pattern 10.2: Safe Null Checks with ??

**Problem**: Need fallback values for nullable fields.

**Solution**: Use null-coalescing operator `??`.

**Implementation**:
```dart
// Environment variables (nullable)
final baseUrl = dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

// User display name (nullable)
final displayName = firebaseUser.displayName ?? 'User';

// Optional parameters
Future<void> loadPlants({int? limit}) async {
  final actualLimit = limit ?? 10;  // Default to 10
  // ...
}
```

**Why This Works**:
- Single-line fallback (no if statements)
- Type-safe (left and right must have same type)
- Readable and concise

---

## Summary

This document codifies the patterns developed during Firebase Authentication integration and API Service Layer implementation. These patterns are production-ready and should be followed for all Flutter mobile development in the Plant ID Community project.

**Key Principles**:
1. **Security First**: Use flutter_secure_storage, redact PII, validate tokens
2. **Memory Safety**: Cancel subscriptions, dispose timers, cleanup resources
3. **Type Safety**: Null-safe code, explicit types, code generation
4. **User Experience**: Friendly error messages, loading states, offline support
5. **Developer Experience**: Code generation, hot reload, debug logging

**Next Steps**:
- Task 3: Navigation & Routing (go_router patterns)
- Task 4: UI Components (Material Design 3 widgets)
- Task 5: Local Storage (SQLite + Drift patterns)

---

**Last Updated**: November 15, 2025
**Contributors**: Claude Code + Will Tower
**Related Documentation**:
- Backend Firebase Auth: `backend/docs/FIREBASE_AUTHENTICATION.md`
- Web Patterns: `web/TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md`
- Backend Patterns: `backend/docs/patterns/`
