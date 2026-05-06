# Flutter Dependency Update Progress

**Date**: November 16, 2025 (updated May 5, 2026 — Phase 7)
**Branch**: `flutter-dependency-updates`
**Issue**: #206

---

## ✅ Completed Updates (Phase 6 - Backend Wagtail/Treebeard, May 2026)

### 6. wagtail: 7.3.1 → 7.4 (LTS) ✅
- **Status**: COMPLETE
- **Migrations applied**: `wagtailadmin.0006_formstate`, `wagtailcore.0097_baselogentry_uuid_action_timestamp_indexes`, `wagtailsearch.0010_add_text_fields`
- **Breaking Changes**: Removed Django 4.2 support (we use Django 5.2 — no impact). New StreamField `w-` CSS class prefix added alongside legacy classes (backwards compatible).
- **Security**: Fixes 5 CVEs (CVE-2026-44197–44201) for improper permission handling
- **Tests**: 548 passed, 45 failed (pre-existing), 2 skipped — zero regressions
- **Also upgraded**: `django-treebeard` 4.7.1 → 5.0.5 (auto-pulled as Wagtail 7.4 dependency), `modelsearch` 1.2.2 → 1.3.1

### 7. django-treebeard: 4.7.1 → 5.0.5 ✅
- **Status**: COMPLETE (installed as part of wagtail 7.4 resolution above)
- **Breaking Changes**: None for this project

### 8. CLAUDE.md: firebase-admin pin note updated ✅
- Changed `>=6.6.0,<7.0.0` → `>=7.4.0`

### 9. Flutter SDK upgrade: 3.38.1 → 3.41.9 / Dart 3.10.0 → 3.11.5 ✅
- **Status**: COMPLETE (May 5, 2026)
- **Command**: `flutter upgrade`
- **Tests**: 59 passing, 3 skipped — zero regressions

### 10. flutter_riverpod 3.3.1 ✅ (already resolved)
- **Status**: CONFIRMED IN LOCKFILE — lockfile already had 3.3.1 (satisfies `^3.1.0`)
- **No pubspec.yaml change needed**

### 11. riverpod_generator 4.0.3 ✅ (already resolved)
- **Status**: CONFIRMED IN LOCKFILE — lockfile already had 4.0.3 (satisfies `^4.0.0+1`)
- **No pubspec.yaml change needed**

### 12. drift / drift_dev: 2.31.0 → 2.33.0 ⏸️ STILL DEFERRED
- **Blocker (updated)**: Flutter SDK 3.41.9 pins `meta: 1.17.0` exactly in its own pubspec
  - `drift 2.33.0` requires `sqlite3: ^3.1.5`
  - `sqlite3 3.x` + `drift_dev >= 2.32.1` (needs `analyzer >= 10.0.x`) + Flutter meta pin = unsolvable
  - `analyzer >= 10.0.2` requires `meta ^1.18.0`, which conflicts with Flutter SDK's `meta 1.17.0` pin
- **Resolution**: Blocked until Flutter SDK updates its bundled `meta` to `>= 1.18.0`
- **Previous blocker**: Dart SDK < 3.11 — now resolved (Dart 3.11.5)

---

## ✅ Completed Updates (Phase 1 - High Priority)

### 1. flutter_dotenv: 5.2.1 → 6.0.0 ✅
- **Status**: COMPLETE
- **Tests**: 15/15 passing (API service tests)
- **Breaking Changes**: None detected
- **Commit**: a79461d

### 2. permission_handler: 11.4.0 → 12.0.1 ✅ (CRITICAL)
- **Status**: COMPLETE
- **Transitive Updates**: permission_handler_android 12.1.0 → 13.0.1
- **Tests**: No new compilation errors
- **Breaking Changes**: None detected (requires manual testing on devices)
- **Commit**: 864deed
- **⚠️ Note**: Manual testing required for camera/gallery permissions on iOS and Android

### 3. geocoding: 3.0.0 → 4.0.0 ✅
- **Status**: COMPLETE
- **Transitive Updates**: geocoding_android 3.3.1 → 4.0.1
- **Tests**: No geocoding-related errors
- **Breaking Changes**: None detected
- **Commit**: 72ff965

---

## 🔄 In Progress (Phase 2 & 3)

### 4. flutter_secure_storage Platform Updates ⏸️ BLOCKED
- **Status**: BLOCKED by version constraints
- **Current Version**: 9.2.4 (latest stable)
- **Platform Packages Need**: 2.x and 4.x updates
- **Blocker**: Platform package major version updates require flutter_secure_storage v10.x
- **Available**: v10.0.0-beta.4 exists but is not stable
- **Decision**: Defer until stable v10.x release
- **Security Impact**: Current 9.2.4 version is secure and functional

### 5. Integration Test Mock Service Fixes ✅ COMPLETE PENDING TOOLCHAIN VALIDATION
- **Status**: Source updated; pending validation in a Flutter-capable environment
- **Root Cause**: Dio 5.8+ API changes (http package 1.5.0 → 1.6.0 update)
- **Completed**:
  - ✅ `test/integration/offline_sync_test.dart` (OfflineApiService, OnlineApiService)
    - Added `Options? options` parameter to all HTTP methods
    - Added `queryParameters` to post/put/patch/delete
    - Fixed uploadFile signature (fieldName default, callback type)
  - Commit: 264abeb

- **Completed Follow-up**:
  - ✅ `test/integration/plant_identification_flow_test.dart`
    - MockApiService signatures match `ApiService`
    - FailingApiService signatures match `ApiService`
    - EmptyResponseApiService signatures match `ApiService`
  - ✅ Firestore service overrides use the current generated-provider override pattern
  - ⚠️ Could not run `flutter test` in the current cloud workspace because Flutter/Dart are not installed

---

## 📋 Remaining Work

### Phase 3: Validate Integration Test Fixes
**Priority**: HIGH
**Estimated Time**: 30 minutes in a Flutter-capable environment

1. Run the integration-test compile checks:
   ```bash
   cd plant_community_mobile
   flutter test test/integration/offline_sync_test.dart
   flutter test test/integration/plant_identification_flow_test.dart
   ```

2. If failures remain, treat them as runtime expectations rather than known mock-signature drift unless the analyzer reports new signature mismatches.

### Phase 4: Low-Priority Transitive Dependencies
**Priority**: LOW
**Estimated Time**: 20 minutes

Update remaining 20 packages using `flutter pub upgrade`:
- flutter_local_notifications: 18.0.1 → 19.5.0 (defer - not implemented yet)
- package_info_plus: 8.3.1 → 9.0.0
- sqlite3: 2.9.4 → 3.0.1
- material_color_utilities: 0.11.1 → 0.13.0
- js: 0.6.7 → 0.7.2
- test: 1.26.3 → 1.27.0
- Plus 14 more transitive dependencies

### Phase 5: Final Validation
**Priority**: HIGH
**Estimated Time**: 30 minutes

1. Run full test suite: `flutter test`
2. Run flutter analyze: `flutter analyze`
3. Verify zero errors (warnings OK)
4. Check that API service tests still pass
5. Document any known issues in PR

---

## 🚀 Deployment Notes

### Manual Testing Required Before Merge:
- [ ] Test camera permissions on iOS physical device
- [ ] Test camera permissions on Android physical device
- [ ] Test gallery/photo picker on both platforms
- [ ] Verify environment variables load correctly (`flutter run -d macos`)
- [ ] Verify authentication flow works (login/logout)

### Merge Checklist:
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Flutter analyze shows 0 errors
- [ ] Manual testing on iOS and Android complete
- [ ] PR created with detailed changelog
- [ ] Known issues documented

---

## 📊 Summary

**Total Packages Updated**: 7
- ✅ Complete: 3 (flutter_dotenv, permission_handler, geocoding)
- ⏸️ Blocked: 1 (flutter_secure_storage - awaiting stable v10)
- 🟡 Pending validation: 1 (integration test source fixes)
- 📋 Pending: 1 (low-priority updates)

**Test Status**:
- API Service Tests: ✅ previously passing in Flutter environment
- Integration Tests: 🟡 source updated; requires Flutter environment validation
- Overall Status: 🟡 In Progress pending `flutter test` and `flutter analyze`

**Estimated Time to Complete**: 1-2 hours in a Flutter-capable environment
- Integration test validation: 30 min
- Low-priority updates: 20 min
- Final validation: 30 min
- Buffer: 20 min

---

## 🔗 Related Files

- Work Plan: `plant_community_mobile/FLUTTER_DEPENDENCY_UPDATES_REMAINING.md`
- Test Files:
  - `test/integration/offline_sync_test.dart` (fixed)
  - `test/integration/plant_identification_flow_test.dart` (source fixed; needs Flutter validation)
  - `test/api_service_test.dart` (passing)

---

**Next Steps for Next Session**:
1. Run integration tests to verify source-level fixes
2. Run full test suite and flutter analyze
3. Complete manual iOS/Android permission and auth smoke tests
4. Update low-priority dependencies when toolchain validation is available
5. Create pull request

---

**Generated**: 2025-11-16
**Last Updated**: 2026-05-05

---

## ✅ Web Frontend Major Upgrades (May 5, 2026)

All 7 upgrade branches merged into `main`. Final state:

| Package | Old | New | Branch |
|---------|-----|-----|--------|
| vite | ^7.1 | ^8.0.10 | `upgrade/vite-8` |
| typescript | ^5.9 | ^6.0.3 | `upgrade/typescript-6` |
| eslint | ^9.39 | ^10.3.0 | `upgrade/eslint-10` |
| @eslint/js | ^9.39 | ^10.0.1 | `upgrade/eslint-10` |
| @vitejs/plugin-react | ^5.2 | ^6.0.1 | `upgrade/vite-8` |
| lucide-react | ^0.552 | ^1.14.0 | `upgrade/lucide-react-1` |
| jsdom | ^27.1 | ^29.1.1 | `upgrade/jsdom-29` |
| globals | ^16.5 | ^17.6.0 | `upgrade/web-remaining-majors` |
| rollup-plugin-visualizer | ^6.0 | ^7.0.1 | `upgrade/web-remaining-majors` |

**Verification**: 669/669 tests passing, 0 lint warnings, 0 TypeScript errors, build clean.
