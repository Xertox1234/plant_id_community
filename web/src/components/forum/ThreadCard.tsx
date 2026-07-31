import { memo } from 'react';
import { Link } from 'react-router-dom';
import { threadPath } from '../../utils/forumUrls';
import Timestamp from '../ui/Timestamp';
import type { Thread } from '@/types';

interface ThreadCardProps {
  thread: Thread;
  compact?: boolean;
  /** Pass true for search results where author data is unavailable (sentinel). */
  hideAuthor?: boolean;
  /**
   * Filter the list by a tag (audit M5). When omitted the tags still render, but
   * as inert chips — used where there is no list to filter (e.g. search results).
   */
  onTagClick?: (tag: string) => void;
  /** The tag currently filtering the list, so its chip can read as active. */
  activeTag?: string;
}

/**
 * ThreadCard Component
 *
 * Displays a thread preview in the thread list.
 * Shows title, excerpt, author, stats, and activity time.
 */
function ThreadCard({
  thread,
  compact = false,
  hideAuthor = false,
  onTagClick,
  activeTag,
}: ThreadCardProps) {
  const threadUrl = threadPath(thread.category, thread);
  const tags = thread.tags ?? [];

  return (
    <div
      className={`
      bg-surface-2 rounded-lg shadow-md hover:shadow-lg transition-shadow
      ${thread.is_pinned ? 'border-l-4 border-tertiary bg-tertiary/10' : ''}
      ${thread.is_locked ? 'opacity-75' : ''}
      ${compact ? 'p-3' : 'p-6'}
    `}
    >
      <Link to={threadUrl} className="block">
        {/* Badges */}
        <div className="flex flex-wrap gap-2 mb-2">
          {thread.is_pinned && (
            <span className="px-2 py-1 bg-tertiary/20 text-ink text-xs font-semibold rounded">
              📌 Pinned
            </span>
          )}
          {thread.is_locked && (
            <span className="px-2 py-1 bg-surface-3 text-ink-2 text-xs font-semibold rounded">
              🔒 Locked
            </span>
          )}
          {thread.is_solved && (
            /* `text-ink` on a tinted surface, mirroring the Pinned badge — NOT
               `text-ok`, whose token is the same dark green in every theme and
               so fails contrast on the dark ones. */
            <span className="px-2 py-1 bg-secondary/20 text-ink text-xs font-semibold rounded">
              {/* The checkmark is decorative — "Solved" already carries the
                  meaning, so a screen reader must not announce "check mark". */}
              <span aria-hidden="true">✓</span> Solved
            </span>
          )}
          {thread.is_unread && (
            <span className="px-2 py-1 bg-primary/10 text-primary text-xs font-semibold rounded">
              New
            </span>
          )}
        </div>

        {/* Thread Title */}
        <h3
          className={`
          font-bold text-ink hover:text-primary transition-colors
          ${compact ? 'text-lg mb-1' : 'text-xl mb-2'}
        `}
        >
          {thread.title}
        </h3>

        {/* Excerpt (not in compact mode) */}
        {!compact && thread.excerpt && (
          <p className="text-ink-2 mb-4 line-clamp-2">{thread.excerpt}</p>
        )}

        {/* Metadata */}
        <div className="flex items-center gap-2 text-sm text-ink-3 flex-wrap">
          {/* Author — omitted for search results where no real author data exists */}
          {!hideAuthor && (
            <>
              {/* The whole card is already a <Link> to the thread, so the author
                  name stays plain text here — a nested <a> is invalid HTML. The
                  clickable author link lives on PostCard + the thread header. */}
              <span className="font-medium text-ink-2">
                {thread.author.display_name || thread.author.username}
              </span>
              <span aria-hidden="true">•</span>
            </>
          )}

          {/* Category (if compact) */}
          {compact && (
            <>
              <span>
                {thread.category.icon && <span className="mr-1">{thread.category.icon}</span>}
                {thread.category.name}
              </span>
              <span aria-hidden="true">•</span>
            </>
          )}

          {/* Stats */}
          <span title={`${thread.post_count} replies`}>💬 {thread.post_count || 0}</span>

          <span aria-hidden="true">•</span>

          <span title={`${thread.view_count} views`}>👁️ {thread.view_count || 0}</span>

          <span aria-hidden="true">•</span>

          {/* Last Activity */}
          <Timestamp iso={thread.last_activity_at} prefix="Last activity" />
        </div>
      </Link>

      {/* Tags (audit M5) — deliberately OUTSIDE the card-level <Link>: a nested
          <a>/<button> inside an anchor is invalid HTML (the browser auto-closes
          the outer one) and breaks getByRole('link'). Chips are buttons only
          when the parent can actually filter; otherwise they are inert text. */}
      {tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {tags.map((tag) =>
            onTagClick ? (
              <button
                key={tag}
                type="button"
                onClick={() => onTagClick(tag)}
                aria-pressed={tag === activeTag}
                className={`inline-flex min-h-11 items-center rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  tag === activeTag
                    ? 'bg-primary/20 text-primary ring-1 ring-primary/40'
                    : 'bg-surface-3 text-ink-2 hover:bg-surface-1'
                }`}
              >
                #{tag}
              </button>
            ) : (
              <span
                key={tag}
                className="rounded-full bg-surface-3 px-3 py-1 text-xs font-medium text-ink-2"
              >
                #{tag}
              </span>
            )
          )}
        </div>
      )}
    </div>
  );
}

export default memo(ThreadCard);
