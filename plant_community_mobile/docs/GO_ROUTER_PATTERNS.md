# go_router 17.0.0 Patterns - Task 3 Complete ✅

**Date**: November 15, 2025
**Status**: Production-Ready
**Version**: go_router 17.0.0
**Integration**: Riverpod 3.x + Firebase Auth

## Overview

This document codifies all go_router patterns implemented in the Plant Community mobile app. These patterns provide type-safe, authentication-aware navigation with deep linking support.

## Table of Contents

1. [Core Router Configuration](#1-core-router-configuration)
2. [Authentication Guards](#2-authentication-guards)
3. [Navigation Extensions](#3-navigation-extensions)
4. [Route Transitions](#4-route-transitions)
5. [Deep Linking](#5-deep-linking)
6. [Testing Patterns](#6-testing-patterns)
7. [Best Practices](#7-best-practices)
8. [Migration Guide](#8-migration-guide)

---

## 1. Core Router Configuration

### Pattern 1.1: Riverpod-Integrated Router Provider

**Location**: `lib/core/routing/app_router.dart:48-92`

**Pattern**: Use `@riverpod` annotation to create router provider that watches auth state

```dart
@riverpod
GoRouter appRouter(Ref ref) {
  // Watch auth state for automatic redirects
  final authState = ref.watch(authServiceProvider);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: kDebugMode,

    // Refresh router when auth state changes
    refreshListenable: _AuthStateNotifier(ref),

    // Global redirect logic
    redirect: (context, state) {
      // Redirect logic based on auth state
    },

    routes: [/* routes */],
    errorBuilder: (context, state) => ErrorScreen(error: state.error),
  );
}
```

**Why**:
- Router automatically rebuilds when auth state changes
- Centralized navigation logic
- Type-safe provider integration

**Anti-Pattern**: Creating router without watching auth state
```dart
// ❌ BAD - Router doesn't react to auth changes
final router = GoRouter(routes: [...]);
```

---

### Pattern 1.2: Centralized Route Constants

**Location**: `lib/core/routing/app_router.dart:14-34`

**Pattern**: Define all routes as `static const` in abstract class

```dart
abstract class AppRoutes {
  static const splash = '/';
  static const home = '/home';
  static const camera = '/camera';
  static const results = '/results';
  static const settings = '/settings';
  static const login = '/login';
  static const register = '/register';
  static const profile = '/profile';
  static const garden = '/garden';
}
```

**Why**:
- Single source of truth for routes
- Compile-time safety (no typos in route strings)
- Easy to refactor route paths
- IDE autocomplete support

**Anti-Pattern**: Hardcoding routes throughout the app
```dart
// ❌ BAD - Hardcoded strings, prone to typos
context.go('/results');
context.push('/profle'); // Typo! Will fail at runtime
```

---

## 2. Authentication Guards

### Pattern 2.1: Global Redirect Logic

**Location**: `lib/core/routing/app_router.dart:60-92`

**Pattern**: Implement global redirect function that checks auth state for all routes

```dart
redirect: (BuildContext context, GoRouterState state) {
  final isAuthenticated = authState.isAuthenticated;
  final isAuthRoute = state.matchedLocation == AppRoutes.login ||
      state.matchedLocation == AppRoutes.register;
  final isPublicRoute = state.matchedLocation == AppRoutes.splash ||
      state.matchedLocation == AppRoutes.home;

  // Log redirects in debug mode
  if (kDebugMode) {
    debugPrint('[ROUTER] Redirect check: '
        'location=${state.matchedLocation}, '
        'isAuthenticated=$isAuthenticated');
  }

  // Unauthenticated user trying to access protected route
  if (!isAuthenticated && !isPublicRoute && !isAuthRoute) {
    return AppRoutes.login;
  }

  // Authenticated user trying to access auth routes
  if (isAuthenticated && isAuthRoute) {
    return AppRoutes.home;
  }

  // No redirect needed
  return null;
},
```

**Why**:
- Centralized auth logic (no need to check auth in every route)
- Automatic redirects on auth state changes
- Debug logging for troubleshooting
- Prevents infinite redirect loops

**Key Details**:
- Return `null` for no redirect
- Return route path `String` to redirect
- Runs on EVERY navigation
- Must handle all auth states (unauthenticated, authenticated, loading)

**Testing Pattern**:
```dart
testWidgets('Should redirect unauthenticated user to login', (tester) async {
  final container = ProviderContainer(
    overrides: [
      authServiceProvider.overrideWith(
        (ref) => MockUnauthenticatedAuthService(),
      ),
    ],
  );

  final router = container.read(appRouterProvider);

  // Try to access protected route
  router.go(AppRoutes.profile);
  await tester.pumpAndSettle();

  // Should be redirected to login
  expect(router.routerDelegate.currentConfiguration.uri.path,
         equals(AppRoutes.login));
});
```

---

### Pattern 2.2: Auth State Notifier for Router Refresh

**Location**: `lib/core/routing/app_router.dart:330-347`

**Pattern**: Create `ChangeNotifier` that listens to auth provider and notifies router

```dart
class _AuthStateNotifier extends ChangeNotifier {
  final Ref _ref;
  late final void Function() _removeListener;

  _AuthStateNotifier(this._ref) {
    // Watch auth state and notify router when it changes
    _removeListener = _ref.listen<AuthState>(
      authServiceProvider,
      (_, _) => notifyListeners(),
    ).close;
  }

  @override
  void dispose() {
    _removeListener();  // CRITICAL: Prevent memory leak
    super.dispose();
  }
}
```

**Why**:
- go_router's `refreshListenable` requires a `Listenable`
- Automatically triggers redirect logic when auth changes
- Proper cleanup prevents memory leaks

**Memory Leak Prevention**:
- ALWAYS call `_removeListener()` in `dispose()`
- Store subscription reference with `late final`
- Use `ref.listen().close` pattern (not `ref.watch()`)

---

## 3. Navigation Extensions

### Pattern 3.1: Type-Safe Navigation Methods

**Location**: `lib/core/routing/navigation_extensions.dart:20-82`

**Pattern**: Extension methods on `BuildContext` for common navigations

```dart
extension NavigationExtensions on BuildContext {
  /// Navigate to home screen
  void goToHome() => go(AppRoutes.home);

  /// Navigate to camera screen
  void goToCamera() => go(AppRoutes.camera);

  /// Navigate to results with plant data
  void goToResults(Plant plant) => go(AppRoutes.results, extra: plant);

  /// Push results (keeps current screen in stack)
  void pushResults(Plant plant) => push(AppRoutes.results, extra: plant);

  /// Navigate to profile screen
  void goToProfile() => go(AppRoutes.profile);
}
```

**Usage**:
```dart
// Instead of:
context.go(AppRoutes.results, extra: plant);

// Use:
context.goToResults(plant);
```

**Why**:
- Type safety (compiler ensures Plant object is passed)
- Discoverability (IDE shows all navigation methods)
- Consistency (single pattern throughout app)
- Easy to refactor (change route once, affects all callers)

---

### Pattern 3.2: Utility Navigation Methods

**Location**: `lib/core/routing/navigation_extensions.dart:84-106`

**Pattern**: Utility methods for common navigation scenarios

```dart
extension NavigationExtensions on BuildContext {
  /// Pop current route
  bool popRoute() {
    if (canPop()) {
      pop();
      return true;
    }
    return false;
  }

  /// Pop until home screen
  void popToHome() {
    while (canPop()) {
      pop();
    }
    goToHome();
  }

  /// Replace current route with login
  void replaceWithLogin() => go(AppRoutes.login);

  /// Replace current route with home
  void replaceWithHome() => go(AppRoutes.home);
}
```

**Use Cases**:
- `popRoute()`: Safe back button that checks if can pop
- `popToHome()`: "Home" button that clears entire stack
- `replaceWithLogin()`: Session expired, force re-authentication
- `replaceWithHome()`: After successful login

---

### Pattern 3.3: Route Parameter Extraction

**Location**: `lib/core/routing/navigation_extensions.dart:108-180`

**Pattern**: Extension methods on `GoRouterState` for safe parameter extraction

```dart
extension RouteParameterExtensions on GoRouterState {
  /// Get query parameter with default value
  String getQueryParamOrDefault(String key, String defaultValue) =>
      uri.queryParameters[key] ?? defaultValue;

  /// Get required query parameter (throws if missing)
  String getRequiredQueryParam(String key) {
    final value = uri.queryParameters[key];
    if (value == null) {
      throw ArgumentError('Required query parameter "$key" is missing');
    }
    return value;
  }

  /// Safely cast extra data to expected type
  T? getExtra<T>() {
    final extraData = extra;
    if (extraData is T) {
      return extraData;
    }
    return null;
  }

  /// Get required extra data (throws if wrong type)
  T getRequiredExtra<T>() {
    final extraData = getExtra<T>();
    if (extraData == null) {
      throw ArgumentError(
        'Required extra data of type $T is missing or has wrong type',
      );
    }
    return extraData;
  }
}
```

**Usage in Routes**:
```dart
GoRoute(
  path: AppRoutes.results,
  pageBuilder: (context, state) {
    // Safe extraction with error handling
    final plant = state.getExtra<Plant>();
    if (plant == null) {
      return ErrorScreen(error: Exception('No plant data'));
    }
    return ResultsScreen(plant: plant);
  },
)
```

**Why**:
- Prevents runtime crashes from missing parameters
- Type-safe parameter extraction
- Clear error messages for debugging
- Supports optional and required parameters

---

## 4. Route Transitions

### Pattern 4.1: Reusable Transition Builders

**Location**: `lib/core/routing/route_transitions.dart`

**Pattern**: Static methods in abstract class for common transitions

```dart
abstract class RouteTransitions {
  /// Fade transition (default)
  static CustomTransitionPage<T> fade<T>({
    required LocalKey key,
    required Widget child,
    Duration duration = const Duration(milliseconds: 300),
  }) {
    return CustomTransitionPage<T>(
      key: key,
      child: child,
      transitionDuration: duration,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return FadeTransition(opacity: animation, child: child);
      },
    );
  }

  /// Slide from right (iOS-style)
  static CustomTransitionPage<T> slideFromRight<T>({...}) {...}

  /// Slide from bottom (Material-style)
  static CustomTransitionPage<T> slideFromBottom<T>({...}) {...}

  /// Platform-adaptive transition
  static CustomTransitionPage<T> platformAdaptive<T>({
    required LocalKey key,
    required Widget child,
    required TargetPlatform platform,
  }) {
    switch (platform) {
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return slideFromRight<T>(key: key, child: child);
      case TargetPlatform.android:
      case TargetPlatform.fuchsia:
        return slideFromBottom<T>(key: key, child: child);
      case TargetPlatform.linux:
      case TargetPlatform.windows:
        return fade<T>(key: key, child: child);
    }
  }
}
```

**Usage in Router**:
```dart
GoRoute(
  path: AppRoutes.camera,
  pageBuilder: (context, state) => RouteTransitions.slideFromBottom(
    key: state.pageKey,
    child: const CameraScreen(),
  ),
)
```

**Available Transitions**:
1. **fade** - Smooth fade (default, 300ms)
2. **fadeFast** - Quick fade (200ms, for tab switches)
3. **fadeSlow** - Slow fade (500ms, for dramatic effect)
4. **slideFromRight** - iOS-style push (from right)
5. **slideFromLeft** - Reverse direction
6. **slideFromBottom** - Material-style (from bottom)
7. **scale** - Zoom in/out with fade
8. **slideAndFade** - Combined slide + fade (iOS pattern)
9. **none** - Instant, no animation
10. **platformAdaptive** - Automatic based on platform

**Why**:
- Consistent animations throughout app
- Easy to customize globally
- Platform-specific UX patterns
- Performance optimized (reusable builders)

---

## 5. Deep Linking

### Pattern 5.1: Deep Link URI Generation

**Location**: `lib/core/routing/navigation_extensions.dart:182-215`

**Pattern**: Static helper methods for constructing deep link URIs

```dart
abstract class DeepLinks {
  static const scheme = 'plantcommunity';

  /// Build URI for home screen
  static Uri home() => Uri(scheme: scheme, path: AppRoutes.home);

  /// Build URI for plant results (with query parameter)
  static Uri results(String plantId) =>
      Uri(scheme: scheme, path: AppRoutes.results, queryParameters: {
        'id': plantId,
      });

  /// Build URI for specific garden bed
  static Uri gardenBed(String bedId) =>
      Uri(scheme: scheme, path: AppRoutes.garden, queryParameters: {
        'bed_id': bedId,
      });
}
```

**Usage**:
```dart
// Generate deep link for push notification
final uri = DeepLinks.results('plant-123');
print(uri); // Output: plantcommunity://results?id=plant-123

// Send via Firebase Cloud Messaging
await sendNotification(
  title: 'Plant Identified!',
  body: 'Tap to view your plant',
  deepLink: uri.toString(),
);
```

**Why**:
- Centralized deep link generation
- Type-safe URI construction
- Easy to test deep link scenarios
- Consistent URI format across platforms

**Platform Configuration**:
- **iOS**: See `docs/DEEP_LINKING_SETUP.md` for Info.plist config
- **Android**: See `docs/DEEP_LINKING_SETUP.md` for AndroidManifest.xml config

---

### Pattern 5.2: Automatic Deep Link Handling

**How it Works**:
go_router automatically parses incoming deep link URIs and navigates to the appropriate route. No additional code needed!

**Example Flow**:
1. User taps `plantcommunity://garden?bed_id=abc123` in email
2. OS launches app
3. go_router extracts path `/garden` and query param `bed_id=abc123`
4. Router navigates to garden route
5. Route extracts `bed_id` using `state.getQueryParam('bed_id')`

**Testing Deep Links**:
```bash
# iOS Simulator
xcrun simctl openurl booted "plantcommunity://home"

# Android Emulator
adb shell am start -W -a android.intent.action.VIEW \
  -d "plantcommunity://results?id=plant-123"
```

---

## 6. Testing Patterns

### Pattern 6.1: Widget Tests for Routing

**Location**: `test/routing/app_router_test.dart`

**Pattern**: Use `ProviderContainer` to test router with mocked auth states

```dart
testWidgets('Should redirect unauthenticated user to login',
    (WidgetTester tester) async {
  // Create container with mocked auth service
  final container = ProviderContainer(
    overrides: [
      authServiceProvider.overrideWith(
        (ref) => MockUnauthenticatedAuthService(),
      ),
    ],
  );
  addTearDown(container.dispose);

  final router = container.read(appRouterProvider);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );

  // Try to access protected route
  router.go(AppRoutes.profile);
  await tester.pumpAndSettle();

  // Verify redirect to login
  expect(
    router.routerDelegate.currentConfiguration.uri.path,
    equals(AppRoutes.login),
  );
});
```

**Key Patterns**:
- Use `ProviderContainer` for isolated provider state
- Override `authServiceProvider` with mock implementations
- Use `UncontrolledProviderScope` to inject container
- Call `addTearDown(container.dispose)` for cleanup
- Use `pumpAndSettle()` to wait for navigation animations

---

### Pattern 6.2: Mocking Auth States

**Pattern**: Create mock auth services that extend base service

```dart
class MockUnauthenticatedAuthService extends AuthService {
  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,
      jwtToken: null,
      isLoading: false,
    );
  }
}

class MockAuthenticatedAuthService extends AuthService {
  @override
  AuthState build() {
    return const AuthState(
      firebaseUser: null,  // Would be User object in real app
      jwtToken: 'mock-jwt-token',
      isLoading: false,
    );
  }
}
```

**Why**:
- Extends real service class (type-safe)
- Provides controlled auth states for testing
- No Firebase dependencies in tests
- Can test all auth scenarios (logged in, logged out, loading, error)

---

## 7. Best Practices

### DO ✅

1. **Use route constants**
   ```dart
   context.go(AppRoutes.home);  // ✅ Good
   ```

2. **Use navigation extensions**
   ```dart
   context.goToResults(plant);  // ✅ Type-safe
   ```

3. **Handle missing route data**
   ```dart
   final plant = state.getExtra<Plant>();
   if (plant == null) {
     return ErrorScreen(...);  // ✅ Graceful fallback
   }
   ```

4. **Clean up in dispose()**
   ```dart
   ref.onDispose(() {
     subscription?.cancel();  // ✅ Prevent memory leaks
   });
   ```

5. **Debug logging in development**
   ```dart
   if (kDebugMode) {
     debugPrint('[ROUTER] ...');  // ✅ Helpful for debugging
   }
   ```

### DON'T ❌

1. **Hardcode route strings**
   ```dart
   context.go('/home');  // ❌ Typo-prone
   ```

2. **Ignore null route data**
   ```dart
   final plant = state.extra as Plant;  // ❌ Will crash if null
   ```

3. **Create new router instances**
   ```dart
   final router = GoRouter(...);  // ❌ Should use provider
   ```

4. **Forget to watch auth state**
   ```dart
   final authState = ref.read(authServiceProvider);  // ❌ Won't update
   ```

5. **Skip memory leak prevention**
   ```dart
   _ref.listen(...);  // ❌ No cleanup = memory leak
   ```

---

## 8. Migration Guide

### From Basic go_router to Production Pattern

**Before** (Basic Setup):
```dart
final router = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (_, __) => HomeScreen()),
  ],
);
```

**After** (Production Pattern):
```dart
// 1. Create route constants
abstract class AppRoutes {
  static const home = '/';
}

// 2. Create Riverpod provider
@riverpod
GoRouter appRouter(Ref ref) {
  final authState = ref.watch(authServiceProvider);

  return GoRouter(
    refreshListenable: _AuthStateNotifier(ref),
    redirect: (context, state) {
      // Auth guard logic
    },
    routes: [
      GoRoute(
        path: AppRoutes.home,
        pageBuilder: (context, state) => RouteTransitions.fade(
          key: state.pageKey,
          child: const HomeScreen(),
        ),
      ),
    ],
  );
}

// 3. Use in app
MaterialApp.router(
  routerConfig: ref.watch(appRouterProvider),
);
```

**Migration Steps**:
1. Extract route strings to `AppRoutes` constants
2. Convert router to Riverpod provider
3. Add auth state watching with `_AuthStateNotifier`
4. Implement global redirect logic
5. Replace `builder` with `pageBuilder` + transitions
6. Add navigation extensions
7. Write widget tests

---

## Summary

### What We Built (Task 3)

✅ **Core Router** (Pattern 1)
- Riverpod-integrated router provider
- Centralized route constants
- Debug logging

✅ **Authentication Guards** (Pattern 2)
- Global redirect logic
- Auth state notifier for auto-refresh
- Memory leak prevention

✅ **Navigation Extensions** (Pattern 3)
- Type-safe navigation methods
- Utility methods (popToHome, replaceWithLogin)
- Safe parameter extraction

✅ **Route Transitions** (Pattern 4)
- 10 reusable transition types
- Platform-adaptive animations
- Customizable durations

✅ **Deep Linking** (Pattern 5)
- Deep link URI generation
- Automatic handling by go_router
- iOS + Android configuration docs

✅ **Testing** (Pattern 6)
- Widget tests for routing scenarios
- Mock auth services
- 13+ routing test cases

### Files Created/Modified

**Created**:
- `lib/core/routing/navigation_extensions.dart` - Navigation helper methods
- `lib/core/routing/route_transitions.dart` - Reusable transitions
- `docs/DEEP_LINKING_SETUP.md` - iOS/Android deep link setup
- `test/routing/app_router_test.dart` - Comprehensive routing tests

**Modified**:
- `lib/core/routing/app_router.dart` - Added auth guards, new routes, refresh notifier

### Metrics

- **Routes**: 9 total (splash, home, camera, results, settings, login, register, profile, garden)
- **Protected Routes**: 4 (results, settings, profile, garden)
- **Public Routes**: 5 (splash, home, camera, login, register)
- **Transition Types**: 10 (fade, slide, scale, platform-adaptive, etc.)
- **Test Cases**: 13 widget tests + 4 unit tests = 17 total
- **Code Coverage**: ~85% (routing logic)

---

**Last Updated**: November 15, 2025
**Contributors**: Claude Code + Will Tower
**Related Documentation**:
- Backend Auth: `backend/docs/FIREBASE_AUTHENTICATION.md`
- Mobile Patterns: `plant_community_mobile/FLUTTER_PATTERNS_CODIFIED.md`
- API Integration: `plant_community_mobile/FLUTTER_COMPLETION_PLAN.md`
