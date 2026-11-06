import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show CustomSemanticsAction;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../shared/widgets/api_image.dart';
import '../../shared/widgets/canopy_surfaces.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../models/plant.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import '../profile/forum_notification_settings_card.dart' show apiErrorMessage;
import '../scan/capture_steps.dart';
import '../scan/scan_card_actions.dart';
import '../scan/scan_decisions.dart';
import '../scan/scan_job_api.dart';
import '../scan/scan_job_tracker.dart';
import '../scan/widgets/short_scan_card.dart';
import 'package:plant_community_mobile/core/routing/main_shell.dart';

/// Identified-plant collection hub.
///
/// Reads the user's plant collection from [plantsStreamProvider] — Firestore
/// with offline persistence — so the list is available offline, updates in real
/// time, and syncs across devices. Shows a sync/offline badge driven by the
/// snapshot metadata, and graceful signed-out / loading / error / empty states.
///
/// Finished scans still waiting for a keep-or-dismiss decision come first,
/// as [ShortScanCard]s; a long-press on a kept plant offers Remove.
class CollectionScreen extends ConsumerWidget {
  const CollectionScreen({super.key, this.now});

  /// The clock for the undecided cards' countdown; defaults to
  /// [DateTime.now]. Injected by tests.
  final DateTime Function()? now;

  static const removeActionKey = Key('plant-remove-action');
  static const removeConfirmKey = Key('plant-remove-confirm');

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
                icon: LucideIcons.user,
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
                      icon: LucideIcons.cloudOff,
                      title: "Couldn't load your collection",
                      subtitle: 'Check your connection and try again.',
                      ext: ext,
                    ),
                    data: (snapshot) => _CollectionBody(
                      snapshot: snapshot,
                      ext: ext,
                      now: now ?? DateTime.now,
                    ),
                  ),
      ),
    );
  }
}

/// Renders the populated collection: the undecided scans, the count eyebrow +
/// sync badge, then either the plant grid (with an "add" tile) or an
/// empty-state call to action (only when there are no undecided cards either).
class _CollectionBody extends ConsumerWidget {
  const _CollectionBody({
    required this.snapshot,
    required this.ext,
    required this.now,
  });

  final PlantsSnapshot snapshot;
  final GreenThumbExtension ext;
  final DateTime Function() now;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final plants = snapshot.plants;
    final eyebrowStyle = Theme.of(
      context,
    ).textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3);
    // A fetch error (offline) hides the section; the kept grid still shows.
    // A refetch (after a dismiss) keeps the previous cards, no flicker.
    final undecidedAsync = ref.watch(undecidedScansProvider);
    final undecided = undecidedAsync.hasError
        ? const <ScanJob>[]
        : undecidedAsync.value ?? const <ScanJob>[];

    return _MinuteClock(
      now: now,
      builder: (context, at) {
        final cards = _liveCards(undecided, at);
        return CustomScrollView(
          slivers: [
            if (cards.isNotEmpty)
              SliverPadding(
                padding: EdgeInsets.fromLTRB(
                  ext.padScreen,
                  ext.padScreen,
                  ext.padScreen,
                  0,
                ),
                sliver: SliverList.separated(
                  itemCount: cards.length,
                  separatorBuilder: (_, _) => SizedBox(height: ext.gapY),
                  itemBuilder: (context, i) => _UndecidedCard(
                    key: ValueKey(cards[i].id),
                    job: cards[i],
                    now: now,
                  ),
                ),
              ),
            SliverPadding(
              padding:
                  EdgeInsets.all(ext.padScreen) +
                  MainShell.fabClearanceOf(context),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${plants.length} '
                          '${plants.length == 1 ? "PLANT" : "PLANTS"} '
                          'IDENTIFIED',
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
            if (plants.isEmpty && cards.isEmpty)
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
      },
    );
  }

  /// Undecided scans still inside their decide-by time, newest first. One
  /// past it goes at once, without waiting for the server's sweep; one with
  /// no decide-by (the server always sets it) is left out.
  static List<ScanJob> _liveCards(List<ScanJob> jobs, DateTime at) {
    final live = [
      for (final j in jobs)
        if (j.decideBy != null && j.decideBy!.isAfter(at)) j,
    ]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return live;
  }
}

/// Rebuilds [builder] every minute with the time from [now], so the
/// countdowns tick and an expired card drops out.
class _MinuteClock extends StatefulWidget {
  const _MinuteClock({required this.now, required this.builder});

  final DateTime Function() now;
  final Widget Function(BuildContext context, DateTime now) builder;

  @override
  State<_MinuteClock> createState() => _MinuteClockState();
}

class _MinuteClockState extends State<_MinuteClock> {
  late final Timer _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.builder(context, widget.now());
}

/// One undecided scan in My Plants: View opens the full result, Dismiss
/// erases it, and a half-result the tracker can still re-run offers Try
/// again (the same rule as `/scans/<id>`).
class _UndecidedCard extends ConsumerWidget {
  const _UndecidedCard({super.key, required this.job, required this.now});

  final ScanJob job;
  final DateTime Function() now;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canRetry = watchCanRetryScan(ref, job.id);
    return ShortScanCard(
      job: job,
      now: now,
      onView: () => context.push(scanFullResultPath(job.id)),
      onDismiss: () => _dismiss(context, ref),
      onTryAgain: canRetry ? () => _tryAgain(context, ref) : null,
    );
  }

  void _tryAgain(BuildContext context, WidgetRef ref) {
    final mode = ref.read(scanJobTrackerProvider).lastCapture?.mode;
    final messenger = ScaffoldMessenger.maybeOf(context);
    unawaited(
      reportScanRetry(
        ref.read(scanJobTrackerProvider.notifier).retry(),
        mode: mode ?? ScanMode.diagnose,
        messenger: messenger,
      ),
    );
  }

  Future<void> _dismiss(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.maybeOf(context);
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await ref.read(scanDecisionsProvider).dismiss(job.id);
    } catch (e) {
      debugPrint('[SCAN_JOB] Dismiss from My Plants failed: ${e.runtimeType}');
      messenger?.showSnackBar(
        SnackBar(
          content: Text(
            apiErrorMessage(e) ?? "Couldn't dismiss the scan. Try again.",
          ),
        ),
      );
      return;
    }
    clearTrackedScanPill(container, job.id);
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
      icon = LucideIcons.refreshCw;
      label = 'Syncing…';
    } else if (snapshot.isFromCache) {
      icon = LucideIcons.cloudOff;
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

    void openActions() => unawaited(_showPlantActions(context, plant));

    // Remove is also a semantics action, so a screen reader reaches it
    // without the gesture (docs/rules/flutter.md).
    return Semantics(
      customSemanticsActions: {
        const CustomSemanticsAction(label: 'Remove'): openActions,
      },
      child: GestureDetector(
        onLongPress: () {
          Feedback.forLongPress(context);
          openActions();
        },
        child: _card(context, cs, hasImage),
      ),
    );
  }

  Widget _card(BuildContext context, ColorScheme cs, bool hasImage) {
    return CanopyCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 100,
            width: double.infinity,
            child: hasImage
                ? ApiImage(
                    url: plant.imageUrl!,
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
                    style: AppTypography.micro.copyWith(
                      color: GreenThumbExtension.onLeaf,
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
    child: Icon(
      LucideIcons.leaf,
      size: 32,
      color: cs.primary.withValues(alpha: 0.4),
    ),
  );
}

/// The long-press sheet of a kept plant: "Remove", then a confirmation.
Future<void> _showPlantActions(BuildContext context, Plant plant) async {
  final remove = await showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    builder: (sheetContext) => SafeArea(
      child: ListTile(
        key: CollectionScreen.removeActionKey,
        leading: Icon(
          LucideIcons.trash2,
          color: Theme.of(sheetContext).colorScheme.error,
        ),
        title: const Text('Remove'),
        onTap: () => Navigator.of(sheetContext).pop(true),
      ),
    ),
  );
  if (remove != true || !context.mounted) return;
  final confirmed = await _confirmRemove(context, plant);
  if (confirmed != true || !context.mounted) return;

  final messenger = ScaffoldMessenger.maybeOf(context);
  final decisions = ProviderScope.containerOf(
    context,
    listen: false,
  ).read(scanDecisionsProvider);
  try {
    await decisions.removePlant(plant);
  } catch (e) {
    debugPrint('[COLLECTION] Remove failed: ${e.runtimeType}');
    messenger?.showSnackBar(
      SnackBar(
        content: Text(
          apiErrorMessage(e) ?? "Couldn't remove the plant. Try again.",
        ),
      ),
    );
  }
}

/// "Remove `name` from My Plants?" with Remove / Cancel, in-app.
Future<bool?> _confirmRemove(BuildContext context, Plant plant) {
  return showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);
      return Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Remove ${plant.name} from My Plants?',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            FilledButton(
              key: CollectionScreen.removeConfirmKey,
              style: FilledButton.styleFrom(
                backgroundColor: theme.colorScheme.error,
                foregroundColor: theme.colorScheme.onError,
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: () => Navigator.of(sheetContext).pop(true),
              child: const Text('Remove'),
            ),
            const SizedBox(height: AppSpacing.sm),
            TextButton(
              style: TextButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: () => Navigator.of(sheetContext).pop(false),
              child: const Text('Cancel'),
            ),
          ],
        ),
      );
    },
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
        onTap: () => context.push(AppRoutes.camera),
        borderRadius: radius,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(color: ext.line2, width: 2),
          ),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(LucideIcons.plus, color: ext.ink3, size: 28),
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
          Icon(LucideIcons.leaf, size: 48, color: ext.ink3),
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
            onPressed: () => context.push(AppRoutes.camera),
            icon: const Icon(LucideIcons.camera),
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
