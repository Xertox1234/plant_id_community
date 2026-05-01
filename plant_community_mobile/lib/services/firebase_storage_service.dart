import 'dart:io';

import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as path;
import 'package:uuid/uuid.dart';

/// Provider for Firebase Storage uploads used by plant identification.
final firebaseStorageServiceProvider =
    NotifierProvider<FirebaseStorageService, void>(FirebaseStorageService.new);

/// Firebase Storage service for uploading user plant photos.
class FirebaseStorageService extends Notifier<void> {
  static const int maxImageBytes = 5 * 1024 * 1024;
  static const Map<String, String> _allowedImageTypes = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
  };

  final FirebaseStorage? _providedStorage;
  final Uuid _uuid;

  FirebaseStorageService({FirebaseStorage? storage, Uuid? uuid})
      : _providedStorage = storage,
        _uuid = uuid ?? const Uuid();

  FirebaseStorage get _storage => _providedStorage ?? FirebaseStorage.instance;

  @override
  void build() {
    // Stateless service; dependencies are initialized in the constructor.
  }

  /// Upload a plant image and return its download URL.
  Future<String> uploadPlantImage(
    String filePath, {
    Function(double progress)? onProgress,
  }) async {
    final file = File(filePath);

    if (!file.existsSync()) {
      throw FirebaseStorageServiceException('Image file does not exist: $filePath');
    }

    final extension = path.extension(filePath).toLowerCase();
    final contentType = _allowedImageTypes[extension];
    if (contentType == null) {
      throw FirebaseStorageServiceException(
        'Unsupported image type. Use JPG, PNG, WebP, or GIF images.',
      );
    }

    final imageSize = file.lengthSync();
    if (imageSize > maxImageBytes) {
      throw FirebaseStorageServiceException('Image must be 5 MB or smaller.');
    }
    if (!_hasValidImageSignature(file, extension)) {
      throw FirebaseStorageServiceException('Image content does not match the file type.');
    }

    final imageId = _uuid.v4();
    final storageRef = _storage.ref('plant_images/$imageId$extension');

    try {
      final uploadTask = storageRef.putFile(
        file,
        SettableMetadata(contentType: contentType),
      );

      if (onProgress != null) {
        uploadTask.snapshotEvents.listen((snapshot) {
          final totalBytes = snapshot.totalBytes;
          if (totalBytes > 0) {
            onProgress(snapshot.bytesTransferred / totalBytes);
          }
        });
      }

      final snapshot = await uploadTask;
      final downloadUrl = await snapshot.ref.getDownloadURL();

      if (kDebugMode) {
        debugPrint('[FIREBASE STORAGE] Uploaded plant image successfully');
      }

      return downloadUrl;
    } on FirebaseException catch (error) {
      throw FirebaseStorageServiceException(
        'Failed to upload plant image: ${error.message ?? error.code}',
      );
    } catch (error) {
      throw FirebaseStorageServiceException('Failed to upload plant image: $error');
    }
  }

  bool _hasValidImageSignature(File file, String extension) {
    final handle = file.openSync(mode: FileMode.read);
    final bytes = handle.readSync(12);
    handle.closeSync();

    if (bytes.length < 4) {
      return false;
    }

    switch (extension) {
      case '.jpg':
      case '.jpeg':
        return bytes[0] == 0xFF && bytes[1] == 0xD8 && bytes[2] == 0xFF;
      case '.png':
        return bytes[0] == 0x89 &&
            bytes[1] == 0x50 &&
            bytes[2] == 0x4E &&
            bytes[3] == 0x47;
      case '.gif':
        return bytes[0] == 0x47 &&
            bytes[1] == 0x49 &&
            bytes[2] == 0x46 &&
            bytes[3] == 0x38;
      case '.webp':
        return bytes.length >= 12 &&
            bytes[0] == 0x52 &&
            bytes[1] == 0x49 &&
            bytes[2] == 0x46 &&
            bytes[3] == 0x46 &&
            bytes[8] == 0x57 &&
            bytes[9] == 0x45 &&
            bytes[10] == 0x42 &&
            bytes[11] == 0x50;
      default:
        return false;
    }
  }

  /// Delete a plant image by download URL.
  Future<void> deletePlantImage(String imageUrl) async {
    try {
      await _storage.refFromURL(imageUrl).delete();
    } on FirebaseException catch (error) {
      if (error.code == 'object-not-found') {
        return;
      }
      throw FirebaseStorageServiceException(
        'Failed to delete plant image: ${error.message ?? error.code}',
      );
    } catch (error) {
      throw FirebaseStorageServiceException('Failed to delete plant image: $error');
    }
  }
}

/// Error raised by Firebase Storage operations.
class FirebaseStorageServiceException implements Exception {
  final String message;

  FirebaseStorageServiceException(this.message);

  @override
  String toString() => 'FirebaseStorageServiceException: $message';
}