import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import Button from '../ui/Button';
import LoadingSpinner from '../ui/LoadingSpinner';
import Timestamp from '../ui/Timestamp';
import { useAuth } from '../../contexts/AuthContext';
import {
  addBlogComment,
  fetchBlogComments,
  flagBlogComment,
  BLOG_COMMENT_MAX_LENGTH,
} from '../../services/blogCommentService';
import { ForumApiError } from '../../services/forumService';
import { logger } from '../../utils/logger';
import type { BlogComment, BlogCommentAuthor } from '../../types/blog';

/**
 * BlogCommentSection — reader comments under a blog article (todo 352).
 *
 * - Plain-text comments, one level of replies (the backend rejects deeper).
 * - Approved comments are public; the caller's OWN pending ones come back
 *   too, badged "awaiting moderation".
 * - `allowComments === false` (from the post payload) renders the closed
 *   note and never fetches; an undefined flag (older/list payloads) lets
 *   the endpoint's own 403 make the same call.
 * - Every async result is guarded by a request epoch bumped per post, so a
 *   late list or POST for the previous article never lands in this one.
 * - Notices go through ONE always-mounted `aria-live` region (sr-only when
 *   empty) — a conditionally rendered live region announces nothing.
 */

interface BlogCommentSectionProps {
  postId: number;
  /** `BlogPost.allow_comments`; undefined = unknown, the GET's 403 decides. */
  allowComments?: boolean;
  /** `BlogPost.comment_count` — the heading count until the list has loaded. */
  commentCount?: number;
}

const CLOSED_TEXT = 'Comments are closed on this post.';
const RATE_LIMITED_TEXT = "You're commenting too fast — try again in a minute.";
const LOAD_ERROR_TEXT = "Couldn't load comments.";
const PENDING_BADGE = 'Awaiting moderation — only you can see this';

const TEXTAREA_CLASS =
  'w-full rounded-md border border-line bg-surface-2/60 px-3 py-2 text-body text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-60';

function authorName(author: BlogCommentAuthor | null | undefined): string {
  return author?.display_name || author?.username || 'Anonymous';
}

/**
 * Notice text for a failed write. Branches on the HTTP STATUS, never the
 * message text (docs/rules/react.md): a 403 arrives as the server's detail,
 * a 429 as the envelope's generic line, a 400 as "field: text".
 */
function describeWriteError(err: unknown): string {
  if (err instanceof ForumApiError) {
    if (err.status === 429) return RATE_LIMITED_TEXT;
    if (err.status === 401) return 'Sign in to comment.';
    if (err.status === 400) {
      // The envelope flattens field errors to "<field>: <text>" joined by
      // "; ". The field names are ours, not something the reader typed, so
      // drop every recognised prefix, segment by segment — not just the
      // first — so a future multi-field error never leaks "parent: …".
      return err.message
        .split('; ')
        .map((segment) => segment.replace(/^(content|parent|detail): /, ''))
        .join('; ');
    }
    return err.message;
  }
  return err instanceof Error && err.message ? err.message : 'Something went wrong.';
}

/** Approved comments incl. replies — the same thing the server's `comment_count` counts. */
function approvedCount(comments: BlogComment[]): number {
  return comments.reduce(
    (n, c) => n + (c.is_approved ? 1 : 0) + c.replies.filter((r) => r.is_approved).length,
    0
  );
}

interface CommentBodyProps {
  comment: BlogComment;
}

/** Author line + plain-text body — shared by top-level comments and replies. */
function CommentBody({ comment }: CommentBodyProps) {
  return (
    <>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-body-sm font-semibold text-ink">{authorName(comment.author)}</span>
        <Timestamp
          iso={comment.created_at}
          prefix="Posted"
          className="font-mono text-micro text-ink-3"
        />
        {!comment.is_approved && (
          <span className="rounded-pill border border-line bg-surface-2/60 px-2 py-0.5 text-micro text-ink-2">
            {PENDING_BADGE}
          </span>
        )}
      </div>
      {/* PLAIN TEXT by contract — never HTML, never dangerouslySetInnerHTML. */}
      <p className="whitespace-pre-wrap break-words text-body leading-relaxed text-ink">
        {comment.content}
      </p>
    </>
  );
}

export default function BlogCommentSection({
  postId,
  allowComments,
  commentCount,
}: BlogCommentSectionProps) {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  // `isAuthenticated` is `!!user` and does not change across an account
  // swap; the list depends on WHO is asking (own pending comments), so key
  // the load on the identity itself.
  const userId = user?.id;

  const [comments, setComments] = useState<BlogComment[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [closedByServer, setClosedByServer] = useState(false);

  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyDraft, setReplyDraft] = useState('');
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [flaggedIds, setFlaggedIds] = useState<number[]>([]);
  const [flaggingId, setFlaggingId] = useState<number | null>(null);

  // Monotonic request epoch, bumped by the per-post effect below. A result
  // — list, POST, flag, success or failure — lands only if no newer post has
  // been loaded since the request was issued. Read in handlers/effects
  // only, never during render (react-hooks/refs).
  const epochRef = useRef(0);
  // Stable so the effect cleanup can invalidate without reading the ref
  // inside the cleanup body (react-hooks/exhaustive-deps' node-ref heuristic
  // cannot tell a counter ref from a DOM ref).
  const invalidateEpoch = useCallback(() => {
    epochRef.current++;
  }, []);

  const closed = allowComments === false || closedByServer;

  const load = useCallback(
    (epoch: number) => {
      setLoading(true);
      setLoadError(null);
      fetchBlogComments(postId).then(
        (list) => {
          if (epoch !== epochRef.current) return;
          setComments(list);
          setLoaded(true);
          setLoading(false);
        },
        (err: unknown) => {
          if (epoch !== epochRef.current) return;
          if (err instanceof ForumApiError && err.status === 403) {
            // The post has comments disabled — the server's word beats an
            // absent/stale `allow_comments` on the page payload.
            setClosedByServer(true);
          } else {
            logger.error('Error loading blog comments', {
              component: 'BlogCommentSection',
              error: err,
              context: { postId },
            });
            setLoadError(LOAD_ERROR_TEXT);
          }
          setLoading(false);
        }
      );
    },
    [postId]
  );

  useEffect(() => {
    const epoch = ++epochRef.current;
    // Everything below belongs to the post (and identity) we are leaving.
    setComments([]);
    setLoaded(false);
    setLoading(false);
    setLoadError(null);
    setClosedByServer(false);
    setNotice(null);
    setDraft('');
    setSubmitting(false);
    setReplyingTo(null);
    setReplyDraft('');
    setReplySubmitting(false);
    setFlaggedIds([]);
    setFlaggingId(null);
    if (allowComments === false) return; // closed: no request at all
    load(epoch);
    // Unmount (or a deps change) invalidates every in-flight result: a
    // response landing after this section is gone must not call setState.
    return invalidateEpoch;
  }, [postId, userId, allowComments, load, invalidateEpoch]);

  // Retry is only offered once the previous load has SETTLED with an error,
  // so no other load for this post is in flight and the current epoch is
  // safe to reuse (bumping it would orphan an in-flight submit's result).
  // A submit that lands after the refreshed list already contains it is
  // deduped by id in `upsert` below.
  const retry = () => load(epochRef.current);

  // Append-or-replace by id: a refreshed list and an in-flight write can
  // both deliver the same comment; React keys are comment ids.
  const upsert = (list: BlogComment[], item: BlogComment): BlogComment[] =>
    list.some((c) => c.id === item.id)
      ? list.map((c) => (c.id === item.id ? item : c))
      : [...list, item];

  const isOwn = (comment: BlogComment): boolean => {
    if (!user) return false;
    const author = comment.author;
    if (author?.id != null) return author.id === user.id;
    return !!author?.username && author.username === user.username;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || submitting) return;
    const epoch = epochRef.current;
    setSubmitting(true);
    setNotice(null);
    try {
      const created = await addBlogComment(postId, { content });
      if (epoch !== epochRef.current) return;
      setComments((prev) => upsert(prev, created));
      setDraft('');
      setNotice(
        created.is_approved
          ? 'Comment posted.'
          : 'Your comment is awaiting moderation — only you can see it until it is approved.'
      );
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setNotice(describeWriteError(err));
    } finally {
      if (epoch === epochRef.current) setSubmitting(false);
    }
  };

  const openReply = (commentId: number) => {
    // ONE inline reply composer at a time: opening another closes this one.
    setReplyingTo(commentId);
    setReplyDraft('');
    setNotice(null);
  };

  const handleReplySubmit = async (event: FormEvent<HTMLFormElement>, parentId: number) => {
    event.preventDefault();
    const content = replyDraft.trim();
    if (!content || replySubmitting) return;
    const epoch = epochRef.current;
    setReplySubmitting(true);
    setNotice(null);
    try {
      const created = await addBlogComment(postId, { content, parent: parentId });
      if (epoch !== epochRef.current) return;
      setComments((prev) =>
        prev.map((c) => (c.id === parentId ? { ...c, replies: upsert(c.replies, created) } : c))
      );
      setReplyingTo(null);
      setReplyDraft('');
      setNotice(
        created.is_approved
          ? 'Reply posted.'
          : 'Your reply is awaiting moderation — only you can see it until it is approved.'
      );
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setNotice(describeWriteError(err));
    } finally {
      if (epoch === epochRef.current) setReplySubmitting(false);
    }
  };

  const handleFlag = async (commentId: number) => {
    if (flaggingId !== null) return;
    const epoch = epochRef.current;
    setFlaggingId(commentId);
    setNotice(null);
    try {
      const result = await flagBlogComment(commentId);
      if (epoch !== epochRef.current) return;
      setFlaggedIds((prev) => (prev.includes(commentId) ? prev : [...prev, commentId]));
      setNotice(result?.detail || 'Comment flagged for review.');
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setNotice(describeWriteError(err));
    } finally {
      if (epoch === epochRef.current) setFlaggingId(null);
    }
  };

  const count = loaded ? approvedCount(comments) : (commentCount ?? 0);
  const canWrite = !authLoading && isAuthenticated;
  const showSignIn = !authLoading && !isAuthenticated;
  // A write outcome always wins the live region: the composer stays usable
  // while the list is broken, and "awaiting moderation" / 429 must never be
  // shadowed by a stale "Couldn't load comments." (review finding).
  const liveText = notice ?? loadError;

  const renderActions = (comment: BlogComment) => {
    if (!canWrite) return null;
    const own = isOwn(comment);
    // Depth is one level and a pending comment cannot be replied to yet —
    // only an approved top-level comment gets a Reply control.
    const canReply = comment.parent === null && comment.is_approved;
    const canFlag = !own && comment.is_approved;
    if (!canReply && !canFlag) return null;
    const flagged = flaggedIds.includes(comment.id);
    return (
      <div className="flex flex-wrap items-center gap-1">
        {canReply && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-11"
            onClick={() => openReply(comment.id)}
          >
            Reply
          </Button>
        )}
        {canFlag && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-11"
            disabled={flagged || flaggingId !== null}
            aria-pressed={flagged}
            onClick={() => void handleFlag(comment.id)}
          >
            {flagged ? 'Flagged' : 'Flag'}
          </Button>
        )}
      </div>
    );
  };

  const renderReplyComposer = (comment: BlogComment) => {
    const id = `blog-reply-composer-${comment.id}`;
    return (
      <form
        onSubmit={(event) => void handleReplySubmit(event, comment.id)}
        className="mt-1 flex flex-col gap-2"
      >
        <label htmlFor={id} className="text-meta font-semibold text-ink-2">
          Reply to {authorName(comment.author)}
        </label>
        <textarea
          id={id}
          autoFocus
          value={replyDraft}
          onChange={(event) => setReplyDraft(event.target.value)}
          maxLength={BLOG_COMMENT_MAX_LENGTH}
          rows={3}
          disabled={replySubmitting}
          className={TEXTAREA_CLASS}
        />
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-micro text-ink-3">
            {`${replyDraft.length}/${BLOG_COMMENT_MAX_LENGTH}`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-11"
              disabled={replySubmitting}
              onClick={() => {
                setReplyingTo(null);
                setReplyDraft('');
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              className="min-h-11"
              loading={replySubmitting}
              loadingText="Posting…"
              disabled={replySubmitting || !replyDraft.trim()}
            >
              Post reply
            </Button>
          </div>
        </div>
      </form>
    );
  };

  return (
    <section
      aria-labelledby="blog-comments-heading"
      className="mx-auto flex w-full max-w-[70ch] flex-col gap-5 border-t border-line pt-8"
    >
      <h2 id="blog-comments-heading" className="text-lead font-semibold text-ink">
        Comments ({count})
      </h2>

      {/* Persistent live region: ALWAYS mounted (no conditional ancestor),
          text swaps in, visually collapsed when empty. Carries load errors
          and every write/flag outcome. */}
      <div
        aria-live="polite"
        aria-atomic="true"
        data-testid="blog-comments-notice"
        className={
          liveText
            ? 'rounded-md border border-line bg-surface-2 px-4 py-3 text-body-sm text-ink-2'
            : 'sr-only'
        }
      >
        {liveText}
      </div>

      {closed ? (
        <p className="text-body-sm text-ink-3">{CLOSED_TEXT}</p>
      ) : (
        <>
          {loadError && (
            <div>
              <Button variant="outline" size="sm" className="min-h-11" onClick={retry}>
                Retry
              </Button>
            </div>
          )}

          {loading && <LoadingSpinner label="Loading comments…" className="py-6" />}

          {loaded && comments.length === 0 && (
            <p className="text-body-sm text-ink-3">No comments yet.</p>
          )}

          {comments.length > 0 && (
            <ol aria-label="Comments" className="flex flex-col gap-4">
              {comments.map((comment) => (
                <li
                  key={comment.id}
                  id={`comment-${comment.id}`}
                  className="flex flex-col gap-2 rounded-md border border-line bg-surface-2/40 p-4"
                >
                  <CommentBody comment={comment} />
                  {renderActions(comment)}
                  {replyingTo === comment.id && renderReplyComposer(comment)}
                  {comment.replies.length > 0 && (
                    <ol
                      aria-label="Replies"
                      className="mt-1 flex flex-col gap-3 border-l-2 border-line pl-4"
                    >
                      {comment.replies.map((reply) => (
                        <li
                          key={reply.id}
                          id={`comment-${reply.id}`}
                          className="flex flex-col gap-2"
                        >
                          <CommentBody comment={reply} />
                          {renderActions(reply)}
                        </li>
                      ))}
                    </ol>
                  )}
                </li>
              ))}
            </ol>
          )}

          {canWrite && (
            <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-2">
              <label
                htmlFor="blog-comment-composer"
                className="text-body-sm font-semibold text-ink"
              >
                Add a comment
              </label>
              <textarea
                id="blog-comment-composer"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={BLOG_COMMENT_MAX_LENGTH}
                rows={4}
                disabled={submitting}
                placeholder="Share your experience with this plant…"
                className={TEXTAREA_CLASS}
              />
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-micro text-ink-3">
                  {`${draft.length}/${BLOG_COMMENT_MAX_LENGTH}`}
                </span>
                <Button
                  type="submit"
                  size="sm"
                  className="min-h-11"
                  loading={submitting}
                  loadingText="Posting…"
                  disabled={submitting || !draft.trim()}
                >
                  Post comment
                </Button>
              </div>
            </form>
          )}

          {showSignIn && (
            <p className="text-body-sm text-ink-2">
              <Link
                to="/login"
                className="font-semibold text-primary underline-offset-2 hover:underline"
              >
                Sign in to comment
              </Link>
            </p>
          )}
        </>
      )}
    </section>
  );
}
