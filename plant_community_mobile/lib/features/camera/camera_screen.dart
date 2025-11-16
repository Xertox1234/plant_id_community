import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../services/plant_identification_service.dart';
import '../../services/api_service.dart';
import '../../models/plant.dart';

/// Camera screen for plant identification
///
/// Ported from design_reference/src/components/PlantCamera.tsx
///
/// Features:
/// - Take photo with camera
/// - Upload from gallery
/// - Sample images for testing (optional)
/// - Real plant identification via Django backend
class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  final ImagePicker _picker = ImagePicker();
  String? _selectedImagePath;
  bool _isIdentifying = false;
  double _uploadProgress = 0.0;

  /// Handle photo from camera
  Future<void> _takePhoto() async {
    try {
      final XFile? photo = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1080,
        maxHeight: 1080,
        imageQuality: 85,
      );

      if (photo != null) {
        setState(() {
          _selectedImagePath = photo.path;
        });
      }
    } catch (e) {
      _showError('Failed to take photo: $e');
    }
  }

  /// Handle photo from gallery
  Future<void> _pickFromGallery() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 1080,
        maxHeight: 1080,
        imageQuality: 85,
      );

      if (image != null) {
        setState(() {
          _selectedImagePath = image.path;
        });
      }
    } catch (e) {
      _showError('Failed to pick image: $e');
    }
  }

  /// Handle sample image selection
  void _useSampleImage(String imageUrl) {
    setState(() {
      _selectedImagePath = imageUrl;
    });
  }

  /// Identify the plant using real backend API
  Future<void> _identifyPlant() async {
    if (_selectedImagePath == null) return;

    setState(() {
      _isIdentifying = true;
      _uploadProgress = 0.0;
    });

    try {
      // Call real plant identification service
      final plantIdService = ref.read(plantIdentificationServiceProvider.notifier);

      final Plant plant = await plantIdService.identifyPlant(
        _selectedImagePath!,
        onUploadProgress: (progress) {
          if (mounted) {
            setState(() {
              _uploadProgress = progress;
            });
          }
        },
      );

      if (!mounted) return;

      // Navigate to results screen with plant data (passed as extra)
      context.go(AppRoutes.results, extra: plant);
    } on ApiException catch (e) {
      // Handle API-specific errors (network, auth, etc.)
      if (!mounted) return;
      _showError('API Error: ${e.message}');
    } on PlantIdentificationException catch (e) {
      // Handle plant identification errors
      if (!mounted) return;
      _showError(e.message);
    } catch (e) {
      // Handle unexpected errors
      if (!mounted) return;
      _showError('Failed to identify plant. Please try again.');
    } finally {
      if (mounted) {
        setState(() {
          _isIdentifying = false;
          _uploadProgress = 0.0;
        });
      }
    }
  }

  /// Show error snackbar
  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.lightDestructive,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Identify Plant'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Image Display Card
              _buildImageCard(),
              const SizedBox(height: AppSpacing.xl),

              // Action Buttons
              _buildActionButtons(),
              const SizedBox(height: AppSpacing.xl),

              // Sample Images (optional, can be removed for production)
              // Uncomment to enable test images from MockPlantService
              // if (_selectedImagePath == null) _buildSampleImages(),
            ],
          ),
        ),
      ),
    );
  }

  /// Image display card
  Widget _buildImageCard() {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 1.0,
        child: _selectedImagePath != null
            ? _buildSelectedImage()
            : _buildPlaceholder(),
      ),
    );
  }

  /// Selected image display
  Widget _buildSelectedImage() {
    final bool isUrl = _selectedImagePath!.startsWith('http');

    return isUrl
        ? CachedNetworkImage(
            imageUrl: _selectedImagePath!,
            fit: BoxFit.cover,
            placeholder: (context, url) => const Center(
              child: CircularProgressIndicator(),
            ),
            errorWidget: (context, url, error) => const Center(
              child: Icon(Icons.error),
            ),
          )
        : Image.file(
            File(_selectedImagePath!),
            fit: BoxFit.cover,
          );
  }

  /// Placeholder when no image selected
  Widget _buildPlaceholder() {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? AppColors.darkCard
            : AppColors.lightCard,
        border: Border.all(
          color: Theme.of(context).dividerColor.withValues(alpha: 0.25),
          width: 2,
          strokeAlign: BorderSide.strokeAlignInside,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.camera_alt,
            size: 64,
            color: Theme.of(context).iconTheme.color?.withValues(alpha: 0.5),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            'Upload a photo to identify the plant',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Theme.of(context).textTheme.bodySmall?.color,
                ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  /// Action buttons (camera, gallery, identify)
  Widget _buildActionButtons() {
    return Column(
      children: [
        // Take Photo button
        ElevatedButton.icon(
          onPressed: _isIdentifying ? null : _takePhoto,
          icon: const Icon(Icons.camera_alt),
          label: const Text('Take Photo'),
          style: ElevatedButton.styleFrom(
            minimumSize: const Size.fromHeight(50),
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Upload from Gallery button
        OutlinedButton.icon(
          onPressed: _isIdentifying ? null : _pickFromGallery,
          icon: const Icon(Icons.upload),
          label: const Text('Upload from Gallery'),
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(50),
          ),
        ),

        // Identify button (shown only when image is selected)
        if (_selectedImagePath != null) ...[
          const SizedBox(height: AppSpacing.md),
          ElevatedButton.icon(
            onPressed: _isIdentifying ? null : _identifyPlant,
            icon: _isIdentifying
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : const Icon(Icons.search),
            label: Text(_isIdentifying ? 'Identifying...' : 'Identify Plant'),
            style: ElevatedButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              backgroundColor: AppColors.green600,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ],
    );
  }

  /// Sample images grid (commented out - can be re-enabled for testing)
  /*
  Widget _buildSampleImages() {
    return Column(
      children: [
        Text(
          'Or try a sample image',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).textTheme.bodySmall?.color,
              ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: AppSpacing.md),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 4,
            crossAxisSpacing: AppSpacing.sm,
            mainAxisSpacing: AppSpacing.sm,
          ),
          itemCount: sampleImages.length,
          itemBuilder: (context, index) {
            final imageUrl = sampleImages[index];
            return _buildSampleImageTile(imageUrl, index);
          },
        ),
      ],
    );
  }

  /// Individual sample image tile
  Widget _buildSampleImageTile(String imageUrl, int index) {
    return InkWell(
      onTap: () => _useSampleImage(imageUrl),
      borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMD),
          border: Border.all(
            color: Colors.transparent,
            width: 2,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: CachedNetworkImage(
          imageUrl: imageUrl,
          fit: BoxFit.cover,
          placeholder: (context, url) => Container(
            color: AppColors.green100,
            child: const Center(
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
          errorWidget: (context, url, error) => Container(
            color: AppColors.lightCard,
            child: const Icon(Icons.error, size: 24),
          ),
        ),
      ),
    );
  }

  /// Sample images (can be used for testing without real API)
  static const List<String> sampleImages = [
    'https://images.unsplash.com/photo-1717130082324-00781001faba?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzdWNjdWxlbnQlMjBwbGFudCUyMGNsb3NlfGVufDF8fHx8MTc2MTA1OTEwOHww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1680593384685-1d8c68f37872?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxmZXJuJTIwbGVhdmVzJTIwbmF0dXJlfGVufDF8fHx8MTc2MTA1OTEwOHww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1648528203163-8604bf696e7c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb25zdGVyYSUyMHBsYW50JTIwaW5kb29yfGVufDF8fHx8MTc2MTAxNjkzOXww&ixlib=rb-4.1.0&q=80&w=1080',
    'https://images.unsplash.com/photo-1631791222734-2f1cb65e2fa9?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxsYXZlbmRlciUyMGZsb3dlcnMlMjBmaWVsZHxlbnwxfHx8fDE3NjEwMjEzMTh8MA&ixlib=rb-4.1.0&q=80&w=1080',
  ];
  */
}
