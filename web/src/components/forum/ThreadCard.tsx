import { memo, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { logger } from '../../utils/logger';
import { threadPath } from '../../utils/forumUrls';
import type { Thread } from '@/types';

interface ThreadCardProps {
  thread: Thread;
  compact?: boolean;
  /** Pass true for search results where author data is unavailable (sentinel). */
  hideAuthor?: boolean;
}

/**
 * ThreadCard Component
 *
 * Displays a thread preview in the thread list.
 * Shows title, excerpt, author, stats, and activity time.
 */
function ThreadCard({ thread, compact = false, hideAuthor = false }: ThreadCardProps) {
  // Memoize formatted date to prevent recalculation
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(thread.last_activity_at), {
        addSuffix: true,
      });
    } catch (error) {
      logger.error('Error formatting date in ThreadCard', {
        component: 'ThreadCard',
        error,
        context: { threadId: thread.id, lastActivityAt: thread.last_activity_at },
      });
      return 'recently';
    }
  }, [thread.last_activity_at, thread.id]);

  const threadUrl = threadPath(thread.category, thread);

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
          <span title={new Date(thread.last_activity_at).toLocaleString()}>{formattedDate}</span>
        </div>
      </Link>
    </div>
  );
}

export default memo(ThreadCard);
