import { memo, useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Flag, Link2, Pencil, SmilePlus, Trash2, UserCheck, UserX } from 'lucide-react';
import StreamFieldRenderer from '../StreamFieldRenderer';
import EditHistoryDialog from './EditHistoryDialog';
import Timestamp from '../ui/Timestamp';
import Card from '../ui/Card';
import { POST_CARD_PADDING } from '../ui/dimensions';
import Avatar from '../ui/Avatar';
import { userProfilePath } from '../../utils/forumUrls';
import { DELETED_AUTHOR_USERNAME, TRUST_LEVEL_LABELS } from '../../utils/forumAuthor';
import { REACTION_TYPES } from '../../utils/forumReactions';
import { specimenAvatar } from '../../utils/forumAvatars';
import type { Post } from '@/types';

interface PostCardProps {
  post: Post;
  onEdit?: (post: Post) => void;
  onDelete?: (post: Post) => void;
  onReact?: (postId: string, reactionType: string) => void;
  onReport?: (postId: string, reason: string) => Promise<void>;
  /** Block/unblock this post's author (todo 284/M9). Same triple-gate
   * discipline as onReport: visibility is `post.can_block && handler`. */
  onBlock?: (username: string) => Promise<void>;
  onUnblock?: (username: string) => Promise<void>;
  /** Whether this post is the topic's accepted answer (audit H6). */
  isSolution?: boolean;
  /**
   * Accept/clear this post as the answer. Passed ONLY when the viewer may do
   * so (the thread page gates on the topic's `can_mark_solution`), so its mere
   * presence is the affordance — same contract as onEdit/onDelete. Never
   * offered on the opening post: the question is not its own answer, and the
   * backend rejects it with a 422.
   */
  onToggleSolution?: (post: Post) => void;
}

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
 * PostCard Component — a Canopy gradient card.
 *
 * Displays a single post in a thread: author info, content, reactions, and
 * edit/delete options. The accepted answer is marked with a secondary ring
 * (applied alongside the border tint) plus a text label — never colour alone.
 */
function PostCard({
  post,
  onEdit,
  onDelete,
  onReact,
  onReport,
  onBlock,
  onUnblock,
  isSolution = false,
  onToggleSolution,
}: PostCardProps) {
  // Edit/delete/report/block visibility is driven by the backend capability
  // flags (PostSerializer.can_edit/can_delete/can_report/can_block) — the
  // only authority on author-or-mod (edit/delete) and not-the-author
  // (report/block).
  const showEdit = !!post.can_edit && !!onEdit;
  const showDelete = !!post.can_delete && !!onDelete;
  const showReport = !!post.can_report && !!onReport;
  const showBlockAction = !!post.can_block && !!(onBlock || onUnblock);
  const [isReporting, setIsReporting] = useState(false);
  const [reportReason, setReportReason] = useState<string>(REPORT_REASONS[0].value);
  const [hasReported, setHasReported] = useState(false);
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [isBlockActionPending, setIsBlockActionPending] = useState(false);
  // Local-only: reveals a collapsed (is_blocked) post without a refetch — the
  // real author/body are already in the payload (server doesn't redact).
  // Deliberately NOT tracking a local "just blocked/unblocked" flag: blocking
  // an author can affect every OTHER post by them on the page too, so the
  // handler is called as-is and the parent's refetch is the only source of
  // truth for post.is_blocked (todo 284/M9).
  const [revealed, setRevealed] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  // Stable identity: EditHistoryDialog's focus effect depends on [open,
  // onClose], so a fresh inline closure would tear it down and re-run on every
  // unrelated PostCard re-render (report flow, reactions, copy-link),
  // yanking a keyboard user's focus back to Close mid-review.
  const closeHistory = useCallback(() => setShowHistory(false), []);
  // When the clipboard API is unavailable, reveal the URL inline for manual copy
  // instead of a native window.prompt (audit M24).
  const [copyFallbackUrl, setCopyFallbackUrl] = useState<string | null>(null);
  const [showReactionPicker, setShowReactionPicker] = useState(false);
  const nonZeroReactions = REACTION_TYPES.filter((t) => (post.reaction_counts?.[t] ?? 0) > 0);
  // Author name + avatar link to the public profile (todo 257 H7) — but a
  // deleted author ([deleted] sentinel) has no profile, so render plain.
  const authorHref =
    post.author.username === DELETED_AUTHOR_USERNAME ? null : userProfilePath(post.author.username);

  // Same non-optimistic contract as submitReport: call the handler and let
  // the parent's refetch update post.is_blocked. Guards against a double
  // click while the request is in flight; does not fabricate success.
  const handleBlock = async () => {
    if (!onBlock) return;
    setIsBlockActionPending(true);
    try {
      await onBlock(post.author.username);
    } finally {
      setIsBlockActionPending(false);
    }
  };

  const handleUnblock = async () => {
    if (!onUnblock) return;
    setIsBlockActionPending(true);
    try {
      await onUnblock(post.author.username);
    } finally {
      setIsBlockActionPending(false);
    }
  };

  // Collapsed placeholder for a blocked author's post (todo 284/M9) — COLLAPSE,
  // not HIDE: removing a reply mid-thread would break numbering/reply-count
  // continuity. The real content is already in `post` (server doesn't
  // redact); "Show anyway" is a local, no-refetch reveal.
  if (post.is_blocked && !revealed) {
    return (
      <Card className={POST_CARD_PADDING}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-sm text-ink-3">
            You've blocked{' '}
            <span className="font-medium text-ink">
              {post.author.display_name || post.author.username}
            </span>
            .
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setRevealed(true)}
              className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-3 rounded-pill"
            >
              Show anyway
            </button>
            {onUnblock && (
              <button
                type="button"
                onClick={handleUnblock}
                disabled={isBlockActionPending}
                className="min-h-11 px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-pill inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <UserCheck className="h-3.5 w-3.5" aria-hidden="true" /> Unblock
              </button>
            )}
          </div>
        </div>
      </Card>
    );
  }

  const handleCopyLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}#post-${post.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedLink(true);
      setCopyFallbackUrl(null);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      // Clipboard API unavailable (http, old browser) — surface the URL inline.
      setCopyFallbackUrl(url);
    }
  };

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

  return (
    <Card
      data-testid="post-card"
      className={`group ${POST_CARD_PADDING} ${isSolution ? 'border-secondary/60 ring-1 ring-secondary/40' : ''}`}
    >
      {/* Accepted-answer banner (audit H6). A visible label, not colour alone —
          the ring carries no meaning for a colour-blind reader and none at
          all for a screen reader. */}
      {isSolution && (
        <p className="gt-label mb-4 inline-flex items-center gap-1.5 text-secondary">
          <Check className="h-3.5 w-3.5" aria-hidden="true" /> Accepted answer
        </p>
      )}

      {/* Post Header */}
      <div className="flex items-start justify-between flex-wrap gap-2 mb-4">
        {/* Author Info */}
        <div className="flex items-center gap-3">
          {/* Decorative (alt="") — the author's name sits right beside it, so
              announcing the image would only repeat it. */}
          <Avatar
            src={post.author.avatar || specimenAvatar(post.author.username)}
            alt=""
            size="md"
          />

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              {authorHref ? (
                <Link
                  to={authorHref}
                  className="font-semibold text-ink hover:text-primary hover:underline"
                >
                  {post.author.display_name || post.author.username}
                </Link>
              ) : (
                <span className="font-semibold text-ink">
                  {post.author.display_name || post.author.username}
                </span>
              )}

              {typeof post.author.trust_level === 'number' && post.author.trust_level >= 1 && (
                <span className="gt-label rounded-full border border-sky/40 px-2 py-0.5 text-sky">
                  {TRUST_LEVEL_LABELS[post.author.trust_level] ??
                    `Level ${post.author.trust_level}`}
                </span>
              )}

              {post.is_first_post && (
                <span className="gt-label rounded-full border border-primary/40 px-2 py-0.5 text-primary">
                  Original Post
                </span>
              )}
            </div>

            <div className="gt-label mt-0.5 normal-case tracking-normal">
              <Timestamp iso={post.created_at} prefix="Posted" />

              {post.edited_at && (
                <>
                  <span className="mx-1">·</span>
                  {/* The stamp is the entry point to the history it describes
                      (todo 282). Revisions were always stored; until now
                      nothing surfaced them outside the Wagtail admin. */}
                  <button
                    type="button"
                    onClick={() => setShowHistory(true)}
                    className="min-h-11 underline decoration-dotted underline-offset-2 hover:text-primary"
                  >
                    Edited <Timestamp iso={post.edited_at} />
                    {post.edited_by &&
                      ` by ${post.edited_by.display_name || post.edited_by.username}`}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Actions — copy-link is available to every post; edit/delete are gated
            on the backend capability flags AND the presence of a handler. Always
            visible on mobile; on desktop they fade in on hover AND on keyboard
            focus — opacity-0 keeps them tab-reachable, so a focus reveal is
            required for WCAG 2.4.7 (audit 2026-07-11 H20). */}
        <div className="flex gap-1 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
          <button
            onClick={handleCopyLink}
            className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-3 rounded-pill inline-flex items-center gap-1.5"
            title="Copy link to this post"
            aria-label="Copy link to this post"
          >
            {copiedLink ? (
              <>
                <Check className="h-3.5 w-3.5" aria-hidden="true" /> Copied
              </>
            ) : (
              <>
                <Link2 className="h-3.5 w-3.5" aria-hidden="true" /> Copy link
              </>
            )}
          </button>
          {onToggleSolution && (
            <button
              onClick={() => onToggleSolution(post)}
              className="min-h-11 px-3 py-1 text-sm text-ink-2 hover:bg-secondary/10 rounded-pill inline-flex items-center gap-1.5"
              // aria-pressed makes this a toggle to assistive tech, so the
              // current state is announced rather than inferred from the label.
              aria-pressed={isSolution}
              title={isSolution ? 'Remove the accepted answer' : 'Mark this reply as the answer'}
            >
              <Check className="h-3.5 w-3.5" aria-hidden="true" />{' '}
              {isSolution ? 'Accepted' : 'Mark as answer'}
            </button>
          )}
          {showEdit && (
            <button
              onClick={() => onEdit!(post)}
              className="min-h-11 px-3 py-1 text-sm text-sky hover:bg-sky/10 rounded-pill inline-flex items-center gap-1.5"
              title="Edit post"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit
            </button>
          )}
          {showDelete && (
            <button
              onClick={() => onDelete!(post)}
              className="min-h-11 px-3 py-1 text-sm text-error hover:bg-error/10 rounded-pill inline-flex items-center gap-1.5"
              title="Delete post"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" /> Delete
            </button>
          )}
        </div>
      </div>

      {/* Clipboard-unavailable fallback: the URL, selectable for manual copy. */}
      {copyFallbackUrl && (
        <div className="mb-4">
          <label htmlFor={`copy-link-${post.id}`} className="sr-only">
            Post link (copy manually)
          </label>
          <input
            id={`copy-link-${post.id}`}
            type="text"
            readOnly
            value={copyFallbackUrl}
            onFocus={(e) => e.currentTarget.select()}
            className="w-full rounded-sm border border-line-2 bg-surface px-3 py-2 text-sm text-ink"
          />
        </div>
      )}

      {/* Post Content */}
      <div className="mb-4 break-words leading-relaxed">
        <StreamFieldRenderer blocks={post.body} mentionHighlight />
      </div>

      {(onReact || nonZeroReactions.length > 0) && (
        <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-line">
          {nonZeroReactions.map((type) => {
            // Whether the CURRENT user has this reaction active (M23). Only
            // meaningful on the interactive (authed) buttons; the anon display
            // buttons omit aria-pressed (they aren't toggles).
            const isReacted = !!post.reacted?.includes(type);
            return (
              <button
                key={type}
                type="button"
                onClick={onReact ? () => onReact(post.id, type) : undefined}
                disabled={!onReact}
                aria-pressed={onReact ? isReacted : undefined}
                className={`inline-flex items-center gap-1.5 min-h-11 px-3 py-1 rounded-full border text-sm transition-colors disabled:cursor-default ${
                  isReacted
                    ? 'border-secondary/60 bg-secondary/15 text-ink'
                    : 'border-line bg-transparent hover:border-line-2 hover:bg-surface-3 disabled:hover:bg-transparent'
                }`}
                aria-label={onReact ? `React ${type}` : `${post.reaction_counts?.[type]} ${type}`}
                title={onReact ? `React ${type}` : type}
              >
                <span aria-hidden="true">{getReactionEmoji(type)}</span>
                <span className="font-mono text-xs font-medium">
                  {post.reaction_counts?.[type]}
                </span>
              </button>
            );
          })}
          {onReact && !showReactionPicker && (
            <button
              type="button"
              onClick={() => setShowReactionPicker(true)}
              className="inline-flex items-center justify-center min-h-11 min-w-11 px-3 py-1 text-ink-3 border border-transparent hover:border-line hover:bg-surface-3 rounded-full text-sm transition-colors"
              aria-label="Add reaction"
              title="Add reaction"
            >
              <SmilePlus className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          {onReact &&
            showReactionPicker &&
            REACTION_TYPES.filter((t) => !nonZeroReactions.includes(t)).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => {
                  onReact(post.id, type);
                  setShowReactionPicker(false);
                }}
                aria-pressed={false}
                className="inline-flex items-center min-h-11 px-3 py-1 border border-line bg-transparent hover:border-line-2 hover:bg-surface-3 rounded-full text-sm transition-colors"
                aria-label={`React ${type}`}
                title={`React ${type}`}
              >
                <span aria-hidden="true">{getReactionEmoji(type)}</span>
              </button>
            ))}
        </div>
      )}

      {/* Trust & safety row — Block/Unblock and Report never show for the
          post's own author (can_block/can_report are the backend authority;
          mirrors can_edit/can_delete). */}
      {(showBlockAction || showReport) && (
        <div className="flex justify-end items-center gap-2 pt-3 border-t border-line">
          {showBlockAction &&
            (post.is_blocked
              ? onUnblock && (
                  <button
                    type="button"
                    onClick={handleUnblock}
                    disabled={isBlockActionPending}
                    className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-3 rounded-pill inline-flex items-center gap-1.5 disabled:opacity-50"
                    title="Unblock user"
                  >
                    <UserCheck className="h-3.5 w-3.5" aria-hidden="true" /> Unblock
                  </button>
                )
              : onBlock && (
                  <button
                    type="button"
                    onClick={handleBlock}
                    disabled={isBlockActionPending}
                    className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:text-error hover:bg-error/10 rounded-pill inline-flex items-center gap-1.5 disabled:opacity-50"
                    title="Block user"
                  >
                    <UserX className="h-3.5 w-3.5" aria-hidden="true" /> Block
                  </button>
                ))}
          {showReport &&
            (hasReported ? (
              <span className="gt-label italic">Reported</span>
            ) : isReporting ? (
              <div className="flex items-center gap-2">
                <label htmlFor={`report-reason-${post.id}`} className="sr-only">
                  Report reason
                </label>
                <select
                  id={`report-reason-${post.id}`}
                  value={reportReason}
                  onChange={(e) => setReportReason(e.target.value)}
                  className="text-sm border border-line rounded-sm px-2 py-1 bg-surface"
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
                  className="min-h-11 px-3 py-1 text-sm text-error hover:bg-error/10 rounded-pill disabled:opacity-50"
                >
                  Submit
                </button>
                <button
                  type="button"
                  onClick={() => setIsReporting(false)}
                  disabled={isSubmittingReport}
                  className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-2 rounded-pill disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsReporting(true)}
                className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:text-error hover:bg-error/10 rounded-pill inline-flex items-center gap-1.5"
                title="Report post"
              >
                <Flag className="h-3.5 w-3.5" aria-hidden="true" /> Report
              </button>
            ))}
        </div>
      )}

      <EditHistoryDialog open={showHistory} postId={post.id} onClose={closeHistory} />
    </Card>
  );
}

export default memo(PostCard);
