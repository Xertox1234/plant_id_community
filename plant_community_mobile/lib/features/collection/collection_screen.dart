import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../models/plant.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';

/// Identified-plant collection hub.
///
/// Reads the user's plant collection from [plantsStreamProvider] — Firestore
/// with offline persistence — so the list is available offline, updates in real
/// time, and syncs across devices. Shows a sync/offline badge driven by the
/// snapshot metadata, and graceful signed-out / loading / error / empty states.
class CollectionScreen extends ConsumerWidget {
  const CollectionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final uid = ref.watch(currentUserIdProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('My Collection'), centerTitle: true),
      body: SafeArea(
        // `/collection` is not auth-guarded, so the uid can be null. Branch on
        // it rather than passing an empty string into the provider (which would
        // throw in FirestoreService._validateUserId).
        child: uid == null || uid.isEmpty
            ? _CenteredMessage(
                icon: Icons.person_outline,
                title: 'Sign in to see your collection',
                subtitle:
                    'Your identified plants sync across devices and stay '
                    'available offline once you sign in.',
                ext: ext,
              )
            : ref
                  .watch(plantsStreamProvider(uid))
                  .when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (error, _) => _CenteredMessage(
                      icon: Icons.cloud_off_outlined,
                      title: "Couldn't load your collection",
                      subtitle: 'Check your connection and try again.',
                      ext: ext,
                    ),
                    data: (snapshot) =>
                        _CollectionBody(snapshot: snapshot, ext: ext),
                  ),
      ),
    );
  }
}

/// Renders the populated collection: count eyebrow + sync badge, then either the
/// plant grid (with an "add" tile) or an empty-state call to action.
class _CollectionBody extends StatelessWidget {
  const _CollectionBody({required this.snapshot, required this.ext});

  final PlantsSnapshot snapshot;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final plants = snapshot.plants;
    final eyebrowStyle = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);

    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: EdgeInsets.all(ext.padScreen),
          sliver: SliverList(
            delegate: SliverChildListDelegate([
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${plants.length} '
                      '${plants.length == 1 ? "PLANT" : "PLANTS"} IDENTIFIED',
                      style: eyebrowStyle,
                    ),
                  ),
                  _SyncBadge(snapshot: snapshot, ext: ext),
                ],
              ),
              SizedBox(height: ext.gapY),
            ]),
          ),
        ),
        if (plants.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: _EmptyState(ext: ext),
          )
        else
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
                ...plants.map((p) => _PlantCard(plant: p, ext: ext)),
                _AddCard(ext: ext),
              ]),
            ),
          ),
      ],
    );
  }
}

/// Small pill that surfaces Firestore sync state. Renders nothing when fully
/// synced from the server; shows "Syncing…" for pending local writes and
/// "Offline" when data is served from the local cache.
class _SyncBadge extends StatelessWidget {
  const _SyncBadge({required this.snapshot, required this.ext});

  final PlantsSnapshot snapshot;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final IconData icon;
    final String label;
    if (snapshot.hasPendingWrites) {
      icon = Icons.sync;
      label = 'Syncing…';
    } else if (snapshot.isFromCache) {
      icon = Icons.cloud_off_outlined;
      label = 'Offline';
    } else {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: ext.ink3.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: ext.ink2),
          const SizedBox(width: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: ext.ink2,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _PlantCard extends StatelessWidget {
  const _PlantCard({required this.plant, required this.ext});

  final Plant plant;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final hasImage = plant.imageUrl != null && plant.imageUrl!.isNotEmpty;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 100,
            width: double.infinity,
            child: hasImage
                ? CachedNetworkImage(
                    imageUrl: plant.imageUrl!,
                    fit: BoxFit.cover,
                    placeholder: (_, _) => _imagePlaceholder(cs),
                    errorWidget: (_, _, _) => _imagePlaceholder(cs),
                  )
                : _imagePlaceholder(cs),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plant.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  plant.scientificName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
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

  Widget _imagePlaceholder(ColorScheme cs) => Container(
    color: cs.surfaceContainerLow,
    alignment: Alignment.center,
    child: Icon(Icons.eco, size: 32, color: cs.primary.withValues(alpha: 0.4)),
  );
}

class _AddCard extends StatelessWidget {
  const _AddCard({required this.ext});

  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final radius = BorderRadius.circular(AppSpacing.rMd);

    return Material(
      color: cs.surfaceContainerLow,
      borderRadius: radius,
      child: InkWell(
        onTap: () => context.go(AppRoutes.camera),
        borderRadius: radius,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(color: cs.outlineVariant, width: 2),
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
        ),
      ),
    );
  }
}

/// Empty state shown when the user has no identified plants yet.
class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.ext});

  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(ext.padScreen),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.eco_outlined, size: 48, color: ext.ink3),
          SizedBox(height: ext.gapY),
          Text('No plants yet', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Identify your first plant and it will appear here — even offline.',
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: ext.ink3),
          ),
          SizedBox(height: ext.gapY),
          FilledButton.icon(
            onPressed: () => context.go(AppRoutes.camera),
            icon: const Icon(Icons.add_a_photo_outlined),
            label: const Text('Identify a plant'),
          ),
        ],
      ),
    );
  }
}

/// Centered icon + title + subtitle, used for signed-out and error states.
class _CenteredMessage extends StatelessWidget {
  const _CenteredMessage({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.ext,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: EdgeInsets.all(ext.padScreen),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: ext.ink3),
            SizedBox(height: ext.gapY),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              subtitle,
              textAlign: TextAlign.center,
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
