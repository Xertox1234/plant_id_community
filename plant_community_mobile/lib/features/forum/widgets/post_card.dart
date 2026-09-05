import 'package:flutter/material.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_body_renderer.dart';
import 'reaction_pills.dart';

/// A single forum post: author identity, moderation/edited markers, the
/// rendered StreamField body, and reactions.
///
/// Stateful only for the blocked-author reveal (todo 341): a post whose
/// author the viewer has blocked renders COLLAPSED (never hidden — removing
/// a reply mid-thread would break reply continuity) until "Show anyway" is
/// tapped, a local, no-refetch reveal that mirrors the web's PostCard.
class PostCard extends StatefulWidget {
  const PostCard({
    super.key,
    required this.post,
    this.onReact,
    this.onOpenLink,
    this.onEdit,
    this.onDelete,
    this.onReport,
    this.onAuthorTap,
    this.isSolution = false,
    this.onToggleSolution,
    this.onShowHistory,
    this.onQuote,
  });

  final ForumPost post;

  /// Non-null when the viewer may react (logged in). Called with the type.
  final void Function(String type)? onReact;
  final void Function(String href)? onOpenLink;

  /// Called when Edit is chosen. The caller (not this widget) gates
  /// visibility on `post.canEdit` — never re-derive ownership here (todo
  /// 292 AC1); this widget only renders what its caller already decided.
  final VoidCallback? onEdit;

  /// Called when Delete is chosen, AFTER the caller's own confirmation —
  /// this widget does not confirm destructive actions itself.
  final VoidCallback? onDelete;

  /// Called when Report is chosen. Shown only when `post.canReport` (never
  /// for the viewer's own post — server authority) AND a handler is wired.
  final VoidCallback? onReport;

  /// Called when the author identity is tapped — the caller navigates to
  /// the author's public profile. `null` (or a deleted author) renders no
  /// tap affordance at all (see [AuthorIdentity]).
  final VoidCallback? onAuthorTap;

  /// Whether this post is the topic's accepted answer — derived by the
  /// caller from `topic.solvedPostId` (the single source), never stored on
  /// the post.
  final bool isSolution;

  /// Called when "Mark as answer" / "Unmark answer" is chosen. The caller
  /// gates it on `topic.canMarkSolution` and never wires it on the opening
  /// post (the endpoint 422s a question marked as its own answer).
  final VoidCallback? onToggleSolution;

  /// Called when the "edited" stamp is tapped to open the edit history.
  /// When `null` the stamp is a static label (an anonymous viewer — the
  /// history endpoint is auth-only).
  final VoidCallback? onShowHistory;

  /// Called when the Quote action is tapped (todo 341 wave 3) — the caller
  /// opens the reply composer pre-filled with this post's text as a `quote`
  /// block. Wired only for a signed-in viewer on an open topic; `null`
  /// renders no button. A visible action beside the reactions, not a menu
  /// entry, so a post with no other capability still offers it.
  final VoidCallback? onQuote;

  @override
  State<PostCard> createState() => _PostCardState();
}

class _PostCardState extends State<PostCard> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    final post = widget.post;
    if (post.isBlocked && !_revealed) {
      return _BlockedPlaceholder(
        author: post.author,
        onReveal: () => setState(() => _revealed = true),
      );
    }
    final theme = Theme.of(context);
    final author = post.author;
    return Card(
      shape: widget.isSolution
          ? RoundedRectangleBorder(
              side: BorderSide(color: theme.colorScheme.secondary, width: 1.5),
              borderRadius: BorderRadius.circular(AppSpacing.rMd),
            )
          : null,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.isSolution)
              const Padding(
                padding: EdgeInsets.only(bottom: AppSpacing.sm),
                child: _SolutionChip(),
              ),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AuthorIdentity(author: author, onTap: widget.onAuthorTap),
                      if (forumRelativeTime(post.createdAt).isNotEmpty)
                        Text(
                          forumRelativeTime(post.createdAt),
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                    ],
                  ),
                ),
                if (post.isOpeningPost)
                  Icon(
                    Icons.push_pin_outlined,
                    size: 16,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                _PostMenu(
                  post: post,
                  onEdit: widget.onEdit,
                  onDelete: widget.onDelete,
                  onReport: widget.onReport,
                  isSolution: widget.isSolution,
                  onToggleSolution: widget.onToggleSolution,
                ),
              ],
            ),
            if (post.isPending)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: _PendingChip(),
              ),
            const SizedBox(height: AppSpacing.sm),
            ForumBodyRenderer(post.body, onOpenLink: widget.onOpenLink),
            if (post.isEdited)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: _EditedStamp(onTap: widget.onShowHistory),
              ),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Expanded(
                  child: ReactionPills(
                    counts: post.reactionCounts,
                    reacted: post.reacted,
                    onReact: widget.onReact,
                  ),
                ),
                if (widget.onQuote != null)
                  IconButton(
                    tooltip: 'Quote',
                    icon: const Icon(Icons.format_quote_outlined, size: 20),
                    onPressed: widget.onQuote,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Overflow menu with Mark-as-answer/Report/Edit/Delete, each gated on its
/// own capability flag (todo 292 AC1) — never shown just because a callback
/// exists. Absent entirely when nothing applies, so a viewer with no
/// capability sees no menu at all.
class _PostMenu extends StatelessWidget {
  const _PostMenu({
    required this.post,
    this.onEdit,
    this.onDelete,
    this.onReport,
    required this.isSolution,
    this.onToggleSolution,
  });

  final ForumPost post;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final VoidCallback? onReport;
  final bool isSolution;
  final VoidCallback? onToggleSolution;

  @override
  Widget build(BuildContext context) {
    final showEdit = onEdit != null && post.canEdit;
    final showDelete = onDelete != null && post.canDelete;
    final showReport = onReport != null && post.canReport;
    final showSolution = onToggleSolution != null;
    if (!showEdit && !showDelete && !showReport && !showSolution) {
      return const SizedBox.shrink();
    }
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert, size: 20),
      tooltip: 'Post options',
      onSelected: (value) {
        switch (value) {
          case 'edit':
            onEdit?.call();
          case 'delete':
            onDelete?.call();
          case 'report':
            onReport?.call();
          case 'solution':
            onToggleSolution?.call();
        }
      },
      itemBuilder: (context) => [
        if (showSolution)
          PopupMenuItem(
            value: 'solution',
            child: Text(isSolution ? 'Unmark answer' : 'Mark as answer'),
          ),
        if (showEdit) const PopupMenuItem(value: 'edit', child: Text('Edit')),
        if (showDelete)
          const PopupMenuItem(value: 'delete', child: Text('Delete')),
        if (showReport)
          const PopupMenuItem(value: 'report', child: Text('Report')),
      ],
    );
  }
}

/// Collapsed placeholder for a blocked author's post (todo 284/M9 on the
/// web; todo 341 here). The real content is already in the post (the
/// server doesn't redact) — "Show anyway" reveals it locally.
class _BlockedPlaceholder extends StatelessWidget {
  const _BlockedPlaceholder({required this.author, required this.onReveal});

  final ForumAuthor author;
  final VoidCallback onReveal;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          children: [
            Icon(
              Icons.block,
              size: 16,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                "You've blocked ${author.name}.",
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
            TextButton(onPressed: onReveal, child: const Text('Show anyway')),
          ],
        ),
      ),
    );
  }
}

/// The "edited" stamp — a tappable history affordance when [onTap] is
/// wired (44px target), a static italic label otherwise.
class _EditedStamp extends StatelessWidget {
  const _EditedStamp({this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = theme.textTheme.labelSmall?.copyWith(
      fontStyle: FontStyle.italic,
      color: theme.colorScheme.onSurfaceVariant,
    );
    final onTap = this.onTap;
    if (onTap == null) return Text('edited', style: style);
    return Tooltip(
      message: 'View edit history',
      child: TextButton.icon(
        onPressed: onTap,
        style: TextButton.styleFrom(
          padding: EdgeInsets.zero,
          minimumSize: const Size(48, 48),
          alignment: Alignment.centerLeft,
          foregroundColor: theme.colorScheme.onSurfaceVariant,
        ),
        icon: const Icon(Icons.history, size: 14),
        label: Text('edited', style: style),
      ),
    );
  }
}

class _SolutionChip extends StatelessWidget {
  const _SolutionChip();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: 'Accepted answer',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: theme.colorScheme.secondaryContainer,
          borderRadius: BorderRadius.circular(AppSpacing.rXs),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.check_circle,
              size: 14,
              color: theme.colorScheme.onSecondaryContainer,
            ),
            const SizedBox(width: AppSpacing.xs),
            Text(
              'Accepted answer',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSecondaryContainer,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PendingChip extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.rXs),
      ),
      child: Text(
        'Awaiting moderation',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onTertiaryContainer,
        ),
      ),
    );
  }
}
