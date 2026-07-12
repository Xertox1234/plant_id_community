import { memo, useMemo, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import StreamFieldRenderer from '../StreamFieldRenderer';
import type { Post } from '@/types';

interface PostCardProps {
  post: Post;
  onEdit?: (post: Post) => void;
  onDelete?: (post: Post) => void;
  onReact?: (postId: string, reactionType: string) => void;
  onReport?: (postId: string, reason: string) => Promise<void>;
}

// The four reaction types the backend supports.
const REACTION_TYPES = ['like', 'love', 'helpful', 'thanks'] as const;

// Mirrors wagtail_forum Report.REASON_CHOICES.
const REPORT_REASONS = [
  { value: 'spam', label: 'Spam' },
  { value: 'abuse', label: 'Abuse' },
  { value: 'off_topic', label: 'Off topic' },
  { value: 'other', label: 'Other' },
] as const;

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
function PostCard({ post, onEdit, onDelete, onReact, onReport }: PostCardProps) {
  // Edit/delete/report visibility is driven by the backend capability flags
  // (PostSerializer.can_edit/can_delete/can_report) — the only authority on
  // author-or-mod (edit/delete) and not-the-author (report).
  const showEdit = !!post.can_edit && !!onEdit;
  const showDelete = !!post.can_delete && !!onDelete;
  const showReport = !!post.can_report && !!onReport;
  const [isReporting, setIsReporting] = useState(false);
  const [reportReason, setReportReason] = useState<string>(REPORT_REASONS[0].value);
  const [hasReported, setHasReported] = useState(false);
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);

  // Only confirm "Reported" once the request actually succeeds — a network
  // failure must leave the picker open (with the real error surfaced by the
  // caller's onReport), not silently claim success like an optimistic update.
  const submitReport = async () => {
    if (!onReport) return;
    setIsSubmittingReport(true);
    try {
      await onReport(post.id, reportReason);
      setHasReported(true);
      setIsReporting(false);
    } catch {
      // The caller (onReport) already surfaced the error to the user — leave
      // the picker open so they can retry instead of falsely confirming.
    } finally {
      setIsSubmittingReport(false);
    }
  };

  // Memoize formatted date
  const formattedDate = useMemo(() => {
    try {
      return formatDistanceToNow(new Date(post.created_at), { addSuffix: true });
    } catch {
      return 'recently';
    }
  }, [post.created_at]);

  return (
    <div
      className={`
        group bg-surface-2 rounded-lg shadow-md p-6
        ${post.is_first_post ? 'border-l-4 border-primary' : ''}
      `}
    >
      {/* Post Header */}
      <div className="flex items-start justify-between flex-wrap gap-2 mb-4">
        {/* Author Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
            <span className="text-xl font-bold text-leaf">
              {post.author.display_name?.[0] || post.author.username[0]}
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-ink">
                {post.author.display_name || post.author.username}
              </span>

              {post.author.trust_level && (
                <span className="px-2 py-0.5 bg-sky/10 text-ink text-xs rounded">
                  {post.author.trust_level}
                </span>
              )}

              {post.is_first_post && (
                <span className="px-2 py-0.5 bg-primary/10 text-ink text-xs rounded">
                  Original Post
                </span>
              )}
            </div>

            <div className="text-sm text-ink-3">
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

        {/* Actions (edit/delete) — gated on the backend capability flags AND the
            presence of a handler. Always visible on mobile; on desktop they fade
            in on hover AND on keyboard focus — opacity-0 keeps them tab-reachable,
            so a focus reveal is required for WCAG 2.4.7 (audit 2026-07-11 H20). */}
        {(showEdit || showDelete) && (
          <div className="flex gap-2 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
            {showEdit && (
              <button
                onClick={() => onEdit!(post)}
                className="min-h-11 px-3 py-1 text-sm text-sky hover:bg-sky/10 rounded inline-flex items-center"
                title="Edit post"
              >
                ✏️ Edit
              </button>
            )}
            {showDelete && (
              <button
                onClick={() => onDelete!(post)}
                className="min-h-11 px-3 py-1 text-sm text-error hover:bg-error/10 rounded inline-flex items-center"
                title="Delete post"
              >
                🗑️ Delete
              </button>
            )}
          </div>
        )}
      </div>

      {/* Post Content */}
      <div className="mb-4 break-words">
        <StreamFieldRenderer blocks={post.body} />
      </div>

      {/* Reactions — shown only when an onReact handler is provided (Phase 2 write UI). */}
      {onReact && (
        <div className="flex gap-3 pt-4 border-t border-line">
          {REACTION_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => onReact(post.id, type)}
              className="inline-flex items-center gap-1 min-h-11 px-3 py-1 bg-surface-2 hover:bg-surface-3 rounded-full text-sm transition-colors"
              aria-label={`React ${type}`}
              title={`React ${type}`}
            >
              <span>{getReactionEmoji(type)}</span>
              <span className="font-medium">{post.reaction_counts?.[type] ?? 0}</span>
            </button>
          ))}
        </div>
      )}

      {/* Report — never shown to the post's own author (can_report is the
          backend authority; mirrors can_edit/can_delete). */}
      {showReport && (
        <div className="flex justify-end pt-3 border-t border-line">
          {hasReported ? (
            <span className="text-sm text-ink-3 italic">Reported</span>
          ) : isReporting ? (
            <div className="flex items-center gap-2">
              <label htmlFor={`report-reason-${post.id}`} className="sr-only">
                Report reason
              </label>
              <select
                id={`report-reason-${post.id}`}
                value={reportReason}
                onChange={(e) => setReportReason(e.target.value)}
                className="text-sm border border-line rounded px-2 py-1 bg-surface-1"
              >
                {REPORT_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={submitReport}
                disabled={isSubmittingReport}
                className="min-h-11 px-3 py-1 text-sm text-error hover:bg-error/10 rounded disabled:opacity-50"
              >
                Submit
              </button>
              <button
                type="button"
                onClick={() => setIsReporting(false)}
                disabled={isSubmittingReport}
                className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-2 rounded disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsReporting(true)}
              className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:text-error hover:bg-error/10 rounded inline-flex items-center gap-1"
              title="Report post"
            >
              🚩 Report
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default memo(PostCard);
