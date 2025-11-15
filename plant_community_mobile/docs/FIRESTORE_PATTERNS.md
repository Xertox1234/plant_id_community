# Firestore Offline Sync Patterns

**Date**: November 15, 2025
**Task**: Task 6 - Firestore Offline Sync
**Version**: 1.0.0
**Status**: Production-Ready

---

## Overview

This document codifies patterns for implementing Firestore offline synchronization in the Plant Community Mobile app. These patterns enable seamless offline-first functionality with automatic cloud sync when online.

---

## Pattern 1: Offline-First Service Architecture

### Context

Mobile apps must work without internet connection. Users should be able to save plants offline and have data sync automatically when online.

### Implementation

```dart
@riverpod
class FirestoreService extends _$FirestoreService {
  FirebaseFirestore get _firestore => FirebaseFirestore.instance;

  @override
  void build() {
    // Enable offline persistence (cached data available when offline)
    _firestore.settings = const Settings(
      persistenceEnabled: true,
      cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED,
    );

    if (kDebugMode) {
      debugPrint('[FIRESTORE] Service initialized with offline persistence');
    }
  }
}
```

### Key Points

**DO**:
- ✅ Enable `persistenceEnabled: true` for offline support
- ✅ Use `CACHE_SIZE_UNLIMITED` for mobile apps (no storage constraints)
- ✅ Initialize settings in service build() method
- ✅ Log initialization for debugging

**DON'T**:
- ❌ Disable offline persistence (breaks offline functionality)
- ❌ Set cache size too small (<40MB) - causes data eviction
- ❌ Re-initialize settings multiple times
- ❌ Assume network is always available

### Benefits

- Works offline out of the box
- Automatic sync when online
- Instant reads from local cache
- No manual cache management needed

---

## Pattern 2: User-Scoped Data Isolation

### Context

Each user's data must be isolated to prevent unauthorized access. Security rules enforce this server-side, but client code should follow the same structure.

### Implementation

```dart
// Collection structure: /users/{userId}/identified_plants/{plantId}
Future<void> savePlant(String userId, Plant plant) async {
  await _firestore
      .collection('users')
      .doc(userId)  // User-scoped parent document
      .collection('identified_plants')
      .doc(plant.id)
      .set(plant.toJson());
}

Stream<List<Plant>> getPlantsStream(String userId) {
  return _firestore
      .collection('users')
      .doc(userId)  // User-scoped parent document
      .collection('identified_plants')
      .orderBy('timestamp', descending: true)
      .snapshots()
      .map((snapshot) => /* parse plants */);
}
```

### Security Rules

```javascript
// Enforce user isolation server-side
match /users/{userId}/{document=**} {
  allow read, write: if request.auth != null && request.auth.uid == userId;
}
```

### Key Points

**DO**:
- ✅ Always use `/users/{userId}/...` structure
- ✅ Get userId from Firebase Auth (`FirebaseAuth.instance.currentUser?.uid`)
- ✅ Enforce same rules in client and security rules
- ✅ Test with multiple users to verify isolation

**DON'T**:
- ❌ Use global collections for user data
- ❌ Hardcode user IDs
- ❌ Trust client-side auth checks only
- ❌ Share data between users without explicit permissions

### Benefits

- Server-side security enforcement
- Clear data ownership
- Easy access control
- GDPR compliance (user data deletion)

---

## Pattern 3: Real-Time Streams with Error Handling

### Context

Firestore streams can fail due to network issues, permission errors, or invalid data. Graceful error handling prevents app crashes.

### Implementation

```dart
Stream<List<Plant>> getPlantsStream(String userId) {
  return _firestore
      .collection('users')
      .doc(userId)
      .collection('identified_plants')
      .orderBy('timestamp', descending: true)
      .snapshots()
      .map((snapshot) {
        if (kDebugMode) {
          debugPrint(
            '[FIRESTORE] Received ${snapshot.docs.length} plants '
            '(from ${snapshot.metadata.isFromCache ? "cache" : "server"})',
          );
        }

        return snapshot.docs.map((doc) {
          try {
            return Plant.fromJson(doc.data());
          } catch (e) {
            if (kDebugMode) {
              debugPrint('[FIRESTORE ERROR] Failed to parse plant: $e');
            }
            // Skip malformed documents instead of crashing
            return null;
          }
        }).whereType<Plant>().toList(); // Filter out nulls
      }).handleError((error) {
        if (kDebugMode) {
          debugPrint('[FIRESTORE ERROR] Stream error: $error');
        }
        // Return empty list on error instead of throwing
        return <Plant>[];
      });
}
```

### Riverpod Integration

```dart
@riverpod
Stream<List<Plant>> plantsStream(PlantsStreamRef ref, String userId) {
  final firestoreService = ref.watch(firestoreServiceProvider.notifier);
  return firestoreService.getPlantsStream(userId);
}

// Usage in widget
ref.watch(plantsStreamProvider(userId)).when(
  data: (plants) => PlantsList(plants: plants),
  loading: () => LoadingIndicator(),
  error: (error, stack) => ErrorWidget.withDetails(
    message: 'Failed to load plants',
    error: error,
  ),
);
```

### Key Points

**DO**:
- ✅ Handle parsing errors for each document
- ✅ Use `.handleError()` to catch stream errors
- ✅ Log errors for debugging
- ✅ Return safe defaults (empty list) on error
- ✅ Use Riverpod's `.when()` for loading/error states

**DON'T**:
- ❌ Let stream errors crash the app
- ❌ Assume all documents are valid
- ❌ Ignore malformed data
- ❌ Show technical error messages to users

### Benefits

- App never crashes from Firestore errors
- Malformed documents don't break UI
- Clear debugging logs
- User-friendly error handling

---

## Pattern 4: Cache-Aware Debug Logging

### Context

Understanding whether data comes from cache or server is critical for debugging offline functionality.

### Implementation

```dart
Stream<List<Plant>> getPlantsStream(String userId) {
  return _firestore
      .collection('users')
      .doc(userId)
      .collection('identified_plants')
      .snapshots()
      .map((snapshot) {
        // Log cache vs server source
        if (kDebugMode) {
          debugPrint(
            '[FIRESTORE] Received ${snapshot.docs.length} plants '
            '(from ${snapshot.metadata.isFromCache ? "cache" : "server"})',
          );
        }

        return /* parse plants */;
      });
}

Future<Plant?> getPlant(String userId, String plantId) async {
  final doc = await _firestore
      .collection('users')
      .doc(userId)
      .collection('identified_plants')
      .doc(plantId)
      .get();

  if (kDebugMode) {
    debugPrint(
      '[FIRESTORE] Plant fetched from '
      '${doc.metadata.isFromCache ? "cache" : "server"}',
    );
  }

  return doc.exists ? Plant.fromJson(doc.data()!) : null;
}
```

### Key Points

**DO**:
- ✅ Check `snapshot.metadata.isFromCache` to identify source
- ✅ Log cache hits for performance debugging
- ✅ Use `kDebugMode` to disable logs in production
- ✅ Include operation type in log prefix (`[FIRESTORE]`)

**DON'T**:
- ❌ Leave debug logs enabled in production
- ❌ Log sensitive user data
- ❌ Spam logs with every document
- ❌ Use print() instead of debugPrint()

### Benefits

- Easy offline testing verification
- Performance debugging (cache hit rate)
- Clear understanding of data flow
- No performance impact in production

---

## Pattern 5: Type-Safe JSON Serialization

### Context

Firestore stores documents as JSON. Type-safe serialization prevents runtime errors from malformed data.

### Implementation

```dart
class Plant {
  final String id;
  final String name;
  final String scientificName;
  final String description;
  final List<String> care;
  final String? imageUrl;
  final DateTime timestamp;

  const Plant({ /* required fields */ });

  /// Convert Plant to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'scientificName': scientificName,
      'description': description,
      'care': care,  // List<String> serialized as JSON array
      'imageUrl': imageUrl,  // Null-safe
      'timestamp': timestamp.toIso8601String(),  // DateTime as ISO 8601 string
    };
  }

  /// Create Plant from JSON (Firestore document)
  factory Plant.fromJson(Map<String, dynamic> json) {
    return Plant(
      id: json['id'] as String,
      name: json['name'] as String,
      scientificName: json['scientificName'] as String,
      description: json['description'] as String,
      care: (json['care'] as List<dynamic>).cast<String>(),  // Handle List<dynamic>
      imageUrl: json['imageUrl'] as String?,  // Null-safe
      timestamp: DateTime.parse(json['timestamp'] as String),  // Parse ISO 8601
    );
  }
}
```

### Firestore Document Structure

```json
{
  "id": "plant-123",
  "name": "Rose",
  "scientificName": "Rosa",
  "description": "Beautiful flowering plant",
  "care": [
    "Water daily",
    "Full sun",
    "Fertilize monthly"
  ],
  "imageUrl": "https://storage.googleapis.com/...",
  "timestamp": "2025-11-15T10:00:00.000Z"
}
```

### Key Points

**DO**:
- ✅ Use explicit type casts (`as String`, `as List<dynamic>`)
- ✅ Handle null values with `?` operator
- ✅ Store timestamps as ISO 8601 strings
- ✅ Convert List<dynamic> to typed lists with `.cast<T>()`
- ✅ Validate all required fields are present

**DON'T**:
- ❌ Use dynamic types without validation
- ❌ Store DateTime as milliseconds (harder to query)
- ❌ Assume lists are already typed
- ❌ Skip null checks for optional fields

### Benefits

- Type safety at compile time
- Clear error messages on invalid data
- Consistent data format
- Easy debugging of malformed documents

---

## Pattern 6: Optimistic UI Updates

### Context

Firestore writes are queued offline and synced when online. UI should reflect changes immediately without waiting for server confirmation.

### Implementation

```dart
// Service layer - returns immediately
Future<void> savePlant(String userId, Plant plant) async {
  // This completes immediately even offline
  // Firestore queues write for later sync
  await _firestore
      .collection('users')
      .doc(userId)
      .collection('identified_plants')
      .doc(plant.id)
      .set(plant.toJson());

  // UI gets updated via stream (from local cache)
}

// UI layer - immediate feedback
Future<void> _savePlant(WidgetRef ref, Plant plant) async {
  final userId = ref.read(authServiceProvider).firebaseUser?.uid;
  if (userId == null) return;

  final firestoreService = ref.read(firestoreServiceProvider.notifier);

  try {
    // This completes immediately
    await firestoreService.savePlant(userId, plant);

    // Show success message (even if offline)
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Plant saved!')),
    );
  } catch (e) {
    // Handle error
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Failed to save: $e')),
    );
  }
}
```

### Stream Behavior

```dart
// Stream reflects local cache immediately
ref.watch(plantsStreamProvider(userId)).when(
  data: (plants) {
    // This list includes:
    // 1. Previously synced plants (from cache)
    // 2. Newly saved plants (pending sync)
    // 3. Real-time updates from server (when online)

    return PlantsList(plants: plants);
  },
  // ...
);
```

### Key Points

**DO**:
- ✅ Show success feedback immediately
- ✅ Trust Firestore's offline queue
- ✅ Use streams for real-time updates
- ✅ Handle errors gracefully

**DON'T**:
- ❌ Wait for server confirmation to update UI
- ❌ Show loading spinner for writes (instant on cache)
- ❌ Manually track pending writes
- ❌ Duplicate optimistic update logic

### Benefits

- Instant UI feedback
- Works perfectly offline
- No manual cache management
- Automatic conflict resolution

---

## Pattern 7: Batch Operations for Bulk Changes

### Context

Deleting multiple documents or updating many records should use Firestore batch operations for atomicity and performance.

### Implementation

```dart
/// Clear all plants for a user (useful for testing or account deletion)
Future<void> clearAllPlants(String userId) async {
  try {
    final batch = _firestore.batch();

    // Get all plants
    final snapshot = await _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .get();

    // Add all deletions to batch
    for (final doc in snapshot.docs) {
      batch.delete(doc.reference);
    }

    // Execute all deletions atomically
    await batch.commit();

    if (kDebugMode) {
      debugPrint('[FIRESTORE] Deleted ${snapshot.docs.length} plants');
    }
  } catch (e) {
    throw FirestoreException('Failed to clear plants: $e');
  }
}
```

### Key Points

**DO**:
- ✅ Use batches for multiple related operations
- ✅ Batch up to 500 operations (Firestore limit)
- ✅ Commit batch to execute atomically
- ✅ Log operation count for debugging

**DON'T**:
- ❌ Use batches for single operations (overhead)
- ❌ Exceed 500 operations per batch
- ❌ Mix batch and non-batch operations
- ❌ Forget to call `.commit()`

### Batch Limits

- **Max operations per batch**: 500
- **Max batch size**: 10 MB
- **Atomicity**: All operations succeed or all fail

### Benefits

- Atomic operations (all or nothing)
- Better performance for bulk changes
- Reduced network round-trips
- Cleaner error handling

---

## Pattern 8: Custom Exceptions for Domain Errors

### Context

Generic Firebase exceptions don't provide app-specific context. Custom exceptions improve error handling and user feedback.

### Implementation

```dart
/// Custom exception for Firestore errors
class FirestoreException implements Exception {
  final String message;

  FirestoreException(this.message);

  @override
  String toString() => 'FirestoreException: $message';
}

// Usage in service
Future<void> savePlant(String userId, Plant plant) async {
  try {
    await _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .doc(plant.id)
        .set(plant.toJson());
  } on FirebaseException catch (e) {
    if (kDebugMode) {
      debugPrint('[FIRESTORE ERROR] Failed to save plant: ${e.message}');
    }
    // Wrap in custom exception with context
    throw FirestoreException('Failed to save plant: ${e.message ?? e.code}');
  } catch (e) {
    throw FirestoreException('Failed to save plant: $e');
  }
}
```

### UI Error Handling

```dart
try {
  await firestoreService.savePlant(userId, plant);
} on FirestoreException catch (e) {
  // Handle app-specific Firestore errors
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(e.message)),
  );
} catch (e) {
  // Handle unexpected errors
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(content: Text('An unexpected error occurred')),
  );
}
```

### Key Points

**DO**:
- ✅ Create domain-specific exception classes
- ✅ Include operation context in message
- ✅ Preserve original error details for debugging
- ✅ Use custom exceptions in catch blocks

**DON'T**:
- ❌ Let generic Firebase exceptions reach UI
- ❌ Lose original error information
- ❌ Show technical error codes to users
- ❌ Re-throw without adding context

### Benefits

- Clear error messages
- Domain-specific error handling
- Better user feedback
- Easier debugging

---

## Pattern 9: Provider-Based Stream Management

### Context

Riverpod providers handle stream lifecycle, preventing memory leaks and simplifying UI code.

### Implementation

```dart
// Service layer - return raw stream
class FirestoreService {
  Stream<List<Plant>> getPlantsStream(String userId) {
    return _firestore
        .collection('users')
        .doc(userId)
        .collection('identified_plants')
        .snapshots()
        .map((snapshot) => /* parse plants */);
  }
}

// Provider layer - expose stream to UI
@riverpod
Stream<List<Plant>> plantsStream(PlantsStreamRef ref, String userId) {
  final firestoreService = ref.watch(firestoreServiceProvider.notifier);
  return firestoreService.getPlantsStream(userId);
}

// UI layer - consume stream with automatic cleanup
class PlantsList extends ConsumerWidget {
  const PlantsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(authServiceProvider).firebaseUser?.uid;

    if (userId == null) {
      return const Text('Not signed in');
    }

    // Stream automatically disposed when widget unmounts
    final plantsAsync = ref.watch(plantsStreamProvider(userId));

    return plantsAsync.when(
      data: (plants) => ListView.builder(
        itemCount: plants.length,
        itemBuilder: (context, index) => PlantCard(plant: plants[index]),
      ),
      loading: () => const CircularProgressIndicator(),
      error: (error, stack) => Text('Error: $error'),
    );
  }
}
```

### Key Points

**DO**:
- ✅ Use Riverpod providers for stream lifecycle
- ✅ Pass userId as provider parameter
- ✅ Use `.when()` for loading/error states
- ✅ Let Riverpod handle disposal

**DON'T**:
- ❌ Manually manage stream subscriptions
- ❌ Create StreamControllers in services
- ❌ Forget to cancel subscriptions (memory leak)
- ❌ Use StatefulWidget for streams

### Benefits

- Automatic stream disposal
- No memory leaks
- Declarative UI
- Less boilerplate code

---

## Pattern 10: Testing with Firebase Emulator

### Context

Integration tests should use Firebase Emulator Suite, not production Firestore. This enables fast, isolated testing.

### Setup

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Initialize emulators
firebase init emulators

# Start Firestore emulator
firebase emulators:start --only firestore
```

### Test Configuration

```dart
import 'package:cloud_firestore/cloud_firestore.dart';

void main() {
  setUpAll(() async {
    // Connect to emulator
    FirebaseFirestore.instance.useFirestoreEmulator('localhost', 8080);
  });

  tearDown(() async {
    // Clear data after each test
    final firestore = FirebaseFirestore.instance;
    final snapshot = await firestore.collection('users').get();

    for (final doc in snapshot.docs) {
      await doc.reference.delete();
    }
  });

  testWidgets('FirestoreService saves and retrieves plant', (tester) async {
    final container = ProviderContainer();
    final firestoreService = container.read(firestoreServiceProvider.notifier);
    final testUserId = 'test-user-123';

    final plant = Plant(
      id: 'plant-123',
      name: 'Rose',
      scientificName: 'Rosa',
      description: 'Beautiful flower',
      care: ['Water daily'],
      timestamp: DateTime.now(),
    );

    // Act
    await firestoreService.savePlant(testUserId, plant);
    final retrievedPlant = await firestoreService.getPlant(testUserId, 'plant-123');

    // Assert
    expect(retrievedPlant, isNotNull);
    expect(retrievedPlant!.id, equals('plant-123'));
    expect(retrievedPlant.name, equals('Rose'));
  });
}
```

### Key Points

**DO**:
- ✅ Use emulator for all integration tests
- ✅ Clear data between tests (isolation)
- ✅ Test offline scenarios (disconnect emulator)
- ✅ Verify security rules in emulator

**DON'T**:
- ❌ Test against production Firestore
- ❌ Skip emulator setup (costs money, slow)
- ❌ Share test data between tests
- ❌ Hardcode emulator URLs in production

### Benefits

- Fast test execution
- Free (no Firestore costs)
- Isolated test environment
- Offline testing support

---

## Common Pitfalls

### ❌ Pitfall 1: Forgetting to Enable Offline Persistence

```dart
// ❌ WRONG - No offline support
FirebaseFirestore.instance; // Uses default settings

// ✅ CORRECT - Enable offline persistence
FirebaseFirestore.instance.settings = const Settings(
  persistenceEnabled: true,
  cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED,
);
```

### ❌ Pitfall 2: Not Handling Stream Errors

```dart
// ❌ WRONG - Stream crashes app on error
Stream<List<Plant>> getPlantsStream(String userId) {
  return _firestore.collection('users').doc(userId)
      .collection('identified_plants')
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) =>
          Plant.fromJson(doc.data()) // Crashes on malformed data!
      ).toList());
}

// ✅ CORRECT - Graceful error handling
Stream<List<Plant>> getPlantsStream(String userId) {
  return _firestore.collection('users').doc(userId)
      .collection('identified_plants')
      .snapshots()
      .map((snapshot) => snapshot.docs.map((doc) {
        try {
          return Plant.fromJson(doc.data());
        } catch (e) {
          return null; // Skip malformed documents
        }
      }).whereType<Plant>().toList())
      .handleError((error) => <Plant>[]); // Return empty list on stream error
}
```

### ❌ Pitfall 3: Using Global Collections

```dart
// ❌ WRONG - Global collection, no user isolation
await _firestore.collection('identified_plants')
    .doc(plant.id)
    .set(plant.toJson()); // Any user can access any plant!

// ✅ CORRECT - User-scoped collection
await _firestore.collection('users')
    .doc(userId)
    .collection('identified_plants')
    .doc(plant.id)
    .set(plant.toJson()); // Each user's data is isolated
```

### ❌ Pitfall 4: Ignoring Cache Metadata

```dart
// ❌ WRONG - No visibility into cache behavior
final snapshot = await _firestore.collection('users')
    .doc(userId)
    .collection('identified_plants')
    .get();
// Is this from cache or server? No idea!

// ✅ CORRECT - Log cache metadata
final snapshot = await _firestore.collection('users')
    .doc(userId)
    .collection('identified_plants')
    .get();

if (kDebugMode) {
  debugPrint('[FIRESTORE] Data from ${snapshot.metadata.isFromCache ? "cache" : "server"}');
}
```

---

## Production Checklist

Before deploying Firestore to production:

### Security

- [ ] Security rules deployed to Firebase Console
- [ ] Tested authenticated user can read own data
- [ ] Tested authenticated user CANNOT read other users' data
- [ ] Tested unauthenticated user CANNOT access data
- [ ] Data validation rules enforce schema

### Functionality

- [ ] Offline persistence enabled
- [ ] Stream error handling implemented
- [ ] Custom exceptions used
- [ ] Debug logging wrapped in `kDebugMode`
- [ ] Riverpod providers manage stream lifecycle

### Testing

- [ ] Unit tests pass for JSON serialization
- [ ] Integration tests pass with Firebase Emulator
- [ ] Tested offline write → sync when online
- [ ] Tested offline read from cache
- [ ] Tested real-time updates

### Monitoring

- [ ] Firebase Console monitoring set up
- [ ] Firestore usage metrics tracked
- [ ] Error reporting configured
- [ ] Performance monitoring enabled

---

## References

- **Firestore Documentation**: https://firebase.google.com/docs/firestore
- **Offline Persistence**: https://firebase.google.com/docs/firestore/manage-data/enable-offline
- **Security Rules**: https://firebase.google.com/docs/firestore/security/get-started
- **Riverpod**: https://riverpod.dev/docs/introduction/getting_started

---

## Version History

- **v1.0.0** (Nov 15, 2025): Initial Firestore patterns documentation
  - 10 comprehensive patterns
  - Common pitfalls section
  - Production checklist
  - Testing guidance with emulator
