import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../models/plant.dart';

part 'firestore_service.g.dart';

/// Firestore service for offline data persistence and cross-device sync
///
/// This service provides:
/// - Offline data persistence (automatic with Firestore)
/// - Real-time synchronization across devices
/// - User-scoped data isolation
///
/// Collections structure:
/// ```
/// /users/{userId}/
///   ├─ identified_plants/
///   │   ├─ {plantId}/
///   │   │   ├─ id: string
///   │   │   ├─ name: string
///   │   │   ├─ scientificName: string
///   │   │   ├─ imageUrl: string
///   │   │   ├─ timestamp: timestamp
///   │   │   └─ care: array
/// ```
///
/// Usage:
/// ```dart
/// final firestoreService = ref.read(firestoreServiceProvider);
///
/// // Save plant (syncs automatically)
/// await firestoreService.savePlant('userId', plant);
///
/// // Stream plants (works offline with cached data)
/// ref.watch(plantsStreamProvider('userId')).when(
///   data: (plants) => PlantsList(plants: plants),
///   loading: () => LoadingIndicator(),
///   error: (error, stack) => ErrorWidget(error),
/// );
/// ```
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

  /// Validate userId is non-empty and safe for Firestore paths
  ///
  /// Throws [FirestoreException] if userId is invalid
  void _validateUserId(String userId) {
    if (userId.isEmpty) {
      throw FirestoreException('userId cannot be empty');
    }

    // Firestore document IDs have specific rules:
    // - Cannot contain forward slashes
    // - Cannot solely be "." or ".."
    // - Cannot exceed 1500 bytes
    if (userId.contains('/')) {
      throw FirestoreException(
        'Invalid userId: cannot contain forward slashes',
      );
    }

    if (userId == '.' || userId == '..') {
      throw FirestoreException(
        'Invalid userId: cannot be "." or ".."',
      );
    }

    if (userId.length > 1500) {
      throw FirestoreException(
        'Invalid userId: exceeds maximum length of 1500 characters',
      );
    }
  }

  /// Save identified plant to Firestore
  ///
  /// Data will be cached locally and synced when online
  ///
  /// Throws [FirestoreException] if save fails or userId is invalid
  Future<void> savePlant(String userId, Plant plant) async {
    _validateUserId(userId);

    try {
      if (kDebugMode) {
        debugPrint(
          '[FIRESTORE] Saving plant ${plant.name} for user $userId',
        );
      }

      await _firestore
          .collection('users')
          .doc(userId)
          .collection('identified_plants')
          .doc(plant.id)
          .set(plant.toJson());

      if (kDebugMode) {
        debugPrint('[FIRESTORE] Plant saved successfully (will sync when online)');
      }
    } on FirebaseException catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Failed to save plant: ${e.message}');
      }
      throw FirestoreException('Failed to save plant: ${e.message ?? e.code}');
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Unexpected error: $e');
      }
      throw FirestoreException('Failed to save plant: $e');
    }
  }

  /// Get real-time stream of identified plants
  ///
  /// Returns cached data when offline, syncs when online.
  /// Ordered by timestamp (most recent first).
  ///
  /// ⚠️ **IMPORTANT - StreamSubscription Cleanup**:
  /// When calling this method directly (not via `plantsStreamProvider`),
  /// you MUST cancel the StreamSubscription to prevent memory leaks:
  /// ```dart
  /// final subscription = firestoreService.getPlantsStream(userId).listen(...);
  /// // Later, when done:
  /// subscription.cancel();
  /// ```
  /// Prefer using `plantsStreamProvider` which handles cleanup automatically.
  ///
  /// ⚠️ **IMPORTANT - Firestore Index Required**:
  /// This query requires a Firestore composite index on the
  /// `identified_plants` collection with field `timestamp` (descending).
  ///
  /// On first run, if the index doesn't exist, you'll see an error like:
  /// ```
  /// [cloud_firestore/failed-precondition] The query requires an index.
  /// You can create it here: https://console.firebase.google.com/...
  /// ```
  /// Click the URL in the error message to auto-create the index in Firebase Console.
  ///
  /// Throws [FirestoreException] if userId is invalid
  Stream<List<Plant>> getPlantsStream(String userId) {
    _validateUserId(userId);

    if (kDebugMode) {
      debugPrint('[FIRESTORE] Creating plants stream for user $userId');
    }

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
          // Skip malformed documents
          return null;
        }
      }).whereType<Plant>().toList(); // Filter out nulls
    }).handleError((error) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Stream error: $error');
      }
      // Return empty list on error, don't crash the app
      return <Plant>[];
    });
  }

  /// Delete plant from Firestore
  ///
  /// Deletion will sync when online
  ///
  /// Throws [FirestoreException] if deletion fails or userId is invalid
  Future<void> deletePlant(String userId, String plantId) async {
    _validateUserId(userId);

    try {
      if (kDebugMode) {
        debugPrint('[FIRESTORE] Deleting plant $plantId for user $userId');
      }

      await _firestore
          .collection('users')
          .doc(userId)
          .collection('identified_plants')
          .doc(plantId)
          .delete();

      if (kDebugMode) {
        debugPrint('[FIRESTORE] Plant deleted successfully');
      }
    } on FirebaseException catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Failed to delete plant: ${e.message}');
      }
      throw FirestoreException('Failed to delete plant: ${e.message ?? e.code}');
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Unexpected error: $e');
      }
      throw FirestoreException('Failed to delete plant: $e');
    }
  }

  /// Get single plant by ID
  ///
  /// Returns cached data when offline
  ///
  /// Returns null if plant not found
  ///
  /// Throws [FirestoreException] if userId is invalid
  Future<Plant?> getPlant(String userId, String plantId) async {
    _validateUserId(userId);

    try {
      if (kDebugMode) {
        debugPrint('[FIRESTORE] Fetching plant $plantId for user $userId');
      }

      final doc = await _firestore
          .collection('users')
          .doc(userId)
          .collection('identified_plants')
          .doc(plantId)
          .get();

      if (!doc.exists) {
        if (kDebugMode) {
          debugPrint('[FIRESTORE] Plant not found');
        }
        return null;
      }

      final plant = Plant.fromJson(doc.data()!);

      if (kDebugMode) {
        debugPrint(
          '[FIRESTORE] Plant fetched from ${doc.metadata.isFromCache ? "cache" : "server"}',
        );
      }

      return plant;
    } on FirebaseException catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Failed to fetch plant: ${e.message}');
      }
      throw FirestoreException('Failed to fetch plant: ${e.message ?? e.code}');
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Unexpected error: $e');
      }
      throw FirestoreException('Failed to fetch plant: $e');
    }
  }

  /// Clear all plants for a user (useful for testing or account deletion)
  ///
  /// WARNING: This is irreversible!
  ///
  /// Throws [FirestoreException] if userId is invalid
  Future<void> clearAllPlants(String userId) async {
    _validateUserId(userId);

    try {
      if (kDebugMode) {
        debugPrint('[FIRESTORE] Clearing all plants for user $userId');
      }

      final batch = _firestore.batch();
      final snapshot = await _firestore
          .collection('users')
          .doc(userId)
          .collection('identified_plants')
          .get();

      for (final doc in snapshot.docs) {
        batch.delete(doc.reference);
      }

      await batch.commit();

      if (kDebugMode) {
        debugPrint('[FIRESTORE] Deleted ${snapshot.docs.length} plants');
      }
    } on FirebaseException catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Failed to clear plants: ${e.message}');
      }
      throw FirestoreException('Failed to clear plants: ${e.message ?? e.code}');
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[FIRESTORE ERROR] Unexpected error: $e');
      }
      throw FirestoreException('Failed to clear plants: $e');
    }
  }
}

/// Provider for plants stream by user ID
///
/// This provider automatically handles offline/online transitions
@riverpod
Stream<List<Plant>> plantsStream(Ref ref, String userId) {
  final firestoreService = ref.watch(firestoreServiceProvider.notifier);
  return firestoreService.getPlantsStream(userId);
}

/// Custom exception for Firestore errors
class FirestoreException implements Exception {
  final String message;

  FirestoreException(this.message);

  @override
  String toString() => 'FirestoreException: $message';
}
