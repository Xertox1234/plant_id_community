import { memo, useMemo, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { sanitizeHtml, SANITIZE_PRESETS } from '../../utils/sanitize';
import { useAuth } from '../../contexts/AuthContext';
import type { Post } from '@/types';

interface PostCardProps {
  post: Post;
  onEdit?: (post: Post) => void;
  onDelete?: (post: Post) => void;
}

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
function PostCard({ post, onEdit, onDelete }: PostCardProps) {
  const { user } = useAuth();
  const [showActions, setShowActions] = useState(false);

  const isAuthor = user && user.id === post.author.id;
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
        bg-white rounded-lg shadow-md p-6
        ${post.is_first_post ? 'border-l-4 border-green-500' : ''}
      `}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Post Header */}
      <div className="flex items-start justify-between mb-4">
        {/* Author Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
            <span className="text-xl font-bold text-green-700">
              {post.author.display_name?.[0] || post.author.username[0]}
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">
                {post.author.display_name || post.author.username}
              </span>

              {post.author.trust_level && (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded">
                  {post.author.trust_level}
                </span>
              )}

              {post.is_first_post && (
                <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded">
                  Original Post
                </span>
              )}
            </div>

            <div className="text-sm text-gray-500">
              <span title={new Date(post.created_at).toLocaleString()}>
                {formattedDate}
              </span>

              {post.edited_at && (
                <>
                  <span className="mx-1">•</span>
                  <span className="italic">
                    Edited {formatDistanceToNow(new Date(post.edited_at), { addSuffix: true })}
                    {post.edited_by && ` by ${post.edited_by.display_name || post.edited_by.username}`}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions (edit/delete) */}
        {canEdit && showActions && (
          <div className="flex gap-2">
            <button
              onClick={() => onEdit?.(post)}
              className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
              title="Edit post"
            >
              ✏️ Edit
            </button>
            <button
              onClick={() => onDelete?.(post)}
              className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
              title="Delete post"
            >
              🗑️ Delete
            </button>
          </div>
        )}
      </div>

      {/* Post Content */}
      <div
        className="prose max-w-none mb-4"
        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      />

      {/* Reactions */}
      {post.reaction_counts && Object.keys(post.reaction_counts).length > 0 && (
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          {Object.entries(post.reaction_counts).map(([type, count]) => (
            count > 0 && (
              <button
                key={type}
                className="flex items-center gap-1 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-sm transition-colors"
                title={`${count} ${type} reactions`}
              >
                <span>{getReactionEmoji(type)}</span>
                <span className="font-medium">{count}</span>
              </button>
            )
          ))}
        </div>
      )}
    </div>
  );
}

export default memo(PostCard);
