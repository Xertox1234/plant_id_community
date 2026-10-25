import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../models/plant.dart';
import 'api_service.dart';
import 'firebase_storage_service.dart';

/// Injectable UUID generator. Override in tests for deterministic IDs.
final uuidProvider = Provider<Uuid>((ref) => const Uuid());

/// Provider for plant identification orchestration.
final plantIdentificationServiceProvider =
    NotifierProvider<PlantIdentificationService, void>(
      PlantIdentificationService.new,
    );

/// Coordinates image upload and backend plant identification.
class PlantIdentificationService extends Notifier<void> {
  @override
  void build() {
    // Stateless orchestration service.
  }

  /// Upload [imagePath], identify the plant via the backend, and return a model.
  Future<Plant> identifyPlant(
    String imagePath, {
    Function(double progress)? onUploadProgress,
  }) async {
    String? imageUrl;

    try {
      final storageService = ref.read(firebaseStorageServiceProvider.notifier);
      final apiService = ref.read(apiServiceProvider);

      imageUrl = await storageService.uploadPlantImage(
        imagePath,
        onProgress: onUploadProgress,
      );

      final response = await apiService.uploadFile(
        '/plant-identification/identify/',
        filePath: imagePath,
        fieldName: 'image',
        data: {'image_url': imageUrl},
        // Identification runs synchronously on the server (todo 461).
        receiveTimeout: slowAnalysisReceiveTimeout,
      );

      final responseData = response.data;
      if (responseData is! Map<String, dynamic>) {
        throw PlantIdentificationException(
          'Plant identification returned an invalid response.',
        );
      }

      // The backend answers a refusal (e.g. no provider result) with a 200
      // and `success: false`, so the status code alone is not an answer.
      if (responseData['success'] == false) {
        throw PlantIdentificationException(
          _stringValue(responseData, ['error']) ??
              'No plant could be identified from this image.',
        );
      }

      final name = _stringValue(responseData, ['plant_name']);
      final scientificName = _stringValue(responseData, [
        'scientific_name',
        'scientificName',
      ]);

      if (name == null ||
          name.isEmpty ||
          scientificName == null ||
          scientificName.isEmpty) {
        throw PlantIdentificationException(
          'No plant could be identified from this image.',
        );
      }

      return Plant(
        id: _stringValue(responseData, ['id']) ?? ref.read(uuidProvider).v4(),
        name: name,
        scientificName: scientificName,
        description:
            _topSuggestionDescription(responseData) ??
            'No description available.',
        care: _careInstructions(responseData),
        imageUrl: imageUrl,
        timestamp: DateTime.now(),
      );
    } on PlantIdentificationException {
      await _cleanupUploadedImage(imageUrl);
      rethrow;
    } on ApiException {
      await _cleanupUploadedImage(imageUrl);
      rethrow;
    } catch (error) {
      await _cleanupUploadedImage(imageUrl);
      if (kDebugMode) {
        debugPrint('[PLANT IDENTIFICATION] Failed: $error');
      }
      throw PlantIdentificationException('Failed to identify plant: $error');
    }
  }

  Future<void> _cleanupUploadedImage(String? imageUrl) async {
    if (imageUrl == null) {
      return;
    }

    try {
      await ref
          .read(firebaseStorageServiceProvider.notifier)
          .deletePlantImage(imageUrl);
    } catch (cleanupError) {
      if (kDebugMode) {
        debugPrint('[PLANT IDENTIFICATION] Failed to clean up uploaded image');
      }
    }
  }

  static String? _stringValue(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      if (value is String && value.trim().isNotEmpty) {
        return value.trim();
      }
    }
    return null;
  }

  /// The backend carries the description on each suggestion, not at the top.
  static String? _topSuggestionDescription(Map<String, dynamic> data) {
    final suggestions = data['suggestions'];
    if (suggestions is List && suggestions.isNotEmpty) {
      final top = suggestions.first;
      if (top is Map<String, dynamic>) {
        return _stringValue(top, ['description']);
      }
    }
    return null;
  }

  static List<String> _careInstructions(Map<String, dynamic> data) {
    final value = data['care_instructions'] ?? data['care'];
    // The backend sends a map of topic -> advice ({"watering": "...", ...}).
    if (value is Map) {
      final care = <String>[
        for (final entry in value.entries)
          if (entry.value is String &&
              (entry.value as String).trim().isNotEmpty)
            '${_careLabel(entry.key.toString())}: ${(entry.value as String).trim()}',
      ];
      if (care.isNotEmpty) return care;
    }
    if (value is List) {
      return value
          .whereType<String>()
          .where((item) => item.trim().isNotEmpty)
          .toList();
    }
    if (value is String && value.trim().isNotEmpty) {
      return [value.trim()];
    }
    return const ['Follow general care guidelines for this plant species.'];
  }
}

/// `common_issues` -> `Common issues`.
String _careLabel(String key) {
  final words = key.replaceAll('_', ' ').trim();
  return words.isEmpty ? key : words[0].toUpperCase() + words.substring(1);
}

/// Error raised when identification cannot produce a valid plant result.
class PlantIdentificationException implements Exception {
  final String message;

  PlantIdentificationException(this.message);

  @override
  String toString() => 'PlantIdentificationException: $message';
}
