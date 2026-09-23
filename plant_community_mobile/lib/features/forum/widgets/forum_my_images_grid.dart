import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../models/models.dart';
import '../services/forum_api.dart';

/// Open the "Choose from your photos" picker (todo 374; web:
/// `ForumImagePicker`). Resolves to the picked image, or `null` if the sheet
/// was dismissed. Picking reuses the existing image row: no upload, no new
/// row, no idempotency key.
Future<ForumImageBlock?> showForumMyImagesPicker(BuildContext context) {
  return showModalBottomSheet<ForumImageBlock>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) => SafeArea(
      child: SizedBox(
        height: MediaQuery.sizeOf(sheetContext).height * 0.7,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            0,
            AppSpacing.md,
            AppSpacing.md,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Choose from your photos',
                style: Theme.of(
                  sheetContext,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: AppSpacing.sm),
              Expanded(
                child: ForumMyImagesGrid(
                  onPick: (image) => Navigator.of(sheetContext).pop(image),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

/// The caller's own forum photos as a cursor-paginated grid, shared by the
/// composer's picker sheet ([onPick]) and the "My forum photos" screen
/// ([allowDelete]). Fills its parent, so give it bounded height.
///
/// Loads imperatively rather than through a `@riverpod` provider on purpose:
/// a 403 here is an EXPECTED state (not a Forum Member), and a
/// `FutureProvider` that errors auto-retries on a backoff timer for a refusal
/// that will never change (docs/rules/flutter.md, same as the edit-history
/// sheet). The server already scopes the list to the caller's own uploads;
/// nothing here filters it.
class ForumMyImagesGrid extends ConsumerStatefulWidget {
  const ForumMyImagesGrid({super.key, this.onPick, this.allowDelete = false});

  /// Called with the tapped image. Null makes tiles non-tappable.
  final ValueChanged<ForumImageBlock>? onPick;

  /// Shows a delete button on every tile, behind a confirmation dialog.
  final bool allowDelete;

  @override
  ConsumerState<ForumMyImagesGrid> createState() => _ForumMyImagesGridState();
}

enum _LoadState { loading, loaded, forbidden, failed }

class _ForumMyImagesGridState extends ConsumerState<ForumMyImagesGrid> {
  _LoadState _state = _LoadState.loading;
  final List<ForumImageBlock> _images = [];
  String? _next;
  bool _loadingMore = false;
  final Set<int> _deleting = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _state = _LoadState.loading);
    try {
      final page = await ref.read(forumApiProvider).fetchMyImages();
      if (!mounted) return;
      setState(() {
        _images
          ..clear()
          ..addAll(page.items);
        _next = page.next;
        _state = _LoadState.loaded;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      // Branch on the STATUS, never the message text: DRF's PermissionDenied
      // sentence contains neither "403" nor "forbidden".
      setState(
        () => _state = e.statusCode == 403
            ? _LoadState.forbidden
            : _LoadState.failed,
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _state = _LoadState.failed);
    }
  }

  Future<void> _loadMore() async {
    final cursor = _next;
    if (cursor == null || _loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final page = await ref
          .read(forumApiProvider)
          .fetchMyImages(cursorUrl: cursor);
      if (!mounted) return;
      setState(() {
        // A photo deleted from page one can't reappear here, but an id that
        // shifted pages between requests could arrive twice.
        final seen = _images.map((image) => image.id).toSet();
        _images.addAll(page.items.where((image) => seen.add(image.id)));
        _next = page.next;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingMore = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not load more photos.')),
      );
    }
  }

  Future<void> _confirmAndDelete(ForumImageBlock image) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete this photo?'),
        content: const Text(
          'It will also disappear from any posts you already shared it in. '
          'Those posts will show "Photo no longer available" instead. '
          "This can't be undone.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _deleting.add(image.id));
    String? failure;
    var gone = false;
    try {
      await ref.read(forumApiProvider).deleteMyImage(image.id);
      gone = true;
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        gone = true; // already deleted elsewhere: the goal is met
      } else if (e.statusCode == 403) {
        failure = 'You can only delete photos you uploaded.';
      } else {
        failure = e.message.isNotEmpty
            ? e.message
            : 'Could not delete that photo.';
      }
    } catch (_) {
      failure = 'Could not delete that photo.';
    }
    if (!mounted) return;
    setState(() {
      _deleting.remove(image.id);
      if (gone) _images.removeWhere((row) => row.id == image.id);
    });
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(failure ?? 'Photo deleted.')));
    // Deleting every loaded photo is not "no photos" while older pages exist:
    // fetch the next page rather than strand them behind an empty grid.
    if (_images.isEmpty && _next != null) await _loadMore();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.textTheme.bodyMedium?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );
    switch (_state) {
      case _LoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case _LoadState.forbidden:
        return _Message(
          key: const Key('forumMyImages.forbidden'),
          icon: LucideIcons.lock,
          text: 'Your photo library is only available to forum members.',
          style: muted,
        );
      case _LoadState.failed:
        return _Message(
          key: const Key('forumMyImages.error'),
          icon: LucideIcons.imageOff,
          text: "Couldn't load your photos.",
          style: muted,
          action: OutlinedButton(onPressed: _load, child: const Text('Retry')),
        );
      case _LoadState.loaded:
        break;
    }
    if (_images.isEmpty && _next == null) {
      return _Message(
        key: const Key('forumMyImages.empty'),
        icon: LucideIcons.images,
        text: 'No photos yet. Photos you add to forum posts will show up here.',
        style: muted,
      );
    }
    return CustomScrollView(
      slivers: [
        SliverGrid.builder(
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 140,
            mainAxisSpacing: AppSpacing.sm,
            crossAxisSpacing: AppSpacing.sm,
          ),
          itemCount: _images.length,
          itemBuilder: (context, index) {
            final image = _images[index];
            final onPick = widget.onPick;
            return _ImageTile(
              key: ValueKey('forumMyImages.tile.${image.id}'),
              image: image,
              onTap: onPick == null ? null : () => onPick(image),
              onDelete: widget.allowDelete
                  ? () => _confirmAndDelete(image)
                  : null,
              deleting: _deleting.contains(image.id),
            );
          },
        ),
        if (_next != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
              child: Center(
                child: _loadingMore
                    ? const CircularProgressIndicator()
                    : OutlinedButton(
                        onPressed: _loadMore,
                        child: const Text('Load more'),
                      ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ImageTile extends StatelessWidget {
  const _ImageTile({
    super.key,
    required this.image,
    required this.onTap,
    required this.onDelete,
    required this.deleting,
  });

  final ForumImageBlock image;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;
  final bool deleting;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final description = image.alt.trim();
    final label = description.isEmpty ? 'Photo' : 'Photo: $description';
    return Stack(
      fit: StackFit.expand,
      children: [
        Semantics(
          button: onTap != null,
          label: onTap != null ? 'Use this photo. $label' : label,
          // excludeSemantics drops the InkWell's own tap action, so the node
          // must carry it or a screen reader's double-tap does nothing.
          onTap: deleting ? null : onTap,
          excludeSemantics: true,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppSpacing.rTileMd),
            child: Material(
              color: theme.colorScheme.surfaceContainerHighest,
              child: InkWell(
                onTap: deleting ? null : onTap,
                child: CachedNetworkImage(
                  imageUrl: image.url,
                  fit: BoxFit.cover,
                  placeholder: (context, _) => const SizedBox.shrink(),
                  errorWidget: (context, _, _) => Icon(
                    LucideIcons.imageOff,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ),
        ),
        if (onDelete != null)
          Positioned(
            top: AppSpacing.xs,
            right: AppSpacing.xs,
            child: deleting
                ? const Padding(
                    padding: EdgeInsets.all(AppSpacing.sm),
                    child: SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : IconButton.filledTonal(
                    tooltip: 'Delete photo',
                    onPressed: onDelete,
                    icon: const Icon(LucideIcons.trash2, size: 18),
                  ),
          ),
      ],
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({
    super.key,
    required this.icon,
    required this.text,
    required this.style,
    this.action,
  });

  final IconData icon;
  final String text;
  final TextStyle? style;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final action = this.action;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 40,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(text, style: style, textAlign: TextAlign.center),
            if (action != null) ...[
              const SizedBox(height: AppSpacing.sm),
              action,
            ],
          ],
        ),
      ),
    );
  }
}
