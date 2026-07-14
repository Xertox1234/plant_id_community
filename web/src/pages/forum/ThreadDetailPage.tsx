import { useState, useEffect, useCallback, useRef, FormEvent } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  fetchThread,
  fetchPosts,
  createPost,
  updatePost,
  deletePost,
  toggleReaction,
  reportPost,
  subscribeToTopic,
  unsubscribeFromTopic,
} from '../../services/forumService';
import { parseLeadingId } from '../../utils/forumUrls';
import { bodyBlocksToHtml } from '../../utils/forumBody';
import PostCard from '../../components/forum/PostCard';
import TipTapEditor from '../../components/forum/TipTapEditor';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';
import type { Thread, Post } from '@/types';
import type { PaginatedResponse } from '@/types/forum';

/** Strip tags + whitespace to detect an effectively-empty rich-text body. */
function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>/g, '').trim() === '';
}

// Posts are ordered oldest-first, so a brand-new reply is the NEWEST post and lands
// on the last cursor page. Reload every page through to the end after posting so the
// author actually sees their reply (refetching only page 1 would show the oldest 20).
const MAX_REFRESH_PAGES = 50; // safety bound for pathologically long threads
async function collectAllPosts(threadId: number): Promise<{ items: Post[]; next: string | null }> {
  const items: Post[] = [];
  let cursor: string | undefined;
  let next: string | null = null;
  for (let i = 0; i < MAX_REFRESH_PAGES; i++) {
    const page = await fetchPosts(cursor ? { thread: threadId, cursor } : { thread: threadId });
    items.push(...page.items);
    next = page.meta.next ?? null;
    if (!next) break;
    cursor = next;
  }
  return { items, next };
}

/**
 * ThreadDetailPage Component
 *
 * Displays a thread with its posts and the write UI (reply, edit, delete, react).
 * Route: /forum/:categorySlug/:threadSlug
 */
export default function ThreadDetailPage() {
  const { categorySlug, threadSlug } = useParams<{ categorySlug: string; threadSlug: string }>();
  const { isAuthenticated } = useAuth();

  // The route param is a hybrid "id-slug"; lookups use the leading topic id.
  const topicId = parseLeadingId(threadSlug);

  const [thread, setThread] = useState<Thread | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Cursor pagination state
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  // totalPosts is seeded from thread.post_count (meta.count is hardcoded 0 by the service)
  const [totalPosts, setTotalPosts] = useState<number>(0);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);

  // Write-path state
  const [replyBody, setReplyBody] = useState<string>('');
  const [replySubmitting, setReplySubmitting] = useState<boolean>(false);
  // TipTap's `content` is init-only, so resetting replyBody won't clear the editor;
  // bumping this key remounts a fresh (empty) composer after a successful reply.
  const [composerKey, setComposerKey] = useState<number>(0);
  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState<string>('');
  const [editSubmitting, setEditSubmitting] = useState<boolean>(false);
  const [subscribing, setSubscribing] = useState<boolean>(false);
  // A transient banner for write errors + moderation outcomes.
  const [notice, setNotice] = useState<string | null>(null);

  // Tracks the topic currently on screen. handleToggleSubscription reads this
  // after its await to detect that the user navigated to a different thread
  // while its request was in flight, so a late success/failure for thread A
  // can't clobber thread B's displayed state.
  const currentTopicIdRef = useRef<number | null>(null);

  // Load thread and initial posts
  useEffect(() => {
    // Refs must not be written during render (react-hooks/refs) — this
    // effect already re-runs on every topicId change, so it doubles as the
    // sync point.
    currentTopicIdRef.current = topicId;
    // A subscribe/unsubscribe request still in flight for the PREVIOUS
    // thread must not leave this thread's Follow button stuck loading —
    // reset unconditionally on every navigation (handleToggleSubscription's
    // own finally guards against that stale request re-enabling it late).
    setSubscribing(false);

    const loadData = async () => {
      if (topicId == null) {
        setError('Invalid thread URL');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const [threadData, postsData] = (await Promise.all([
          fetchThread(topicId),
          fetchPosts({ thread: topicId }),
        ])) as [Thread, PaginatedResponse<Post>];

        setThread(threadData);
        setPosts(postsData.items);
        // meta.count is hardcoded 0 by the service; seed from thread.post_count instead
        setTotalPosts(threadData.post_count ?? 0);
        setNextCursor(postsData.meta.next ?? null);
      } catch (err) {
        logger.error('Error loading thread data', {
          component: 'ThreadDetailPage',
          error: err,
          context: { categorySlug, threadSlug },
        });
        setError(err instanceof Error ? err.message : 'Failed to load thread');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [topicId, threadSlug, categorySlug]);

  // Load more posts (cursor pagination)
  const handleLoadMore = useCallback(async () => {
    if (topicId == null || !nextCursor) return;

    try {
      setLoadingMore(true);
      const postsData = (await fetchPosts({
        thread: topicId,
        cursor: nextCursor,
      })) as PaginatedResponse<Post>;

      setPosts((prev) => [...prev, ...postsData.items]);
      setNextCursor(postsData.meta.next ?? null);
    } catch (err) {
      logger.error('Error loading more posts', {
        component: 'ThreadDetailPage',
        error: err,
        context: { threadId: thread?.id },
      });
      setNotice(
        `Failed to load more posts: ${err instanceof Error ? err.message : 'Unknown error'}`
      );
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, topicId, thread?.id]);

  // Submit a reply. A published reply is refetched into the list; a pending reply
  // (untrusted author) is unlisted, so we only confirm it was submitted.
  const handleReply = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (topicId == null || isBlankHtml(replyBody)) return;
      try {
        setReplySubmitting(true);
        setNotice(null);
        const res = await createPost({ thread: topicId, content: replyBody });
        setReplyBody('');
        setComposerKey((k) => k + 1); // remount the editor so it visibly clears
        if (res.status === 'published') {
          const refreshed = await collectAllPosts(topicId);
          setPosts(refreshed.items);
          setNextCursor(refreshed.next);
          setTotalPosts((n) => n + 1);
        } else {
          setNotice('Your reply was submitted and is awaiting moderation.');
        }
      } catch (err) {
        logger.error('Error posting reply', {
          component: 'ThreadDetailPage',
          error: err,
          context: { threadId: topicId },
        });
        setNotice(err instanceof Error ? err.message : 'Failed to post reply');
      } finally {
        setReplySubmitting(false);
      }
    },
    [topicId, replyBody]
  );

  const handleReact = useCallback(async (postId: string, reactionType: string) => {
    try {
      const result = await toggleReaction(postId, reactionType);
      setPosts((prev) =>
        prev.map((p) => (p.id === postId ? { ...p, reaction_counts: result.reaction_counts } : p))
      );
    } catch (err) {
      logger.error('Error toggling reaction', {
        component: 'ThreadDetailPage',
        error: err,
        context: { postId, reactionType },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to react');
    }
  }, []);

  const handleToggleSubscription = useCallback(async () => {
    if (!thread || topicId == null) return;
    const requestTopicId = topicId;
    const wasSubscribed = thread.is_subscribed ?? false;
    setSubscribing(true);
    // Optimistic — reads instantly as the new state; rolled back on failure below.
    setThread((prev) => (prev ? { ...prev, is_subscribed: !wasSubscribed } : prev));
    try {
      if (wasSubscribed) {
        await unsubscribeFromTopic(requestTopicId);
      } else {
        await subscribeToTopic(requestTopicId);
      }
    } catch (err) {
      logger.error('Error toggling topic subscription', {
        component: 'ThreadDetailPage',
        error: err,
        context: { threadId: thread.id },
      });
      // Only touch state if still viewing the thread this request was for —
      // the user may have navigated to a different thread while it was in
      // flight, and a late failure here must not roll back or flag THAT
      // thread's subscription state (todo 253 slice 3 review finding).
      if (currentTopicIdRef.current === requestTopicId) {
        setThread((prev) => (prev ? { ...prev, is_subscribed: wasSubscribed } : prev));
        setNotice(err instanceof Error ? err.message : 'Failed to update subscription');
      }
    } finally {
      if (currentTopicIdRef.current === requestTopicId) {
        setSubscribing(false);
      }
    }
  }, [thread, topicId]);

  const handleReport = useCallback(async (postId: string, reason: string) => {
    try {
      await reportPost(postId, reason);
    } catch (err) {
      logger.error('Error reporting post', {
        component: 'ThreadDetailPage',
        error: err,
        context: { postId, reason },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to report post');
      // Rethrow so PostCard's picker stays open for a retry instead of
      // showing a false "Reported" confirmation (unlike handleReact, whose
      // confirmation is driven by reaction_counts and never lies on failure).
      throw err;
    }
  }, []);

  const handleDelete = useCallback(async (post: Post) => {
    if (!window.confirm('Delete this post? This cannot be undone.')) return;
    try {
      await deletePost(post.id);
      setPosts((prev) => prev.filter((p) => p.id !== post.id));
      setTotalPosts((n) => Math.max(0, n - 1));
    } catch (err) {
      logger.error('Error deleting post', {
        component: 'ThreadDetailPage',
        error: err,
        context: { postId: post.id },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to delete post');
    }
  }, []);

  const handleEdit = useCallback((post: Post) => {
    setEditingPostId(post.id);
    setEditBody(bodyBlocksToHtml(post.body));
  }, []);

  const handleEditSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (editingPostId == null || isBlankHtml(editBody)) return;
      try {
        setEditSubmitting(true);
        setNotice(null);
        const res = await updatePost(editingPostId, { content: editBody });
        setPosts((prev) => prev.map((p) => (p.id === editingPostId ? res.post : p)));
        if (res.status === 'pending') {
          setNotice('Your edit was submitted and is awaiting moderation.');
        }
        setEditingPostId(null);
        setEditBody('');
      } catch (err) {
        logger.error('Error editing post', {
          component: 'ThreadDetailPage',
          error: err,
          context: { postId: editingPostId },
        });
        setNotice(err instanceof Error ? err.message : 'Failed to save edit');
      } finally {
        setEditSubmitting(false);
      }
    },
    [editingPostId, editBody]
  );

  const cancelEdit = useCallback(() => {
    setEditingPostId(null);
    setEditBody('');
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
          <strong>Error:</strong> {error || 'Thread not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-ink-2" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li>
            <Link to={`/forum/${categorySlug}`} className="hover:text-primary">
              {thread.category.name}
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-ink">
            {thread.title}
          </li>
        </ol>
      </nav>

      {/* Thread Header */}
      <div className="mb-8 bg-surface-2 rounded-lg shadow-md p-6">
        <div className="flex items-start flex-wrap gap-4 mb-4">
          {thread.category.icon && (
            <span className="text-4xl" aria-hidden="true">
              {thread.category.icon}
            </span>
          )}

          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-3xl font-bold text-ink mb-2">{thread.title}</h1>

            <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-sm text-ink-3">
              <span>
                by{' '}
                <strong className="text-ink-2">
                  {thread.author.display_name || thread.author.username}
                </strong>
              </span>
              <span>•</span>
              <span>💬 {totalPosts} replies</span>
              <span>•</span>
              <span>👁️ {thread.view_count} views</span>
            </div>
          </div>

          {/* Badges */}
          <div className="flex items-center gap-2">
            {thread.is_pinned && (
              <span className="px-3 py-1 bg-tertiary/20 text-ink text-sm font-semibold rounded">
                📌 Pinned
              </span>
            )}
            {thread.is_locked && (
              <span className="px-3 py-1 bg-surface-3 text-ink-2 text-sm font-semibold rounded">
                🔒 Locked
              </span>
            )}
            {isAuthenticated && (
              <Button
                onClick={handleToggleSubscription}
                variant={thread.is_subscribed ? 'outline' : 'primary'}
                loading={subscribing}
                disabled={subscribing}
                className="min-h-11"
              >
                {thread.is_subscribed ? '🔕 Following' : '🔔 Follow'}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Write-path notice (errors + moderation outcomes) */}
      {notice && (
        <div className="mb-6 rounded-lg border border-line bg-surface-2 px-4 py-3 text-ink-2">
          {notice}
        </div>
      )}

      {/* Posts List */}
      <div className="space-y-4 mb-8">
        {posts.map((post) =>
          editingPostId === post.id ? (
            <form
              key={post.id}
              onSubmit={handleEditSubmit}
              className="bg-surface-2 rounded-lg shadow-md p-6 space-y-3"
            >
              <span className="block text-sm font-medium text-ink-2">Edit post</span>
              <TipTapEditor key={post.id} content={editBody} onChange={setEditBody} />
              <div className="flex gap-2">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isBlankHtml(editBody) || editSubmitting}
                  loading={editSubmitting}
                >
                  Save
                </Button>
                <Button type="button" variant="outline" onClick={cancelEdit}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <div key={post.id} id={`post-${post.id}`}>
              <PostCard
                post={post}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onReact={isAuthenticated ? handleReact : undefined}
                onReport={isAuthenticated ? handleReport : undefined}
              />
            </div>
          )
        )}
      </div>

      {/* Load More Button (cursor pagination) */}
      {nextCursor && (
        <div className="mb-8 text-center">
          <Button
            onClick={handleLoadMore}
            variant="outline"
            loading={loadingMore}
            disabled={loadingMore}
            className="min-h-11"
          >
            {loadingMore
              ? 'Loading...'
              : // totalPosts is reply_count (excludes the opening post), so compare it
                // against loaded REPLIES, not all loaded posts, or it under-counts by 1.
                `Load More Posts (${Math.max(
                  0,
                  totalPosts - posts.filter((p) => !p.is_first_post).length
                )} remaining)`}
          </Button>
        </div>
      )}

      {/* Reply composer — hidden when the thread is locked/closed */}
      {thread.is_locked ? (
        <div className="mt-8 rounded-lg border border-line bg-surface-2 p-6 text-center">
          <p className="text-ink-2">🔒 This thread is locked — new replies are disabled.</p>
        </div>
      ) : !isAuthenticated ? (
        <div className="mt-8 rounded-lg border border-line bg-surface-2 p-6 text-center">
          <p className="text-ink-2">
            <Link to="/login" className="text-primary hover:underline">
              Log in
            </Link>{' '}
            to post a reply.
          </p>
        </div>
      ) : (
        <form
          onSubmit={handleReply}
          className="mt-8 bg-surface-2 rounded-lg shadow-md p-6 space-y-3"
        >
          <h2 className="text-lg font-semibold text-ink">Post a Reply</h2>
          <TipTapEditor
            key={composerKey}
            content={replyBody}
            onChange={setReplyBody}
            placeholder="Write a reply..."
          />
          <Button
            type="submit"
            variant="primary"
            disabled={isBlankHtml(replyBody) || replySubmitting}
            loading={replySubmitting}
          >
            Post Reply
          </Button>
        </form>
      )}
    </div>
  );
}
