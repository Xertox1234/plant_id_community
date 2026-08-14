import { useState, useEffect, useCallback, useRef, FormEvent } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
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
  markSolution,
  clearSolution,
} from '../../services/forumService';
import { parseLeadingId, userProfilePath } from '../../utils/forumUrls';
import { DELETED_AUTHOR_USERNAME } from '../../utils/forumAuthor';
import { bodyBlocksToHtml } from '../../utils/forumBody';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import PostCard from '../../components/forum/PostCard';
import IdentificationCard from '../../components/forum/IdentificationCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import TipTapEditor from '../../components/forum/TipTapEditor';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import { useAuth } from '../../contexts/AuthContext';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import PageMeta from '../../components/PageMeta';
import {
  IconBell,
  IconBellOff,
  IconEye,
  IconLock,
  IconPin,
  IconReply,
} from '../../components/forum/ForumIcons';
import type { Thread, Post } from '@/types';
import type { PaginatedResponse } from '@/types/forum';

/** Strip tags + whitespace to detect an effectively-empty rich-text body. */
function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>/g, '').trim() === '';
}

/**
 * Whether the post with `postId` is the topic's accepted answer. The single
 * source for this coercion — the leaf node, the tape/banner styling, and the
 * mark/clear toggle must never disagree on it.
 */
function isSolvedPost(thread: Thread | null, postId: string): boolean {
  return String(thread?.solved_post_id ?? '') === postId;
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
  const location = useLocation();
  const announce = useAnnounce();
  useScrollToTop();

  // The route param is a hybrid "id-slug"; lookups use the leading topic id.
  const topicId = parseLeadingId(threadSlug);

  const [thread, setThread] = useState<Thread | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Bumped by the error-state Retry to re-run the load effect (each run gets a
  // fresh `ignore` guard, so a late response from a superseded run is dropped).
  const [reloadKey, setReloadKey] = useState(0);

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
  // Focus the reply composer after a successful post (M25); reset on navigation
  // so arriving on a thread never steals focus into the reply box.
  const [autoFocusComposer, setAutoFocusComposer] = useState<boolean>(false);
  // A post awaiting delete confirmation (styled dialog, replaces window.confirm).
  const [pendingDelete, setPendingDelete] = useState<Post | null>(null);
  // A post the user asked to edit while another edit has unsaved changes (M27).
  const [pendingEditSwitch, setPendingEditSwitch] = useState<Post | null>(null);
  // The reply just posted by THIS user, for the one-shot "pressed into the
  // page" landing animation (Field Notes signature). Purely visual state.
  const [justPostedId, setJustPostedId] = useState<string | null>(null);

  // Tracks the topic currently on screen. handleToggleSubscription reads this
  // after its await to detect that the user navigated to a different thread
  // while its request was in flight, so a late success/failure for thread A
  // can't clobber thread B's displayed state.
  const currentTopicIdRef = useRef<number | null>(null);
  // Remembers the cursor the deep-link auto-chase last requested. A failed
  // load-more leaves nextCursor unchanged, so gating on "cursor actually
  // changed" stops the chase after one attempt instead of retrying the same
  // failing request forever; the manual "Load More" button remains the retry.
  const chaseCursorRef = useRef<string | null>(null);
  // The hash we've already scrolled to. The arrival effect re-runs on every
  // `posts` change (the chase needs that), so without this it would re-scroll
  // to the anchor on each reply/Load-More while the hash lingers in the URL.
  const scrolledHashRef = useRef<string | null>(null);

  // Load thread and initial posts
  useEffect(() => {
    // Refs must not be written during render (react-hooks/refs) — this
    // effect already re-runs on every topicId change, so it doubles as the
    // sync point.
    currentTopicIdRef.current = topicId;
    // A new thread starts a fresh deep-link chase and a fresh scroll target.
    chaseCursorRef.current = null;
    scrolledHashRef.current = null;
    // Restore this topic's reply draft (per-topic key); remount the composer
    // so TipTap's init-only content picks it up.
    setReplyBody(topicId != null ? (loadDraft(draftKey('reply', String(topicId))) ?? '') : '');
    setComposerKey((k) => k + 1);
    // A subscribe/unsubscribe request still in flight for the PREVIOUS
    // thread must not leave this thread's Follow button stuck loading —
    // reset unconditionally on every navigation (handleToggleSubscription's
    // own finally guards against that stale request re-enabling it late).
    setSubscribing(false);
    // Same for an in-flight load-more (the deep-link chase can start one) —
    // its finally is thread-guarded, so clear the flag here for the new thread.
    setLoadingMore(false);
    // Arriving on a thread must not autofocus the reply box (steals focus/scroll);
    // only a successful reply re-enables it.
    setAutoFocusComposer(false);
    // The press animation belongs to the thread it happened on.
    setJustPostedId(null);

    // react.dev race guard: a stale initial load (fast nav to another thread,
    // unmount, or a Retry superseding an in-flight request) is dropped so
    // thread A's content can't render under thread B's URL (audit M22).
    let ignore = false;
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

        if (ignore) return;
        setThread(threadData);
        setPosts(postsData.items);
        // meta.count is 0 for cursor pages (no total); seed from thread.post_count.
        setTotalPosts(threadData.post_count ?? 0);
        setNextCursor(postsData.meta.next ?? null);
      } catch (err) {
        if (ignore) return;
        logger.error('Error loading thread data', {
          component: 'ThreadDetailPage',
          error: err,
          context: { categorySlug, threadSlug },
        });
        setError(err instanceof Error ? err.message : 'Failed to load thread');
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    loadData();
    return () => {
      ignore = true;
    };
  }, [topicId, threadSlug, categorySlug, reloadKey]);

  // Load more posts (cursor pagination)
  const handleLoadMore = useCallback(async () => {
    if (topicId == null || !nextCursor) return;
    // The deep-link chase fires this automatically, so a response can arrive
    // after the user has navigated to another thread. Guard state writes on the
    // thread this request was for, or a late page for thread A would append to
    // thread B's list (mirrors handleToggleSubscription).
    const requestTopicId = topicId;

    try {
      setLoadingMore(true);
      const postsData = (await fetchPosts({
        thread: requestTopicId,
        cursor: nextCursor,
      })) as PaginatedResponse<Post>;

      if (currentTopicIdRef.current !== requestTopicId) return;
      setPosts((prev) => [...prev, ...postsData.items]);
      setNextCursor(postsData.meta.next ?? null);
    } catch (err) {
      logger.error('Error loading more posts', {
        component: 'ThreadDetailPage',
        error: err,
        context: { threadId: thread?.id },
      });
      if (currentTopicIdRef.current === requestTopicId) {
        setNotice(
          `Failed to load more posts: ${err instanceof Error ? err.message : 'Unknown error'}`
        );
      }
    } finally {
      if (currentTopicIdRef.current === requestTopicId) {
        setLoadingMore(false);
      }
    }
  }, [nextCursor, topicId, thread?.id]);

  // Deep-link arrival: scroll to and briefly highlight #post-N once posts render.
  // If the target sits on a later cursor page, pull pages until it appears (this
  // effect re-runs as `posts` grows), then stop when there is nothing left to load.
  useEffect(() => {
    if (loading) return;
    const match = /^#post-(\d+)$/.exec(location.hash);
    if (!match) return;
    const el = document.getElementById(`post-${match[1]}`);
    if (!el) {
      // Advance at most once per cursor: a failed load-more leaves nextCursor
      // unchanged, so this stops the chase instead of retrying it forever.
      if (nextCursor && !loadingMore && chaseCursorRef.current !== nextCursor) {
        chaseCursorRef.current = nextCursor;
        handleLoadMore();
      }
      return;
    }
    // Scroll to a given anchor only once — not again on later posts changes
    // (a reply, a Load More) while the same hash sits in the URL.
    if (scrolledHashRef.current === location.hash) return;
    scrolledHashRef.current = location.hash;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.classList.add('wf-anchor-flash');
    const timer = setTimeout(() => el.classList.remove('wf-anchor-flash'), 2500);
    return () => clearTimeout(timer);
  }, [loading, posts, location.hash, nextCursor, loadingMore, handleLoadMore]);

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
        if (topicId != null) clearDraft(draftKey('reply', String(topicId)));
        setReplyBody('');
        // Remount the editor so it visibly clears, and focus the fresh composer
        // (M25) — remount-via-key alone left focus dropped after posting.
        setComposerKey((k) => k + 1);
        setAutoFocusComposer(true);
        if (res.status === 'published') {
          const refreshed = await collectAllPosts(topicId);
          setPosts(refreshed.items);
          setNextCursor(refreshed.next);
          setTotalPosts((n) => n + 1);
          // Posts are oldest-first, so the just-posted reply is the last item —
          // mark it for the one-shot press-in landing animation.
          setJustPostedId(refreshed.items[refreshed.items.length - 1]?.id ?? null);
          // Success has no visible banner (the reply just appears), so announce
          // it for screen readers (M25).
          announce('Reply posted.', 'polite');
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
    [topicId, replyBody, announce]
  );

  const handleReact = useCallback(async (postId: string, reactionType: string) => {
    try {
      const result = await toggleReaction(postId, reactionType);
      // Carry the toggle's `reacted` into the post's reacted set (M23) so the
      // button's pressed state flips immediately — previously dropped.
      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p;
          const prevReacted = p.reacted ?? [];
          const reacted = result.reacted
            ? [...new Set([...prevReacted, reactionType])]
            : prevReacted.filter((t) => t !== reactionType);
          return { ...p, reaction_counts: result.reaction_counts, reacted };
        })
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

  // Accept / clear this topic's answer (audit H6). Not optimistic, unlike the
  // subscription toggle above: `solved_post_id` is SHARED topic state that
  // other readers see, and the backend can legitimately refuse (422 on a
  // non-live post, 403 if the viewer's rights changed since page load), so the
  // badge moves only once the server confirms where it landed.
  const handleToggleSolution = useCallback(
    async (post: Post) => {
      if (!thread || topicId == null) return;
      const requestTopicId = topicId;
      const isCurrent = isSolvedPost(thread, post.id);
      try {
        const result = isCurrent
          ? await clearSolution(requestTopicId)
          : await markSolution(requestTopicId, Number(post.id));
        // Same in-flight guard as handleToggleSubscription: a late response
        // must not write onto whatever thread the user has since opened.
        if (currentTopicIdRef.current !== requestTopicId) return;
        setThread((prev) =>
          prev
            ? { ...prev, is_solved: result.is_solved, solved_post_id: result.solved_post_id }
            : prev
        );
      } catch (err) {
        logger.error('Error updating accepted answer', {
          component: 'ThreadDetailPage',
          error: err,
          context: { topicId: requestTopicId, postId: post.id },
        });
        if (currentTopicIdRef.current === requestTopicId) {
          setNotice(err instanceof Error ? err.message : 'Failed to update the accepted answer');
        }
      }
    },
    [thread, topicId]
  );

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

  // Open the styled delete confirmation (M24 — replaces window.confirm).
  const handleDelete = useCallback((post: Post) => {
    setPendingDelete(post);
  }, []);

  const confirmDelete = useCallback(async () => {
    const post = pendingDelete;
    if (!post) return;
    setPendingDelete(null);
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
  }, [pendingDelete]);

  // Start editing `post`. If another post is mid-edit with unsaved changes,
  // confirm the discard first instead of silently dropping them (M27).
  const startEditing = useCallback((post: Post) => {
    setEditingPostId(post.id);
    setEditBody(bodyBlocksToHtml(post.body));
  }, []);

  const handleEdit = useCallback(
    (post: Post) => {
      if (editingPostId != null && editingPostId !== post.id) {
        const current = posts.find((p) => p.id === editingPostId);
        const isDirty = !!current && editBody !== bodyBlocksToHtml(current.body);
        if (isDirty) {
          setPendingEditSwitch(post);
          return;
        }
      }
      startEditing(post);
    },
    [editingPostId, editBody, posts, startEditing]
  );

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

  // Confirmed the unsaved-edit discard (M27): switch to the post the user asked
  // to edit, dropping the previous edit's changes.
  const confirmEditSwitch = useCallback(() => {
    if (pendingEditSwitch) startEditing(pendingEditSwitch);
    setPendingEditSwitch(null);
  }, [pendingEditSwitch, startEditing]);

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
        <ForumErrorState
          message={error || 'Thread not found'}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title={`${thread.title} · PlantID`}
        description={`${thread.title} — a discussion in ${thread.category.name} on the Plant Community forum.`}
        og={{
          title: thread.title,
          description: `A discussion in ${thread.category.name} on Plant Community.`,
          // Canonical topic URL — drop any ?query/#hash; the SPA is client-only.
          url: `${window.location.origin}${window.location.pathname}`,
          type: 'article',
        }}
      />
      {/* Breadcrumb — collection path, in the ledger's mono voice. The
          thread-title crumb stays normal case: user content is never shouted. */}
      <nav className="wf-label mb-8" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2 min-w-0">
          <li>
            <Link to="/forum" viewTransition className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            <Link to={`/forum/${categorySlug}`} viewTransition className="hover:text-primary">
              {thread.category.name}
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="normal-case tracking-normal text-ink-2 truncate">
            {thread.title}
          </li>
        </ol>
      </nav>

      {/* Thread Header — the specimen sheet's label block, closed by a double rule */}
      <header className="mb-8 border-b-2 border-line-2 pb-6">
        <div className="wf-label flex flex-wrap items-center gap-x-2 gap-y-1 mb-2">
          <span>No. {thread.id}</span>
          <span aria-hidden="true">·</span>
          <span>
            {thread.category.icon && (
              <span className="mr-1" aria-hidden="true">
                {thread.category.icon}
              </span>
            )}
            {thread.category.name}
          </span>
          {thread.is_pinned && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1 text-clay">
                <IconPin size={12} /> Pinned
              </span>
            </>
          )}
          {thread.is_locked && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <IconLock size={12} /> Locked
              </span>
            </>
          )}
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1">
            <IconReply size={12} /> {totalPosts} replies
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1">
            <IconEye size={12} /> {thread.view_count} views
          </span>
        </div>

        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="flex-1 min-w-0">
            <h1
              className="wf-title text-2xl sm:text-4xl text-ink mb-3"
              style={{ viewTransitionName: `thread-${thread.id}` }}
            >
              {thread.title}
            </h1>

            <p className="text-sm text-ink-3">
              started by{' '}
              {thread.author.username === DELETED_AUTHOR_USERNAME ? (
                <strong className="text-ink-2">
                  {thread.author.display_name || thread.author.username}
                </strong>
              ) : (
                <Link
                  to={userProfilePath(thread.author.username)}
                  className="font-semibold text-ink-2 hover:text-primary hover:underline"
                >
                  {thread.author.display_name || thread.author.username}
                </Link>
              )}
            </p>
          </div>

          {isAuthenticated && (
            <Button
              onClick={handleToggleSubscription}
              variant={thread.is_subscribed ? 'outline' : 'primary'}
              loading={subscribing}
              disabled={subscribing}
              className="min-h-11 gap-2"
            >
              {thread.is_subscribed ? (
                <>
                  <IconBellOff size={14} /> Following
                </>
              ) : (
                <>
                  <IconBell size={14} /> Follow
                </>
              )}
            </Button>
          )}
        </div>
      </header>

      {/* Write-path notice (errors + moderation outcomes). Persistent live
          region: the container is always mounted so swapping its text is read
          out by a screen reader — a conditionally-mounted `role` node generally
          is NOT announced (audit M26/AC1). Visually collapsed when empty. */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className={
          notice
            ? 'mb-6 rounded-xs border border-line bg-surface-2 px-4 py-3 text-ink-2'
            : 'sr-only'
        }
      >
        {notice}
      </div>

      {/* The plant-ID snapshot, above the opening post (audit M6). Outside the
          posts list on purpose: it belongs to the TOPIC, so it must survive the
          opening post being edited, redacted, or paginated away. */}
      {thread?.identification && (
        <IdentificationCard
          identification={thread.identification}
          solvedPostId={thread.solved_post_id}
        />
      )}

      {/* Posts List — the stem: a rail down the reply chain, one node per post.
          The `.wf-node-row` wrapper carries the node; the accepted answer's
          node grows a leaf. */}
      <div className="wf-thread space-y-5 mb-8">
        {posts.map((post) => {
          const isSolution = isSolvedPost(thread, post.id);
          return editingPostId === post.id ? (
            <div key={post.id} className="wf-node-row">
              <form onSubmit={handleEditSubmit} className="wf-sheet p-5 sm:p-6 space-y-3">
                <span className="wf-label block">Edit post</span>
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
            </div>
          ) : (
            <div
              key={post.id}
              id={`post-${post.id}`}
              className={`wf-node-row ${isSolution ? 'wf-node-row--solution' : ''} ${
                justPostedId === post.id ? 'wf-press' : ''
              }`}
              // The press is one-shot: clear its marker once the longest of its
              // animations (the 2s highlight fade) ends, so the class can't
              // replay when the row's classes are re-applied (edit → Cancel
              // reuses this same div) and the row rejoins the scroll-reveal
              // cascade, which excludes .wf-press rows.
              onAnimationEnd={
                justPostedId === post.id
                  ? (e) => {
                      if (e.animationName === 'wf-anchor-fade') setJustPostedId(null);
                    }
                  : undefined
              }
            >
              <PostCard
                post={post}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onReact={isAuthenticated ? handleReact : undefined}
                onReport={isAuthenticated ? handleReport : undefined}
                isSolution={isSolution}
                // Offered only to a viewer the backend says may mark, and never
                // on the opening post — a question is not its own answer, and
                // the endpoint 422s it.
                onToggleSolution={
                  thread?.can_mark_solution && !post.is_first_post
                    ? handleToggleSolution
                    : undefined
                }
              />
            </div>
          );
        })}
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
        <div className="wf-sheet mt-8 p-6 text-center">
          <p className="inline-flex items-center gap-2 text-ink-2">
            <IconLock size={14} /> This thread is locked — new replies are disabled.
          </p>
        </div>
      ) : !isAuthenticated ? (
        <div className="wf-sheet mt-8 p-6 text-center">
          <p className="text-ink-2">
            <Link to="/login" className="text-primary hover:underline">
              Log in
            </Link>{' '}
            to post a reply.
          </p>
        </div>
      ) : (
        <form onSubmit={handleReply} className="wf-sheet mt-8 p-5 sm:p-6 space-y-3">
          <p className="wf-label">Add to the record</p>
          <h2 className="wf-title text-xl text-ink">Post a Reply</h2>
          <TipTapEditor
            key={composerKey}
            content={replyBody}
            autoFocus={autoFocusComposer}
            onChange={(html) => {
              setReplyBody(html);
              if (topicId != null) {
                saveDraft(draftKey('reply', String(topicId)), isBlankHtml(html) ? '' : html);
              }
            }}
            placeholder="Write a reply..."
          />
          <Button
            type="submit"
            variant="primary"
            disabled={isBlankHtml(replyBody) || replySubmitting}
            loading={replySubmitting}
            loadingText="Posting…"
          >
            Post Reply
          </Button>
        </form>
      )}

      {/* Styled confirmations — replace native window.confirm (M24) and guard
          unsaved edits when switching edit targets (M27). */}
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this post?"
        message="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
      <ConfirmDialog
        open={pendingEditSwitch !== null}
        title="Discard unsaved changes?"
        message="You have unsaved edits on another post. Editing this one will discard them."
        confirmLabel="Discard & edit"
        onConfirm={confirmEditSwitch}
        onCancel={() => setPendingEditSwitch(null)}
      />
    </div>
  );
}
