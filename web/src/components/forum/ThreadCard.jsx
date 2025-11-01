import { memo, useMemo } from 'react';
import { Link } from 'react-router';
import PropTypes from 'prop-types';
import { formatDistanceToNow } from 'date-fns';
import { logger } from '../../utils/logger';

/**
 * ThreadCard Component
 *
 * Displays a thread preview in the thread list.
 * Shows title, excerpt, author, stats, and activity time.
 */
function ThreadCard({ thread, compact = false }) {
  // Memoize formatted date to prevent recalculation
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(thread.last_activity_at), {
        addSuffix: true
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

  const threadUrl = `/forum/${thread.category.slug}/${thread.slug}`;

  return (
    <div className={`
      bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow
      ${thread.is_pinned ? 'border-l-4 border-yellow-500 bg-yellow-50' : ''}
      ${thread.is_locked ? 'opacity-75' : ''}
      ${compact ? 'p-3' : 'p-6'}
    `}>
      <Link to={threadUrl} className="block">
        {/* Badges */}
        <div className="flex gap-2 mb-2">
          {thread.is_pinned && (
            <span className="px-2 py-1 bg-yellow-200 text-yellow-900 text-xs font-semibold rounded">
              📌 Pinned
            </span>
          )}
          {thread.is_locked && (
            <span className="px-2 py-1 bg-gray-200 text-gray-700 text-xs font-semibold rounded">
              🔒 Locked
            </span>
          )}
        </div>

        {/* Thread Title */}
        <h3 className={`
          font-bold text-gray-900 hover:text-green-600 transition-colors
          ${compact ? 'text-lg mb-1' : 'text-xl mb-2'}
        `}>
          {thread.title}
        </h3>

        {/* Excerpt (not in compact mode) */}
        {!compact && thread.excerpt && (
          <p className="text-gray-600 mb-4 line-clamp-2">
            {thread.excerpt}
          </p>
        )}

        {/* Metadata */}
        <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
          {/* Author */}
          <span className="font-medium text-gray-700">
            {thread.author.display_name || thread.author.username}
          </span>

          <span aria-hidden="true">•</span>

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
          <span title={`${thread.post_count} replies`}>
            💬 {thread.post_count || 0}
          </span>

          <span aria-hidden="true">•</span>

          <span title={`${thread.view_count} views`}>
            👁️ {thread.view_count || 0}
          </span>

          <span aria-hidden="true">•</span>

          {/* Last Activity */}
          <span title={new Date(thread.last_activity_at).toLocaleString()}>
            {formattedDate}
          </span>
        </div>
      </Link>
    </div>
  );
}

ThreadCard.propTypes = {
  thread: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    slug: PropTypes.string.isRequired,
    excerpt: PropTypes.string,
    author: PropTypes.shape({
      id: PropTypes.number.isRequired,
      username: PropTypes.string.isRequired,
      display_name: PropTypes.string,
    }).isRequired,
    category: PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      slug: PropTypes.string.isRequired,
      icon: PropTypes.string,
    }).isRequired,
    is_pinned: PropTypes.bool,
    is_locked: PropTypes.bool,
    is_active: PropTypes.bool,
    view_count: PropTypes.number,
    post_count: PropTypes.number,
    last_activity_at: PropTypes.string.isRequired,
    created_at: PropTypes.string,
  }).isRequired,
  compact: PropTypes.bool,
};

export default memo(ThreadCard);
