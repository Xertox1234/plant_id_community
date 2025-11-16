# Flutter Dependency Updates - Remaining Work

**Date Created**: November 16, 2025
**Status**: Pending - Major Version Updates Required
**Context**: Follow-up to commit `49668ef` (Flutter dependency audit)

---

## Overview

This document tracks remaining Flutter dependency updates that require major version changes and individual testing. These were identified during the Flutter dependency audit but not updated due to breaking changes.

**Completed in Previous Session:**
- ✅ Flutter switched to stable 3.38.1 (from beta 3.37.0-0.1.pre)
- ✅ 5 safe dependencies updated (minor/patch versions)
- ✅ Code regenerated with build_runner
- ✅ API service tests passing (14/18)

---

## Remaining Major Version Updates (25 packages)

### High Priority (Direct Dependencies)

#### 1. `flutter_dotenv` (5.2.1 → 6.0.0)
**Impact**: Environment variable management
**Breaking Changes**: Likely API changes in how env vars are loaded
**Testing Required**:
- Verify `.env` file loading still works
- Test environment variable access in all services
- Check error handling for missing env vars

**Files to Review**:
- `lib/services/api_service.dart` (uses env vars for API_BASE_URL)
- `test/api_service_test.dart`

---

#### 2. `flutter_local_notifications` (18.0.1 → 19.5.0)
**Impact**: Push notifications (not yet implemented)
**Breaking Changes**: Android/iOS notification configuration
**Testing Required**:
- Not critical - notifications not yet implemented
- Review when implementing notifications feature

**Files to Review**:
- None (feature not implemented yet)

---

#### 3. `geocoding` (3.0.0 → 4.0.0)
**Impact**: Location services (garden feature)
**Breaking Changes**: API method signatures, error handling
**Testing Required**:
- Test location permission requests
- Verify geocoding service initialization
- Check error handling for location failures

**Files to Review**:
- `lib/features/garden/**/*.dart` (location features)
- Garden-related tests

---

#### 4. `permission_handler` (11.4.0 → 12.0.1)
**Impact**: Camera, location, storage permissions
**Breaking Changes**: Permission request API changes
**Testing Required**:
- Camera permissions (critical - plant identification)
- Photo gallery permissions (critical - image picker)
- Location permissions (garden feature)
- Test on both iOS and Android

**Files to Review**:
- `lib/features/camera/camera_screen.dart`
- `lib/features/garden/**/*.dart`

---

### Medium Priority (Platform Interfaces)

#### 5. `flutter_secure_storage` Platform Updates
**Packages**:
- `flutter_secure_storage_linux`: 1.2.3 → 2.0.1
- `flutter_secure_storage_macos`: 3.1.3 → 4.0.0
- `flutter_secure_storage_platform_interface`: 1.1.2 → 2.0.1
- `flutter_secure_storage_web`: 1.2.1 → 2.0.0
- `flutter_secure_storage_windows`: 3.1.2 → 4.0.0

**Impact**: JWT token storage (CRITICAL for authentication)
**Breaking Changes**: Platform-specific API changes
**Testing Required**:
- Test JWT token storage/retrieval
- Test token deletion (logout)
- Verify Firebase auth token exchange
- Test on ALL platforms: iOS, Android, macOS, web

**Files to Review**:
- `lib/services/auth_service.dart` (JWT storage)
- `test/services/auth_service_test.dart`

**⚠️ SECURITY CRITICAL**: This affects authentication - test thoroughly!

---

### Low Priority (Transitive Dependencies)

#### 6. Other Updates Available
- `package_info_plus`: 8.3.1 → 9.0.0
- `sqlite3`: 2.9.4 → 3.0.1
- `material_color_utilities`: 0.11.1 → 0.13.0
- `js`: 0.6.7 → 0.7.2
- `test`: 1.26.3 → 1.27.0
- Plus 18 more transitive dependencies

**Impact**: Low - mostly internal/test dependencies
**Action**: Update after high/medium priority updates complete

---

## Integration Test Fixes Required

### Issue: API Service Interface Changes
**Cause**: `http` package update (1.5.0 → 1.6.0) added `Options?` parameter to all methods

**Affected Files**:
- `test/integration/offline_sync_test.dart` (57 errors)
- `test/integration/plant_identification_flow_test.dart` (additional errors)

**Errors**:
```dart
// ❌ OLD (broken after http 1.6.0 update):
Future<Response> get(String path, {Map<String, dynamic>? queryParameters})

// ✅ NEW (required):
Future<Response> get(
  String path,
  {
    Options? options,
    Map<String, dynamic>? queryParameters
  }
)
```

**Fix Required for All Mock Services**:
- `MockApiService` - all HTTP methods
- `FailingApiService` - all HTTP methods
- `EmptyResponseApiService` - all HTTP methods
- `OfflineApiService` - all HTTP methods
- `OnlineApiService` - all HTTP methods

**Methods to Update**:
- `get()` - add `Options? options` parameter
- `post()` - add `Options? options, Map<String, dynamic>? queryParameters`
- `put()` - add `Options? options, Map<String, dynamic>? queryParameters`
- `patch()` - add `Options? options, Map<String, dynamic>? queryParameters`
- `delete()` - add `dynamic data, Options? options, Map<String, dynamic>? queryParameters`
- `uploadFile()` - change `required String fieldName` to `String fieldName` (optional)

**Also Fix**:
- `MockFirestoreService` - change from `extends FirestoreService` to proper override pattern
- `MockFirebaseStorageService` - verify override pattern

---

## Production Code Issues (Low Priority)

### Missing Route Definitions (8 errors)
**Files**: `lib/core/routing/navigation_extensions.dart`

**Missing Routes**:
- `AppRoutes.login` (3 occurrences)
- `AppRoutes.register` (1 occurrence)
- `AppRoutes.profile` (3 occurrences)
- `AppRoutes.garden` (4 occurrences)

**Action**: These are future features - routes not yet implemented in `app_router.dart`

### Unused Code (2 warnings)
**File**: `lib/features/camera/camera_screen.dart`

**Issues**:
- `_uploadProgress` field declared but never used
- `_useSampleImage()` method declared but never used (sample images commented out)

**Action**: Either use these or remove them

---

## Testing Strategy

### Phase 1: Update High Priority Dependencies (One at a Time)

1. **flutter_dotenv (6.0.0)**
   ```bash
   # Update pubspec.yaml
   flutter_dotenv: ^6.0.0

   # Update
   flutter pub upgrade flutter_dotenv

   # Test
   flutter test test/api_service_test.dart
   flutter run -d macos  # Verify env loading
   ```

2. **permission_handler (12.0.1)**
   ```bash
   # Update
   flutter pub upgrade permission_handler

   # Test on BOTH platforms
   flutter run -d ios
   flutter run -d android

   # Test camera permissions manually
   # Test gallery permissions manually
   ```

3. **geocoding (4.0.0)**
   ```bash
   # Update
   flutter pub upgrade geocoding

   # Test garden features
   flutter test test/features/garden/
   ```

### Phase 2: Update flutter_secure_storage (CRITICAL)

⚠️ **SECURITY CRITICAL** - Test thoroughly on all platforms!

```bash
# Update all platform packages
flutter pub upgrade flutter_secure_storage flutter_secure_storage_linux flutter_secure_storage_macos flutter_secure_storage_platform_interface flutter_secure_storage_web flutter_secure_storage_windows

# Test authentication flow on ALL platforms
flutter test test/services/auth_service_test.dart

# Manual testing
flutter run -d ios       # Test login/logout
flutter run -d android   # Test login/logout
flutter run -d macos     # Test login/logout
flutter run -d chrome    # Test login/logout (web)

# Verify JWT token storage/retrieval
# Verify Firebase auth token exchange
# Verify logout clears tokens
```

### Phase 3: Fix Integration Tests

1. **Update Mock Services** (add `Options?` parameters to all methods)
2. **Update MockFirestoreService** (fix override pattern)
3. **Run Tests**:
   ```bash
   flutter test test/integration/offline_sync_test.dart
   flutter test test/integration/plant_identification_flow_test.dart
   ```

### Phase 4: Update Low Priority Dependencies

```bash
flutter pub upgrade  # Update all remaining compatible packages
flutter test         # Run full test suite
flutter analyze      # Check for issues
```

---

## Success Criteria

### Must Pass Before Merging:
- ✅ All unit tests passing
- ✅ All integration tests passing
- ✅ Flutter analyze shows 0 errors (warnings OK)
- ✅ Manual testing on iOS and Android
- ✅ Authentication flow works (login/logout)
- ✅ Camera permissions work (plant identification)
- ✅ Environment variables load correctly

### Nice to Have:
- 🎯 Security scanner passes (if script fixed)
- 🎯 All warnings resolved
- 🎯 Test coverage maintained or improved

---

## Breaking Changes Documentation

### Expect Breaking Changes In:

1. **flutter_dotenv 6.0.0**
   - May require different initialization
   - Check for API changes in loading env files

2. **permission_handler 12.0.0**
   - Android permissions API changes
   - iOS permission descriptions may need updates

3. **flutter_secure_storage 2.x/4.x**
   - Platform-specific API changes
   - Initialization may be different
   - Key storage format may change (migration needed?)

4. **geocoding 4.0.0**
   - API method signatures likely changed
   - Error handling may be different

---

## Commands Reference

```bash
# Check what updates are available
flutter pub outdated

# Update specific package
flutter pub upgrade package_name

# Update all packages (respecting version constraints)
flutter pub upgrade

# Regenerate code after updates
flutter pub run build_runner build --delete-conflicting-outputs

# Run tests
flutter test
flutter test test/specific_test.dart

# Static analysis
flutter analyze

# Manual testing
flutter run -d ios
flutter run -d android
flutter run -d macos
flutter run -d chrome
```

---

## Timeline Estimate

**Phase 1 (High Priority)**: 2-3 hours
- flutter_dotenv: 30 min
- permission_handler: 1 hour (iOS + Android testing)
- geocoding: 30 min

**Phase 2 (flutter_secure_storage)**: 2-3 hours
- Update all platform packages: 30 min
- Testing on all platforms: 1.5-2 hours
- Security verification: 30 min

**Phase 3 (Integration Tests)**: 1-2 hours
- Mock service updates: 1 hour
- Testing: 30 min - 1 hour

**Phase 4 (Low Priority)**: 1 hour
- Update remaining packages: 20 min
- Full test suite: 30 min
- Verification: 10 min

**Total Estimated Time**: 6-9 hours

---

## Risks and Mitigation

### Risk: flutter_secure_storage breaks authentication
**Mitigation**:
- Test thoroughly on all platforms before merging
- Keep old version in git history for rollback
- Consider creating migration code for token storage

### Risk: permission_handler breaks camera/gallery
**Mitigation**:
- Test on physical devices (not just simulator)
- Test both camera and gallery permissions
- Keep screenshots of permission dialogs

### Risk: Breaking changes require code refactoring
**Mitigation**:
- Update packages one at a time
- Commit after each successful update
- Easy to identify which package caused issues

---

## Next Session Checklist

- [ ] Read this document thoroughly
- [ ] Start with Phase 1 (flutter_dotenv)
- [ ] Update one package at a time
- [ ] Run tests after each update
- [ ] Commit after each successful update
- [ ] If any update fails, document the issue and move to next
- [ ] Complete integration test fixes
- [ ] Full test suite before final commit

---

## Related Files

- `/plant_community_mobile/pubspec.yaml` - Dependency manifest
- `/plant_community_mobile/pubspec.lock` - Locked versions
- `/plant_community_mobile/lib/services/api_service.dart` - HTTP client
- `/plant_community_mobile/lib/services/auth_service.dart` - Authentication
- `/plant_community_mobile/test/integration/` - Integration tests
- `.github/workflows/security-scan.yml` - CI configuration

---

## Questions for Next Session

1. Should we update `flutter_local_notifications` now or wait until notifications are implemented?
2. Do we need to support web platform for secure storage? (affects testing)
3. Should integration tests be fixed before or after major updates?
4. Do we want to tackle low-priority transitive dependencies or just high/medium priority?

---

**End of Document**
