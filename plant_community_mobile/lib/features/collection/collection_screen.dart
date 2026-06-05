import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

/// Identified-plant collection hub (stub). Shows a 2-column grid of sample
/// plants plus an "add" tile; sync & history are not yet implemented.
class CollectionScreen extends StatelessWidget {
  const CollectionScreen({super.key});

  static const _plants = [
    _PlantEntry(commonName: 'Monstera', scientificName: 'Monstera deliciosa'),
    _PlantEntry(
      commonName: 'Golden Barrel',
      scientificName: 'Echinocactus grusonii',
    ),
    _PlantEntry(
      commonName: 'Peace Lily',
      scientificName: 'Spathiphyllum wallisii',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    final eyebrowStyle = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);

    return Scaffold(
      appBar: AppBar(title: const Text('My Collection'), centerTitle: true),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: EdgeInsets.all(ext.padScreen),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Text(
                    '${_plants.length} PLANTS IDENTIFIED',
                    style: eyebrowStyle,
                  ),
                  SizedBox(height: ext.gapY),
                ]),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: ext.padScreen),
              sliver: SliverGrid(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisSpacing: ext.gapY,
                  crossAxisSpacing: ext.gapY,
                  childAspectRatio: 0.8,
                ),
                delegate: SliverChildListDelegate([
                  ..._plants.map((p) => _PlantCard(plant: p, ext: ext)),
                  _AddCard(ext: ext),
                ]),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.all(ext.padScreen),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Text(
                    'Sync & history coming soon',
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: ext.ink3),
                    textAlign: TextAlign.center,
                  ),
                  SizedBox(height: ext.gapY),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlantEntry {
  const _PlantEntry({required this.commonName, required this.scientificName});
  final String commonName;
  final String scientificName;
}

class _PlantCard extends StatelessWidget {
  const _PlantCard({required this.plant, required this.ext});
  final _PlantEntry plant;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 100,
            color: cs.surfaceContainerLow,
            width: double.infinity,
            child: Center(
              child: Icon(
                Icons.eco,
                size: 32,
                color: cs.primary.withValues(alpha: 0.4),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plant.commonName,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  plant.scientificName,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontFamily: 'GeistMono',
                    color: ext.ink2,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: ext.leaf,
                    borderRadius: BorderRadius.circular(AppSpacing.rXs),
                  ),
                  child: Text(
                    '✓ ID\'d',
                    style: TextStyle(
                      color: GreenThumbExtension.onLeaf,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AddCard extends StatelessWidget {
  const _AddCard({required this.ext});
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        border: Border.all(color: cs.outlineVariant, width: 2),
        color: cs.surfaceContainerLow,
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.add, color: ext.ink3, size: 28),
            const SizedBox(height: 4),
            Text(
              'Identify a plant',
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: ext.ink3),
            ),
          ],
        ),
      ),
    );
  }
}
