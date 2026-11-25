import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../shared/widgets/canopy_surfaces.dart';
import '../forum_format.dart';
import '../models/models.dart';
import 'author_identity.dart';
import 'forum_body_renderer.dart';
import 'forum_style.dart';
import 'reaction_pills.dart';

/// A single forum post: author identity, moderation/edited markers, the
/// rendered StreamField body, and reactions.
///
/// Stateful only for the blocked/muted-author reveal (todo 341): a post whose
/// author the viewer has blocked or muted renders COLLAPSED (never hidden — removing
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
    this.onToggleMute,
    this.currentTopicId,
  });

  final ForumPost post;

  /// The topic this card is shown in — handed to [ForumBodyRenderer] so a
  /// `post_quote` of a post in this same topic drops its "in topic" link
  /// (todo 342). `null` where the surface doesn't know (profile activity).
  final int? currentTopicId;

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

  /// Called when Mute or Unmute is chosen, in the menu or on the muted
  /// placeholder. Shown only when `post.canMute` AND a handler is wired.
  final VoidCallback? onToggleMute;

  @override
  State<PostCard> createState() => _PostCardState();
}

class _PostCardState extends State<PostCard> {
  bool _revealed = false;

  @override
  void didUpdateWidget(covariant PostCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    // A reveal answers one block or mute; a new one collapses again.
    if (oldWidget.post.isBlocked != widget.post.isBlocked ||
        oldWidget.post.isMuted != widget.post.isMuted) {
      _revealed = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final post = widget.post;
    if ((post.isBlocked || post.isMuted) && !_revealed) {
      return _CollapsedPlaceholder(
        blocked: post.isBlocked,
        onUnmute: post.canMute ? widget.onToggleMute : null,
        author: post.author,
        onReveal: () => setState(() => _revealed = true),
      );
    }
    final theme = Theme.of(context);
    final author = post.author;
    return CanopyCard(
      accentBorder: widget.isSolution ? theme.colorScheme.secondary : null,
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
              // The avatar leads both lines, so the date sits under the name
              // on the same text edge instead of under the avatar.
              // A second way in for a finger only: the name beside it is the
              // labelled control, so the detector publishes no semantics of
              // its own (an action with no label is an unnamed button).
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                excludeFromSemantics: true,
                onTap: author.isDeleted ? null : widget.onAuthorTap,
                child: ExcludeSemantics(
                  child: AuthorAvatar(author: author, radius: 20),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AuthorIdentity(
                      author: author,
                      onTap: widget.onAuthorTap,
                      showAvatar: false,
                    ),
                    if (forumRelativeTime(post.createdAt).isNotEmpty)
                      Text(
                        forumRelativeTime(post.createdAt),
                        style: forumMeta(context),
                      ),
                  ],
                ),
              ),
              if (post.isOpeningPost)
                // A sprout, not a pin: this marks the post the topic grew
                // from, and a pin now means "pinned to the top of the forum"
                // (the thread's own pin button, the list's Pinned label).
                Tooltip(
                  message: 'Opening post',
                  child: Icon(
                    LucideIcons.sprout,
                    size: 16,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              _PostMenu(
                post: post,
                onEdit: widget.onEdit,
                onDelete: widget.onDelete,
                onReport: widget.onReport,
                onToggleMute: widget.onToggleMute,
                isSolution: widget.isSolution,
                onToggleSolution: widget.onToggleSolution,
              ),
            ],
          ),
          if (post.isPending)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: const _PendingChip(),
            ),
          const SizedBox(height: AppSpacing.sm),
          ForumBodyRenderer(
            post.body,
            onOpenLink: widget.onOpenLink,
            currentTopicId: widget.currentTopicId,
          ),
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
                  icon: const Icon(LucideIcons.quote, size: 20),
                  onPressed: widget.onQuote,
                ),
            ],
          ),
        ],
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
    this.onToggleMute,
    required this.isSolution,
    this.onToggleSolution,
  });

  final ForumPost post;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final VoidCallback? onReport;
  final VoidCallback? onToggleMute;
  final bool isSolution;
  final VoidCallback? onToggleSolution;

  @override
  Widget build(BuildContext context) {
    final showEdit = onEdit != null && post.canEdit;
    final showDelete = onDelete != null && post.canDelete;
    final showReport = onReport != null && post.canReport;
    final showSolution = onToggleSolution != null;
    final showMute = onToggleMute != null && post.canMute;
    if (!showEdit && !showDelete && !showReport && !showSolution && !showMute) {
      return const SizedBox.shrink();
    }
    return PopupMenuButton<String>(
      icon: const Icon(LucideIcons.ellipsisVertical, size: 20),
      tooltip: 'Post options',
      onSelected: (value) {
        switch (value) {
          case 'edit':
            onEdit?.call();
          case 'delete':
            onDelete?.call();
          case 'report':
            onReport?.call();
          case 'mute':
            onToggleMute?.call();
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
        if (showMute)
          PopupMenuItem(
            value: 'mute',
            child: Text(post.isMuted ? 'Unmute member' : 'Mute member'),
          ),
        if (showReport)
          const PopupMenuItem(value: 'report', child: Text('Report')),
      ],
    );
  }
}

/// Collapsed placeholder for a blocked or muted author's post (todo 284/M9
/// on the web; todo 341 here). Blocked wins when both are set. The real content is already in the post (the
/// server doesn't redact) — "Show anyway" reveals it locally.
class _CollapsedPlaceholder extends StatelessWidget {
  const _CollapsedPlaceholder({
    required this.blocked,
    required this.author,
    required this.onReveal,
    this.onUnmute,
  });

  final bool blocked;

  final ForumAuthor author;
  final VoidCallback onReveal;

  /// Offered on the muted placeholder only.
  final VoidCallback? onUnmute;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final unmute = blocked ? null : onUnmute;
    final reveal = TextButton(
      onPressed: onReveal,
      child: const Text('Show anyway'),
    );
    final notice = Row(
      children: [
        Icon(
          blocked ? LucideIcons.ban : LucideIcons.volumeX,
          size: 16,
          color: theme.colorScheme.onSurfaceVariant,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            blocked
                ? "You've blocked ${author.name}."
                : "You've muted ${author.name}.",
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        if (unmute == null) reveal,
      ],
    );
    return CanopyCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: unmute == null
          ? notice
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: notice,
                ),
                // Two actions under the text: beside it they leave the name
                // no room at large text sizes.
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    children: [
                      TextButton(
                        onPressed: unmute,
                        child: const Text('Unmute'),
                      ),
                      reveal,
                    ],
                  ),
                ),
              ],
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
    // The forum's detail style, like the date above it: neither uppercased
    // nor letterspaced, and NOT italic. (The web uses its mono label face
    // here; on the phone Geist Mono is kept for the uppercase eyebrow only.)
    final style = forumMeta(context);
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
        icon: const Icon(LucideIcons.history, size: 14),
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
              LucideIcons.circleCheck,
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
  const _PendingChip();

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
