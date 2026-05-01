import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../models/plant.dart';
import 'api_service.dart';
import 'firebase_storage_service.dart';

/// Provider for plant identification orchestration.
final plantIdentificationServiceProvider =
    NotifierProvider<PlantIdentificationService, void>(PlantIdentificationService.new);

/// Coordinates image upload and backend plant identification.
class PlantIdentificationService extends Notifier<void> {
  final Uuid _uuid;

  PlantIdentificationService({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

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
      );

      final responseData = response.data;
      if (responseData is! Map<String, dynamic>) {
        throw PlantIdentificationException('Plant identification returned an invalid response.');
      }

      final name = _stringValue(responseData, ['name', 'common_name']);
      final scientificName = _stringValue(responseData, ['scientific_name', 'scientificName']);

      if (name == null || name.isEmpty || scientificName == null || scientificName.isEmpty) {
        throw PlantIdentificationException('No plant could be identified from this image.');
      }

      return Plant(
        id: _stringValue(responseData, ['id']) ?? _uuid.v4(),
        name: name,
        scientificName: scientificName,
        description: _stringValue(responseData, ['description']) ?? 'No description available.',
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
      await ref.read(firebaseStorageServiceProvider.notifier).deletePlantImage(imageUrl);
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

  static List<String> _careInstructions(Map<String, dynamic> data) {
    final value = data['care_instructions'] ?? data['care'];
    if (value is List) {
      return value.whereType<String>().where((item) => item.trim().isNotEmpty).toList();
    }
    if (value is String && value.trim().isNotEmpty) {
      return [value.trim()];
    }
    return const ['Follow general care guidelines for this plant species.'];
  }
}

/// Error raised when identification cannot produce a valid plant result.
class PlantIdentificationException implements Exception {
  final String message;

  PlantIdentificationException(this.message);

  @override
  String toString() => 'PlantIdentificationException: $message';
}