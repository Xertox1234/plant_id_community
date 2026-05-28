import { memo, useMemo } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { sanitizeHtml, SANITIZE_PRESETS } from '../../utils/sanitize';
import { useAuth } from '../../contexts/AuthContext';
import type { Post } from '@/types';

interface PostCardProps {
  post: Post;
  onEdit?: (post: Post) => void;
  onDelete?: (post: Post) => void;
  onReact?: (postId: string, reactionType: string) => void;
}

// The four reaction types the backend supports.
const REACTION_TYPES = ['like', 'love', 'helpful', 'thanks'] as const;

// Helper function for reaction emojis
function getReactionEmoji(type: string): string {
  const emojis: Record<string, string> = {
    like: '👍',
    love: '❤️',
    helpful: '💡',
    thanks: '🙏',
  };
  return emojis[type] || '✨';
}

/**
 * PostCard Component
 *
 * Displays a single post in a thread.
 * Includes author info, content, reactions, and edit/delete options.
 */
function PostCard({ post, onEdit, onDelete, onReact }: PostCardProps) {
  const { user } = useAuth();

  const isAuthor = user && String(user.id) === String(post.author.id);
  const isModerator = user && (user.is_staff || user.is_moderator);
  const canEdit = isAuthor || isModerator;

  // Memoize formatted date
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(post.created_at), { addSuffix: true });
    } catch {
      return 'recently';
    }
  }, [post.created_at]);

  // Sanitize content for display
  const sanitizedContent = useMemo(() => {
    return sanitizeHtml(post.content_raw, SANITIZE_PRESETS.FORUM);
  }, [post.content_raw]);

  return (
    <div
      className={`
        group bg-white dark:bg-gray-800 rounded-lg shadow-md p-6
        ${post.is_first_post ? 'border-l-4 border-green-500' : ''}
      `}
    >
      {/* Post Header */}
      <div className="flex items-start justify-between flex-wrap gap-2 mb-4">
        {/* Author Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
            <span className="text-xl font-bold text-green-700 dark:text-green-400">
              {post.author.display_name?.[0] || post.author.username[0]}
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {post.author.display_name || post.author.username}
              </span>

              {post.author.trust_level && (
                <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 text-xs rounded">
                  {post.author.trust_level}
                </span>
              )}

              {post.is_first_post && (
                <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400 text-xs rounded">
                  Original Post
                </span>
              )}
            </div>

            <div className="text-sm text-gray-500 dark:text-gray-400">
              <span title={new Date(post.created_at).toLocaleString()}>{formattedDate}</span>

              {post.edited_at && (
                <>
                  <span className="mx-1">•</span>
                  <span className="italic">
                    Edited {formatDistanceToNow(new Date(post.edited_at), { addSuffix: true })}
                    {post.edited_by &&
                      ` by ${post.edited_by.display_name || post.edited_by.username}`}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions (edit/delete) — always visible on mobile, fade in on desktop hover */}
        {canEdit && (
          <div className="flex gap-2 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onEdit?.(post)}
              className="min-h-11 px-3 py-1 text-sm text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded inline-flex items-center"
              title="Edit post"
            >
              ✏️ Edit
            </button>
            <button
              onClick={() => onDelete?.(post)}
              className="min-h-11 px-3 py-1 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded inline-flex items-center"
              title="Delete post"
            >
              🗑️ Delete
            </button>
          </div>
        )}
      </div>

      {/* Post Content */}
      <div
        className="prose prose-sm sm:prose-base max-w-none mb-4 break-words prose-pre:overflow-x-auto prose-img:max-w-full prose-img:h-auto prose-table:block prose-table:overflow-x-auto dark:prose-invert"
        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      />

      {/* Reactions — always show the four reaction buttons so a user can add a
          first reaction; counts default to 0 when none exist yet. */}
      <div className="flex gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
        {REACTION_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => onReact?.(post.id, type)}
            className="inline-flex items-center gap-1 min-h-11 px-3 py-1 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full text-sm transition-colors"
            aria-label={`React ${type}`}
            title={`React ${type}`}
          >
            <span>{getReactionEmoji(type)}</span>
            <span className="font-medium">{post.reaction_counts?.[type] ?? 0}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default memo(PostCard);
