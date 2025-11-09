import 'dart:io';
import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_spacing.dart';
import '../../models/plant.dart';

/// Results screen displaying plant identification
///
/// Ported from design_reference/src/components/PlantResults.tsx
///
/// Features:
/// - Plant image with "Identified" badge
/// - Plant name and scientific name
/// - Description
/// - Care instructions with icons
/// - Timestamp
class ResultsScreen extends StatelessWidget {
  final Plant plant;

  const ResultsScreen({
    super.key,
    required this.plant,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Plant Identified'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Plant Image with Badge
              _buildPlantImage(context),
              const SizedBox(height: AppSpacing.lg),

              // Plant Info Card
              _buildPlantInfo(context),
              const SizedBox(height: AppSpacing.lg),

              // Care Instructions Card
              _buildCareInstructions(context),
              const SizedBox(height: AppSpacing.lg),

              // Timestamp
              _buildTimestamp(context),
            ],
          ),
        ),
      ),
    );
  }

  /// Plant image with "Identified" badge
  Widget _buildPlantImage(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          // Image
          AspectRatio(
            aspectRatio: 1.0,
            child: plant.imageUrl != null
                ? _buildImage(plant.imageUrl!)
                : _buildImagePlaceholder(context),
          ),

          // "Identified" Badge
          Positioned(
            top: AppSpacing.md,
            right: AppSpacing.md,
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: AppColors.green600,
                borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle, size: 16, color: Colors.white),
                  SizedBox(width: 4),
                  Text(
                    'Identified',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Build image from URL or file path
  Widget _buildImage(String imagePath) {
    final bool isUrl = imagePath.startsWith('http');

    return isUrl
        ? CachedNetworkImage(
            imageUrl: imagePath,
            fit: BoxFit.cover,
            placeholder: (context, url) => Container(
              color: AppColors.green100,
              child: const Center(child: CircularProgressIndicator()),
            ),
            errorWidget: (context, url, error) => _buildImagePlaceholder(context),
          )
        : Image.file(
            File(imagePath),
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) => _buildImagePlaceholder(context),
          );
  }

  /// Placeholder for missing image
  Widget _buildImagePlaceholder(BuildContext context) {
    return Container(
      color: AppColors.lightCard,
      child: const Center(
        child: Icon(Icons.image_not_supported, size: 64),
      ),
    );
  }

  /// Plant information card
  Widget _buildPlantInfo(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Common Name
            Text(
              plant.name,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: AppSpacing.xs),

            // Scientific Name
            Text(
              plant.scientificName,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    fontStyle: FontStyle.italic,
                    color: Theme.of(context).textTheme.bodySmall?.color,
                  ),
            ),
            const SizedBox(height: AppSpacing.md),

            // Description
            Text(
              plant.description,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).textTheme.bodySmall?.color,
                    height: 1.5,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  /// Care instructions card
  Widget _buildCareInstructions(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                const Icon(Icons.water_drop, size: 20, color: AppColors.blue600),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'Care Instructions',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),

            // Care Items
            ...plant.care.asMap().entries.map((entry) {
              final index = entry.key;
              final instruction = entry.value;
              return Padding(
                padding: EdgeInsets.only(
                  bottom: index < plant.care.length - 1 ? AppSpacing.md : 0,
                ),
                child: _buildCareItem(context, instruction, index),
              );
            }),
          ],
        ),
      ),
    );
  }

  /// Individual care instruction item
  Widget _buildCareItem(BuildContext context, String instruction, int index) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Icons for different care aspects
    final IconData icon = switch (index % 4) {
      0 => Icons.water_drop,
      1 => Icons.wb_sunny,
      2 => Icons.air,
      3 => Icons.thermostat,
      _ => Icons.eco,
    };

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Icon Container
        Container(
          margin: const EdgeInsets.only(top: 2),
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isDark
                ? AppColors.green900.withValues(alpha: 0.3)
                : AppColors.green100,
          ),
          child: Icon(
            icon,
            size: 14,
            color: isDark ? AppColors.green400 : AppColors.green700,
          ),
        ),
        const SizedBox(width: AppSpacing.md),

        // Instruction Text
        Expanded(
          child: Text(
            instruction,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).textTheme.bodySmall?.color,
                  height: 1.5,
                ),
          ),
        ),
      ],
    );
  }

  /// Timestamp display
  Widget _buildTimestamp(BuildContext context) {
    final dateFormat = DateFormat('MMMM d, y');
    final timeFormat = DateFormat('h:mm a');

    return Text(
      'Identified on ${dateFormat.format(plant.timestamp)} at ${timeFormat.format(plant.timestamp)}',
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).textTheme.bodySmall?.color,
          ),
      textAlign: TextAlign.center,
    );
  }
}
