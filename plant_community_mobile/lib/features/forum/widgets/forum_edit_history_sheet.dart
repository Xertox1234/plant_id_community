import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../services/forum_api.dart';
import 'forum_body_renderer.dart';

/// Open a post's edit history (todo 341; web: EditHistoryDialog). The
/// "edited" stamp on a card opens this: the revision list (who, when —
/// newest first), and one revision's body rendered through the same
/// [ForumBodyRenderer] as the live post so the two are comparable.
/// [topicId] is the thread the sheet opened from — the renderer drops a
/// quote's "in topic" link when it points back here (todo 342).
Future<void> showForumEditHistorySheet(
  BuildContext context, {
  required int postId,
  int? topicId,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => ForumEditHistorySheet(postId: postId, topicId: topicId),
  );
}

/// Sheet body. Loads imperatively rather than through a `@riverpod`
/// provider on purpose: a 403 here is an EXPECTED state (see
/// [ForumApi.fetchPostRevisions]), and a `FutureProvider` that errors
/// auto-retries on a backoff timer — leaving a pending timer behind the
/// sheet for a refusal that will never change (docs/rules/flutter.md).
class ForumEditHistorySheet extends ConsumerStatefulWidget {
  const ForumEditHistorySheet({super.key, required this.postId, this.topicId});

  final int postId;
  final int? topicId;

  @override
  ConsumerState<ForumEditHistorySheet> createState() =>
      _ForumEditHistorySheetState();
}

class _ForumEditHistorySheetState extends ConsumerState<ForumEditHistorySheet> {
  List<ForumPostRevision>? _revisions;
  ForumPostRevisionDetail? _selected;
  String? _error;
  bool _loading = true;

  /// The revision whose detail fetch is in flight — a response from a
  /// superseded tap must not overwrite the current selection.
  int? _latestRequest;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final revisions = await ref
          .read(forumApiProvider)
          .fetchPostRevisions(widget.postId);
      if (!mounted) return;
      setState(() {
        _revisions = revisions;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      // Branch on the STATUS, never the message text: DRF's PermissionDenied
      // line contains neither "403" nor "forbidden".
      setState(() {
        _error = e.statusCode == 403
            ? 'This post has been edited by a moderator, so its history is '
                  'only visible to moderators.'
            : "Couldn't load this post's edit history.";
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = "Couldn't load this post's edit history.";
        _loading = false;
      });
    }
  }

  Future<void> _select(ForumPostRevision revision) async {
    _latestRequest = revision.id;
    setState(() => _error = null);
    try {
      final detail = await ref
          .read(forumApiProvider)
          .fetchPostRevision(postId: widget.postId, revisionId: revision.id);
      if (!mounted || _latestRequest != revision.id) return;
      setState(() => _selected = detail);
    } catch (_) {
      if (!mounted || _latestRequest != revision.id) return;
      setState(() => _error = "Couldn't load that revision.");
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final selected = _selected;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.8,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            0,
            AppSpacing.md,
            AppSpacing.md,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (selected != null)
                    IconButton(
                      tooltip: 'Back to history',
                      onPressed: () => setState(() => _selected = null),
                      icon: const Icon(Icons.arrow_back),
                    ),
                  Expanded(
                    child: Text(
                      selected == null
                          ? 'Edit history'
                          : 'Revision from ${forumRelativeTime(selected.createdAt)}',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              // Always mounted so the live region survives state changes.
              Semantics(
                liveRegion: true,
                child: _error == null
                    ? const SizedBox.shrink()
                    : Padding(
                        padding: const EdgeInsets.symmetric(
                          vertical: AppSpacing.sm,
                        ),
                        child: Text(
                          _error ?? '',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.error,
                          ),
                        ),
                      ),
              ),
              Flexible(child: _content(context, selected)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _content(BuildContext context, ForumPostRevisionDetail? selected) {
    final theme = Theme.of(context);
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(AppSpacing.lg),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (selected != null) {
      return SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
          child: ForumBodyRenderer(
            selected.body,
            currentTopicId: widget.topicId,
          ),
        ),
      );
    }
    final revisions = _revisions;
    if (revisions == null) return const SizedBox.shrink();
    if (revisions.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Text(
          'No revisions recorded for this post.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      itemCount: revisions.length,
      itemBuilder: (context, index) {
        final revision = revisions[index];
        return ListTile(
          contentPadding: EdgeInsets.zero,
          minTileHeight: 48,
          leading: const Icon(Icons.history),
          title: Text(revision.user.name),
          subtitle: Text(forumRelativeTime(revision.createdAt)),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _select(revision),
        );
      },
    );
  }
}
