# Flutter Mobile App - Completion Plan

**Date**: November 14, 2025
**Goal**: Finish primary mobile platform with full backend integration
**Timeline**: 2-3 weeks
**Current Status**: MVP Complete (Grade B+) → Production-Ready (Grade A)

---

## Current State Analysis

### ✅ What's Already Implemented

1. **Core Architecture** ✅
   - Flutter 3.27 + Dart SDK 3.9.x
   - Riverpod 3.x state management with code generation
   - go_router 17.0.0 for type-safe navigation
   - Material Design 3 with dark mode support
   - Firebase Core initialized with .env security

2. **Screens Implemented** ✅
   - Splash Screen (animated logo)
   - Home Page (hero section, feature cards)
   - Camera Screen (photo/gallery picker)
   - Results Screen (plant details display)

3. **Reusable Widgets** ✅
   - GradientButton (custom styled button)
   - FeatureCard (home page cards)
   - LoadingIndicator (consistent loading UI)

4. **Mock Services** ✅
   - MockPlantService with 4-plant database
   - 2-second simulated API delay
   - Random plant selection

5. **Dependencies Installed** ✅
   - `dio: ^5.8.1` - HTTP client
   - `firebase_auth: ^6.1.2` - Authentication
   - `cloud_firestore: ^6.1.0` - Offline sync
   - `firebase_storage: ^13.0.4` - Image uploads
   - `image_picker: ^1.2.0` - Camera/gallery
   - `cached_network_image: ^3.4.1` - Image caching

### ❌ What's Missing (12 Tasks)

1. API service layer for Django backend
2. Firebase Authentication with JWT
3. Real PlantIdentificationService
4. Image upload to Firebase Storage
5. Firestore offline sync
6. User profile management
7. Garden tracking integration
8. Error handling & retry logic
9. Loading states & user feedback
10. Integration tests
11. Replace mock with real backend
12. End-to-end testing

---

## Architecture Overview

### Service Layer Architecture

```
┌─────────────────────────────────────────┐
│         Flutter Mobile App              │
├─────────────────────────────────────────┤
│  Screens (UI)                           │
│    ├─ Splash, Home, Camera, Results    │
│    └─ Profile, Garden, Settings        │
├─────────────────────────────────────────┤
│  Providers (State Management)           │
│    ├─ AuthProvider                      │
│    ├─ PlantProvider                     │
│    └─ GardenProvider                    │
├─────────────────────────────────────────┤
│  Services (Business Logic)              │
│    ├─ ApiService (Dio HTTP)            │
│    ├─ AuthService (Firebase + Django)  │
│    ├─ PlantIdentificationService       │
│    ├─ StorageService (Firebase)        │
│    ├─ FirestoreService (Offline)       │
│    └─ GardenService                     │
└─────────────────────────────────────────┘
           ↓          ↓          ↓
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Django   │ │ Firebase │ │ Firebase │
    │ Backend  │ │ Auth     │ │ Firestore│
    │ REST API │ │          │ │ Storage  │
    └──────────┘ └──────────┘ └──────────┘
```

### Data Flow

1. **Authentication Flow**:
   - User signs in → Firebase Auth → Get JWT token
   - JWT token → Django backend for API authorization
   - Token stored in secure storage (flutter_secure_storage)

2. **Plant Identification Flow**:
   - User takes photo → Upload to Firebase Storage → Get URL
   - Call Django `/api/v1/plant-identification/identify/` with image URL
   - Receive PlantSpecies data → Save to Firestore for offline
   - Display results → Option to save to garden

3. **Garden Tracking Flow**:
   - Save plant → Django `/api/v1/calendar/api/plants/`
   - Sync to Firestore for offline access
   - Create care reminders → Django `/api/v1/calendar/api/care-tasks/`
   - View in garden → Django `/api/v1/calendar/api/garden-beds/`

---

## Detailed Implementation Steps

### Task 1: Create API Service Layer ✅ Priority: HIGHEST

**File**: `lib/services/api_service.dart`

**Purpose**: Centralized HTTP client for Django backend

**Implementation**:
```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class ApiService {
  final Dio _dio;
  final String baseUrl;

  ApiService({
    required this.baseUrl,
    String? authToken,
  }) : _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl,
            connectTimeout: const Duration(seconds: 10),
            receiveTimeout: const Duration(seconds: 30),
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
              if (authToken != null) 'Authorization': 'Bearer $authToken',
            },
          ),
        ) {
    // Add interceptors for logging, error handling
    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
    ));

    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (error, handler) async {
          // Handle 401 (token expired) → refresh token
          // Handle 429 (rate limited) → retry with backoff
          // Handle 5xx (server error) → retry logic
          return handler.next(error);
        },
      ),
    );
  }

  // GET request
  Future<Response> get(String path, {Map<String, dynamic>? queryParameters}) {
    return _dio.get(path, queryParameters: queryParameters);
  }

  // POST request
  Future<Response> post(String path, {dynamic data}) {
    return _dio.post(path, data: data);
  }

  // PATCH request
  Future<Response> patch(String path, {dynamic data}) {
    return _dio.patch(path, data: data);
  }

  // DELETE request
  Future<Response> delete(String path) {
    return _dio.delete(path);
  }

  // Multipart upload (for images)
  Future<Response> uploadFile(
    String path,
    String filePath, {
    Map<String, dynamic>? data,
  }) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(filePath),
      if (data != null) ...data,
    });

    return _dio.post(path, data: formData);
  }
}

// Provider
final apiServiceProvider = Provider<ApiService>((ref) {
  // TODO: Get base URL from .env
  // TODO: Get auth token from AuthService
  return ApiService(
    baseUrl: 'http://localhost:8000/api/v1',
    authToken: null, // Will be set by AuthService
  );
});
```

**Testing**:
- Test GET /plant-identification/
- Test POST /plant-identification/identify/
- Test error handling (network failure, 404, 500)

**Estimate**: 3-4 hours

---

### Task 2: Implement Firebase Authentication + JWT

**File**: `lib/services/auth_service.dart`

**Purpose**: Handle Firebase Auth + Django JWT token exchange

**Flow**:
1. User signs in with Firebase (email/password, Google, Apple)
2. Get Firebase ID token
3. Exchange token with Django backend → Get JWT
4. Store JWT in secure storage
5. Use JWT for all API calls

**Implementation**:
```dart
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'api_service.dart';

part 'auth_service.g.dart';

@riverpod
class AuthService extends _$AuthService {
  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();
  static const String _jwtKey = 'django_jwt_token';

  @override
  User? build() {
    // Listen to Firebase auth state changes
    _firebaseAuth.authStateChanges().listen((user) {
      state = user;
      if (user != null) {
        _exchangeFirebaseTokenForJWT(user);
      } else {
        _clearJWT();
      }
    });

    return _firebaseAuth.currentUser;
  }

  // Sign in with email/password
  Future<void> signInWithEmailPassword(String email, String password) async {
    try {
      await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      throw Exception('Sign in failed: $e');
    }
  }

  // Register new user
  Future<void> registerWithEmailPassword(
    String email,
    String password,
    String displayName,
  ) async {
    try {
      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );

      await credential.user?.updateDisplayName(displayName);
    } catch (e) {
      throw Exception('Registration failed: $e');
    }
  }

  // Sign out
  Future<void> signOut() async {
    await _firebaseAuth.signOut();
    await _clearJWT();
  }

  // Exchange Firebase token for Django JWT
  Future<void> _exchangeFirebaseTokenForJWT(User user) async {
    try {
      // Get Firebase ID token
      final firebaseToken = await user.getIdToken();

      // Call Django backend to exchange token
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.post(
        '/auth/firebase-token-exchange/',
        data: {'firebase_token': firebaseToken},
      );

      // Store Django JWT
      final jwtToken = response.data['jwt_token'];
      await _secureStorage.write(key: _jwtKey, value: jwtToken);

      // Update ApiService with new token
      // TODO: Implement token refresh in ApiService
    } catch (e) {
      print('[AUTH] Failed to exchange token: $e');
    }
  }

  // Get stored JWT
  Future<String?> getJWT() async {
    return await _secureStorage.read(key: _jwtKey);
  }

  // Clear JWT
  Future<void> _clearJWT() async {
    await _secureStorage.delete(key: _jwtKey);
  }
}
```

**Backend Integration**:
- Django endpoint: `/api/v1/auth/firebase-token-exchange/`
- Validates Firebase token
- Creates/gets User in Django
- Returns JWT token

**Testing**:
- Test registration flow
- Test sign in/sign out
- Test token exchange
- Test token refresh on expiry

**Estimate**: 4-6 hours

---

### Task 3: Create PlantIdentificationService

**File**: `lib/services/plant_identification_service.dart`

**Purpose**: Call Django plant ID API

**Implementation**:
```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../models/plant.dart';
import 'api_service.dart';
import 'storage_service.dart';

part 'plant_identification_service.g.dart';

@riverpod
class PlantIdentificationService extends _$PlantIdentificationService {
  @override
  FutureOr<List<Plant>> build() async {
    // Load identified plants from Firestore
    return [];
  }

  // Identify plant from image
  Future<Plant> identifyPlant(String imagePath) async {
    try {
      // 1. Upload image to Firebase Storage
      final storageService = ref.read(storageServiceProvider);
      final imageUrl = await storageService.uploadImage(imagePath);

      // 2. Call Django backend
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.post(
        '/plant-identification/identify/',
        data: {
          'image_url': imageUrl,
          'latitude': null, // Optional: user location
          'longitude': null,
        },
      );

      // 3. Parse response
      final plantData = response.data;
      final plant = Plant.fromJson(plantData);

      // 4. Save to Firestore for offline access
      await _savePlantToFirestore(plant);

      // 5. Update state
      state = AsyncValue.data([...state.value ?? [], plant]);

      return plant;
    } catch (e) {
      throw Exception('Plant identification failed: $e');
    }
  }

  // Get plant care instructions
  Future<Map<String, dynamic>> getCareinstructions(String plantId) async {
    final apiService = ref.read(apiServiceProvider);
    final response = await apiService.get('/plant-identification/$plantId/');
    return response.data;
  }

  // Save plant to Firestore (offline sync)
  Future<void> _savePlantToFirestore(Plant plant) async {
    // TODO: Implement Firestore save
  }
}
```

**Django Backend Endpoints Used**:
- `POST /api/v1/plant-identification/identify/` - Identify plant
- `GET /api/v1/plant-identification/{uuid}/` - Get plant details
- `GET /api/v1/plant-identification/species/` - List all species

**Testing**:
- Test identify with real image
- Test error handling (network failure, invalid image)
- Test offline fallback

**Estimate**: 3-4 hours

---

### Task 4: Implement Firebase Storage Service

**File**: `lib/services/storage_service.dart`

**Purpose**: Upload images to Firebase Storage

**Implementation**:
```dart
import 'dart:io';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:path/path.dart' as path;
import 'package:uuid/uuid.dart';

class StorageService {
  final FirebaseStorage _storage = FirebaseStorage.instance;
  final Uuid _uuid = const Uuid();

  // Upload image and return download URL
  Future<String> uploadImage(String filePath) async {
    try {
      // Generate unique filename
      final fileName = '${_uuid.v4()}${path.extension(filePath)}';
      final ref = _storage.ref().child('plant_images/$fileName');

      // Upload file
      final uploadTask = await ref.putFile(File(filePath));

      // Get download URL
      final downloadUrl = await uploadTask.ref.getDownloadURL();

      return downloadUrl;
    } catch (e) {
      throw Exception('Image upload failed: $e');
    }
  }

  // Delete image
  Future<void> deleteImage(String imageUrl) async {
    try {
      final ref = _storage.refFromURL(imageUrl);
      await ref.delete();
    } catch (e) {
      print('[STORAGE] Delete failed: $e');
    }
  }
}

final storageServiceProvider = Provider<StorageService>((ref) {
  return StorageService();
});
```

**Security Rules** (Firebase Console):
```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /plant_images/{imageId} {
      // Allow authenticated users to upload
      allow write: if request.auth != null
                   && request.resource.size < 10 * 1024 * 1024 // 10MB max
                   && request.resource.contentType.matches('image/.*');

      // Allow anyone to read (for public plant database)
      allow read: if true;
    }
  }
}
```

**Testing**:
- Test upload with valid image
- Test upload with >10MB image (should fail)
- Test upload with non-image file (should fail)
- Test delete

**Estimate**: 2-3 hours

---

### Task 5: Add Firestore Offline Sync

**File**: `lib/services/firestore_service.dart`

**Purpose**: Sync data to Firestore for offline access

**Collections Structure**:
```
/users/{userId}/
  ├─ identified_plants/
  │   ├─ {plantId}/
  │   │   ├─ id: string
  │   │   ├─ name: string
  │   │   ├─ scientificName: string
  │   │   ├─ imageUrl: string
  │   │   ├─ timestamp: timestamp
  │   │   └─ care: array
  │
  ├─ garden_beds/
  │   ├─ {bedId}/
  │   │   ├─ id: string
  │   │   ├─ name: string
  │   │   ├─ plants: array
  │   │   └─ created_at: timestamp
  │
  └─ care_tasks/
      ├─ {taskId}/
          ├─ plantId: string
          ├─ taskType: string
          ├─ scheduledDate: timestamp
          └─ completed: boolean
```

**Implementation**:
```dart
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../models/plant.dart';

class FirestoreService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  // Save identified plant
  Future<void> savePlant(String userId, Plant plant) async {
    await _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .doc(plant.id)
        .set(plant.toJson());
  }

  // Get all identified plants (with offline persistence)
  Stream<List<Plant>> getPlantsStream(String userId) {
    return _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .orderBy('timestamp', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => Plant.fromJson(doc.data()))
            .toList());
  }

  // Delete plant
  Future<void> deletePlant(String userId, String plantId) async {
    await _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .doc(plantId)
        .delete();
  }
}

final firestoreServiceProvider = Provider<FirestoreService>((ref) {
  return FirestoreService();
});
```

**Firestore Security Rules**:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only access their own data
    match /users/{userId}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

**Testing**:
- Test offline write → sync when online
- Test offline read (cached data)
- Test real-time updates

**Estimate**: 3-4 hours

---

### Task 6-12: Additional Implementation Details

Due to length constraints, the remaining tasks are summarized:

**Task 6: User Profile Management** (3-4 hours)
- Profile screen with display name, email, photo
- Settings: theme, notifications, logout
- Provider: `UserProfileProvider`

**Task 7: Garden Tracking Integration** (4-6 hours)
- Create `GardenService` calling Django Garden Calendar API
- Sync garden beds, plants, care tasks
- Bidirectional sync: Firestore ↔ Django

**Task 8: Error Handling & Retry Logic** (2-3 hours)
- Implement exponential backoff for retries
- User-friendly error messages
- Network status monitoring

**Task 9: Loading States & User Feedback** (2-3 hours)
- Shimmer loading for lists
- Progress indicators for uploads
- Success/error snackbars

**Task 10: Integration Tests** (4-6 hours)
- Test camera → identify → save flow
- Test offline mode
- Test sync when back online

**Task 11: Replace Mock with Real Backend** (1-2 hours)
- Remove `MockPlantService`
- Update all screens to use real services
- Test thoroughly

**Task 12: End-to-End Testing** (4-6 hours)
- Manual testing on iOS/Android
- Test all user journeys
- Fix bugs found during testing

---

## Backend Integration Checklist

### Django Endpoints Required

✅ Already Implemented:
- `POST /api/v1/plant-identification/identify/` - Plant identification
- `GET /api/v1/plant-identification/{uuid}/` - Plant details
- `GET /api/v1/calendar/api/garden-beds/` - List garden beds
- `POST /api/v1/calendar/api/plants/` - Save plant to garden
- `GET /api/v1/calendar/api/care-tasks/` - List care tasks

❌ Need to Implement:
- `POST /api/v1/auth/firebase-token-exchange/` - JWT token exchange
- `GET /api/v1/users/profile/` - User profile
- `PATCH /api/v1/users/profile/` - Update profile

---

## Testing Strategy

### Unit Tests
- Test each service method independently
- Mock API responses
- Test error scenarios

### Widget Tests
- Test screen layouts
- Test navigation
- Test user interactions

### Integration Tests
```dart
testWidgets('Complete plant identification flow', (tester) async {
  // 1. Launch app
  await tester.pumpWidget(const MyApp());

  // 2. Navigate to camera
  await tester.tap(find.text('Identify Plant'));
  await tester.pumpAndSettle();

  // 3. Take photo (mock image picker)
  // ...

  // 4. Wait for results
  await tester.pumpAndSettle(const Duration(seconds: 3));

  // 5. Verify plant details displayed
  expect(find.text('Plant Name'), findsOneWidget);

  // 6. Save to garden
  await tester.tap(find.text('Save to Garden'));
  await tester.pumpAndSettle();

  // 7. Verify success
  expect(find.text('Saved successfully'), findsOneWidget);
});
```

---

## Timeline & Milestones

### Week 1: Core Services (32-40 hours)
- ✅ Task 1: API Service Layer (4h)
- ✅ Task 2: Firebase Auth + JWT (6h)
- ✅ Task 3: PlantIdentificationService (4h)
- ✅ Task 4: Firebase Storage (3h)
- ✅ Task 5: Firestore Offline Sync (4h)
- ✅ Task 8: Error Handling (3h)
- ✅ Task 9: Loading States (3h)

**Milestone**: Backend integration complete, plant ID working

### Week 2: Features & Integration (28-36 hours)
- ✅ Task 6: User Profile (4h)
- ✅ Task 7: Garden Tracking (6h)
- ✅ Task 10: Integration Tests (6h)
- ✅ Task 11: Replace Mock Service (2h)

**Milestone**: All features implemented, tests passing

### Week 3: Testing & Polish (24-32 hours)
- ✅ Task 12: End-to-End Testing (6h)
- ✅ Bug fixes from testing (10h)
- ✅ UI polish & animations (4h)
- ✅ Performance optimization (4h)

**Milestone**: Production-ready app, Grade A

---

## Deployment Checklist

### Before Release

- [ ] All 149 Django backend tests passing
- [ ] All Flutter widget tests passing
- [ ] Integration tests passing
- [ ] Firebase security rules deployed
- [ ] Environment variables configured (.env)
- [ ] iOS app built and tested on physical device
- [ ] Android app built and tested on physical device
- [ ] Performance profiling done (no memory leaks)
- [ ] Offline mode tested thoroughly
- [ ] Error handling tested (airplane mode, server down)
- [ ] App icons and splash screens configured
- [ ] Privacy policy and terms of service added
- [ ] App Store metadata prepared (screenshots, descriptions)

### Post-Release Monitoring

- [ ] Firebase Analytics configured
- [ ] Crashlytics set up for crash reporting
- [ ] User feedback collection (in-app)
- [ ] A/B testing for key features (optional)

---

## Success Criteria

### Grade A Production-Ready Criteria

1. **Functionality** ✅
   - All core features working (camera, identify, save, view)
   - Offline mode functional
   - Sync working when back online

2. **Performance** ✅
   - App launch < 2 seconds
   - Plant identification < 5 seconds (with network)
   - No memory leaks
   - Smooth 60 FPS scrolling

3. **Security** ✅
   - Firebase Auth properly integrated
   - JWT tokens securely stored
   - API keys in .env (not committed)
   - Firestore security rules enforced

4. **Testing** ✅
   - Unit tests for all services
   - Widget tests for all screens
   - Integration tests for critical flows
   - Manual testing on iOS + Android

5. **User Experience** ✅
   - Intuitive navigation
   - Clear loading states
   - Helpful error messages
   - Beautiful UI with dark mode

---

## Next Steps

**Start with Task 1**: Create API Service Layer

This is the foundation for all backend communication. Once this is done, we can progressively add authentication, plant identification, and other features.

**Recommended Development Flow**:
1. API Service → Test with Django backend
2. Auth Service → Test login/logout
3. Plant ID Service → Test camera → identify flow
4. Storage Service → Test image uploads
5. Firestore Service → Test offline sync
6. Integration → Connect all pieces
7. Testing → Ensure quality
8. Polish → Final touches

**Ready to start?** Let me know and we'll begin with Task 1!
