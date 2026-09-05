import { useState, useEffect, useCallback, useRef, FormEvent } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import {
  Bell,
  BellOff,
  Bookmark,
  BookmarkCheck,
  Eye,
  Lock,
  MessagesSquare,
  Pin,
  Reply,
  Users,
} from 'lucide-react';
import {
  fetchThread,
  fetchThreads,
  fetchPosts,
  createPost,
  updatePost,
  deletePost,
  toggleReaction,
  reportPost,
  blockUser,
  unblockUser,
  subscribeToTopic,
  unsubscribeFromTopic,
  bookmarkTopic,
  unbookmarkTopic,
  markSolution,
  clearSolution,
  votePoll,
} from '../../services/forumService';
import { parseLeadingId, userProfilePath, threadPath } from '../../utils/forumUrls';
import { DELETED_AUTHOR_USERNAME } from '../../utils/forumAuthor';
import { bodyBlocksToHtml } from '../../utils/forumBody';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import { useIdentitySwap } from '../../hooks/useIdentitySwap';
import { specimenAvatar } from '../../utils/forumAvatars';
import PostCard from '../../components/forum/PostCard';
import IdentificationCard from '../../components/forum/IdentificationCard';
import PollCard from '../../components/forum/PollCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import TipTapEditor from '../../components/forum/TipTapEditor';
import { ThreadDetailSkeleton } from '../../components/forum/ForumSkeleton';
import Button from '../../components/ui/Button';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import Avatar from '../../components/ui/Avatar';
import Timestamp from '../../components/ui/Timestamp';
import RailSlot, { RAIL_MEDIA_QUERY } from '../../components/layout/RailSlot';
import RailModule from '../../components/ui/RailModule';
import FromTheBlogModule from '../../components/forum/rail/FromTheBlogModule';
import { useAuth } from '../../contexts/AuthContext';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { logger } from '../../utils/logger';
import PageMeta from '../../components/PageMeta';
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

// Deep-link / just-posted highlight duration — must outlast the CSS
// canopy-flash-fade animation (2.4s).
const CANOPY_FLASH_MS = 2500;

// The board rail shows at most this many other topics (sibling precedent:
// FromTheBlogModule's RAIL_POST_LIMIT).
const RAIL_BOARD_TOPICS_LIMIT = 5;

/**
 * ThreadDetailPage Component
 *
 * Displays a thread with its posts and the write UI (reply, edit, delete, react).
 * Route: /forum/:categorySlug/:threadSlug
 */
export default function ThreadDetailPage() {
  const { categorySlug, threadSlug } = useParams<{ categorySlug: string; threadSlug: string }>();
  const { isAuthenticated, user, revalidateIdentity } = useAuth();
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
  // A passive account swap (focus revalidation, expired session + a different
  // login) clears the stored drafts in AuthContext, but this page's own reply
  // state would re-persist the previous account's text on the next keystroke
  // (code review, PR #629) — drop it and remount the editor.
  useIdentitySwap(user?.id, () => {
    setReplyBody('');
    setComposerKey((k) => k + 1);
    // AuthContext drops every draft key on the swap; this page's own persist
    // only runs from the editor's onChange, so clear this topic's key here
    // too rather than depend on the ordering of two effects.
    if (topicId != null) clearDraft(draftKey('reply', String(topicId)));
  });
  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState<string>('');
  const [editSubmitting, setEditSubmitting] = useState<boolean>(false);
  const [subscribing, setSubscribing] = useState<boolean>(false);
  const [bookmarking, setBookmarking] = useState<boolean>(false);
  // A transient banner for write errors + moderation outcomes.
  const [notice, setNotice] = useState<string | null>(null);
  // Focus the reply composer after a successful post (M25); reset on navigation
  // so arriving on a thread never steals focus into the reply box.
  const [autoFocusComposer, setAutoFocusComposer] = useState<boolean>(false);
  // A post awaiting delete confirmation (styled dialog, replaces window.confirm).
  const [pendingDelete, setPendingDelete] = useState<Post | null>(null);
  // A post the user asked to edit while another edit has unsaved changes (M27).
  const [pendingEditSwitch, setPendingEditSwitch] = useState<Post | null>(null);
  // The reply just posted by THIS user, marked for the one-shot canopy-flash
  // highlight. Purely visual state; cleared by a 2.5s timer.
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
  // End of the current deep-link flash window (epoch ms) — lets an effect
  // re-run inside the window re-arm the highlight for the remaining time.
  const flashUntilRef = useRef(0);

  // Load thread and initial posts
  useEffect(() => {
    // Refs must not be written during render (react-hooks/refs) — this
    // effect already re-runs on every topicId change, so it doubles as the
    // sync point.
    currentTopicIdRef.current = topicId;
    // A new thread starts a fresh deep-link chase and a fresh scroll target.
    chaseCursorRef.current = null;
    scrolledHashRef.current = null;
    flashUntilRef.current = 0;
    // Restore this topic's reply draft (per-topic key); remount the composer
    // so TipTap's init-only content picks it up.
    setReplyBody(topicId != null ? (loadDraft(draftKey('reply', String(topicId))) ?? '') : '');
    setComposerKey((k) => k + 1);
    // A subscribe/unsubscribe request still in flight for the PREVIOUS
    // thread must not leave this thread's Follow button stuck loading —
    // reset unconditionally on every navigation (handleToggleSubscription's
    // own finally guards against that stale request re-enabling it late).
    setSubscribing(false);
    // Same for an in-flight bookmark/unbookmark request (todo 283 / M2) —
    // handleToggleBookmark's own finally has the identical stale-request
    // guard, so it never re-enables this on a late resolve either.
    setBookmarking(false);
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
    if (scrolledHashRef.current !== location.hash) {
      scrolledHashRef.current = location.hash;
      flashUntilRef.current = Date.now() + CANOPY_FLASH_MS;
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // (Re-)arm the highlight for whatever remains of the flash window. The
    // cleanup strips the class on every re-run (posts growing, a Load More
    // click), so without this re-add a mid-window commit would kill the ring
    // permanently and the user never sees which post they were sent to.
    const remaining = flashUntilRef.current - Date.now();
    if (remaining <= 0) return;
    el.classList.add('canopy-flash');
    const timer = setTimeout(() => el.classList.remove('canopy-flash'), remaining);
    return () => {
      clearTimeout(timer);
      // The cleanup must also remove the class: a re-run inside the window
      // cancels the timer, and under reduced motion the static ring would
      // otherwise persist forever if nothing re-armed it.
      el.classList.remove('canopy-flash');
    };
  }, [loading, posts, location.hash, nextCursor, loadingMore, handleLoadMore]);

  // The just-posted highlight is one-shot: clear its marker on a timer (the
  // reduced-motion rendering is a static ring, so animationend never fires).
  useEffect(() => {
    if (justPostedId == null) return;
    const timer = setTimeout(() => setJustPostedId(null), CANOPY_FLASH_MS);
    return () => clearTimeout(timer);
  }, [justPostedId]);

  // Rail: other recent topics on this board. Best-effort — a failure just
  // leaves the module unrendered; never blocks the thread itself. One board =
  // one fetch: the raw page is cached per board slug and filtered at render,
  // so same-board thread navs reuse it (its counts may lag until the board
  // changes). Below the xl breakpoint the rail is display:none, so the fetch
  // is skipped outright rather than paid for content nobody can see.
  const [boardThreads, setBoardThreads] = useState<Thread[]>([]);
  const railVisible = useMediaQuery(RAIL_MEDIA_QUERY);
  const boardSlug = thread?.category?.slug;
  useEffect(() => {
    // Reset before fetching: navigating to a thread on another board (or a
    // fetch failure) must not leave the previous board's list in the rail.
    setBoardThreads([]);
    if (!railVisible || !boardSlug) return;
    let ignore = false;
    fetchThreads({ board: boardSlug })
      .then((data) => {
        if (!ignore) setBoardThreads(data.items);
      })
      .catch(() => {
        /* rail is optional — the thread page must not surface this */
      });
    return () => {
      ignore = true;
    };
  }, [boardSlug, railVisible]);

  // Submit a reply. A published reply is refetched into the list; a pending reply
  // (untrusted author) is unlisted, so we only confirm it was submitted.
  const handleReply = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (topicId == null || isBlankHtml(replyBody)) return;
      // Stale-thread guard (audit 2026-09-04 M2), same as every other write
      // handler here: route param changes reuse this component instance, so
      // a reply submitted on thread A that resolves after navigating to
      // thread B must not clear B's composer or replace B's post list — and
      // this chain (createPost → revalidateIdentity → collectAllPosts) is
      // the longest await on the page.
      const requestTopicId = topicId;
      try {
        setReplySubmitting(true);
        setNotice(null);
        const res = await createPost({ thread: requestTopicId, content: replyBody });
        clearDraft(draftKey('reply', String(requestTopicId)));
        // Defense-in-depth (todo 297): the reply already posted under
        // whatever identity the cookie carried — this can only detect a
        // switch, not prevent one (a TOCTOU race, same as NewThreadPage).
        // A silent "Reply posted." here is exactly how the live prod
        // incident went unnoticed, so a drifted identity gets a distinct,
        // visible notice instead — checked regardless of published/pending,
        // since a misattributed pending reply silently lands in the wrong
        // user's moderation queue just the same. It runs BEFORE the
        // stale-thread guard: it only touches AuthContext, and it is the one
        // write-time identity refresh (AuthContext otherwise revalidates on
        // focus alone), so navigating threads mid-post must not skip it
        // (code review, PR #629).
        const actingUserId = user?.id ?? null;
        const current = await revalidateIdentity();
        const drifted = (current?.id ?? null) !== actingUserId;
        const driftNotice = current?.username
          ? `Your session changed while replying — this was posted as ${current.username}, not the account you started with.`
          : 'Your session changed while replying — you were signed out.';
        if (currentTopicIdRef.current !== requestTopicId) {
          // The page moved on, but a drift still has to be heard somewhere;
          // the announcer is app-global.
          if (drifted) announce(driftNotice, 'assertive');
          return;
        }
        setReplyBody('');
        // Remount the editor so it visibly clears, and focus the fresh composer
        // (M25) — remount-via-key alone left focus dropped after posting.
        setComposerKey((k) => k + 1);
        setAutoFocusComposer(true);

        if (res.status === 'published') {
          const refreshed = await collectAllPosts(requestTopicId);
          if (currentTopicIdRef.current !== requestTopicId) return;
          setPosts(refreshed.items);
          setNextCursor(refreshed.next);
          setTotalPosts((n) => n + 1);
          // Posts are oldest-first, so the just-posted reply is the last item —
          // mark it for the one-shot press-in landing animation.
          setJustPostedId(refreshed.items[refreshed.items.length - 1]?.id ?? null);
          if (drifted) {
            setNotice(driftNotice);
          } else {
            // Success has no visible banner (the reply just appears), so
            // announce it for screen readers (M25).
            announce('Reply posted.', 'polite');
          }
        } else {
          setNotice(
            drifted
              ? `${driftNotice} It is awaiting moderation.`
              : 'Your reply was submitted and is awaiting moderation.'
          );
        }
      } catch (err) {
        logger.error('Error posting reply', {
          component: 'ThreadDetailPage',
          error: err,
          context: { threadId: requestTopicId },
        });
        if (currentTopicIdRef.current === requestTopicId) {
          setNotice(err instanceof Error ? err.message : 'Failed to post reply');
        }
      } finally {
        setReplySubmitting(false);
      }
    },
    [topicId, replyBody, announce, user, revalidateIdentity]
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

  const handleToggleBookmark = useCallback(async () => {
    if (!thread || topicId == null) return;
    const requestTopicId = topicId;
    const wasBookmarked = thread.is_bookmarked ?? false;
    setBookmarking(true);
    // Optimistic — same shape as handleToggleSubscription above.
    setThread((prev) => (prev ? { ...prev, is_bookmarked: !wasBookmarked } : prev));
    try {
      if (wasBookmarked) {
        await unbookmarkTopic(requestTopicId);
      } else {
        await bookmarkTopic(requestTopicId);
      }
    } catch (err) {
      logger.error('Error toggling topic bookmark', {
        component: 'ThreadDetailPage',
        error: err,
        context: { threadId: thread.id },
      });
      // Same navigated-away guard as handleToggleSubscription (todo 253
      // slice 3 review finding) — a late failure must not touch a thread
      // the user has since moved away from.
      if (currentTopicIdRef.current === requestTopicId) {
        setThread((prev) => (prev ? { ...prev, is_bookmarked: wasBookmarked } : prev));
        setNotice(err instanceof Error ? err.message : 'Failed to update bookmark');
      }
    } finally {
      if (currentTopicIdRef.current === requestTopicId) {
        setBookmarking(false);
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

  // Block/unblock an author (todo 284/M9). A block can affect several posts
  // by the same author on this page, so a single-post local update (like
  // handleToggleSolution's setThread) isn't enough — reuse the same
  // full-refetch retry mechanism as the ForumErrorState onRetry below to
  // bring every post's is_blocked flag back in line from the server.
  const handleBlockAuthor = useCallback(async (username: string) => {
    try {
      await blockUser(username);
      setReloadKey((k) => k + 1);
    } catch (err) {
      logger.error('Error blocking user', {
        component: 'ThreadDetailPage',
        error: err,
        context: { username },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to block user');
    }
  }, []);

  const handleUnblockAuthor = useCallback(async (username: string) => {
    try {
      await unblockUser(username);
      setReloadKey((k) => k + 1);
    } catch (err) {
      logger.error('Error unblocking user', {
        component: 'ThreadDetailPage',
        error: err,
        context: { username },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to unblock user');
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
        <ThreadDetailSkeleton />
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

  // Rail: participants derive from already-loaded posts (no new fetch).
  const participants = posts.reduce<
    { username: string; display: string; avatar?: string | null }[]
  >((acc, p) => {
    if (
      p.author.username !== DELETED_AUTHOR_USERNAME &&
      !acc.some((a) => a.username === p.author.username)
    ) {
      acc.push({
        username: p.author.username,
        display: p.author.display_name || p.author.username,
        avatar: p.author.avatar,
      });
    }
    return acc;
  }, []);

  // Rail: the cached board page, minus this thread and pinned topics — pinned
  // announcements sort first server-side (-is_pinned) and would otherwise
  // permanently occupy every slot. List items carry an empty category, so
  // links below build paths from this thread's own (same-board) category.
  const railThreads = boardThreads
    .filter((t) => t.id !== thread.id && !t.is_pinned)
    .slice(0, RAIL_BOARD_TOPICS_LIMIT);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title={`${thread.title} · Houseplant MD`}
        description={`${thread.title} — a discussion in ${thread.category.name} on the Houseplant MD community forum.`}
        og={{
          title: thread.title,
          description: `A discussion in ${thread.category.name} on Houseplant MD.`,
          // Canonical topic URL — drop any ?query/#hash; the SPA is client-only.
          url: `${window.location.origin}${window.location.pathname}`,
          type: 'article',
        }}
      />
      {/* Breadcrumb — collection path, in the mono data voice. The
          thread-title crumb stays normal case: user content is never shouted. */}
      <nav className="gt-label mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2 min-w-0">
          <li>
            <Link to="/forum" viewTransition className="hover:text-primary">
              Forum
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

      {/* Thread Header — the label block, closed by a single rule */}
      <header className="mb-8 border-b border-line-2 pb-6">
        <div className="gt-label flex flex-wrap items-center gap-x-2 gap-y-1 mb-2">
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
                <Pin className="h-3.5 w-3.5" aria-hidden="true" /> Pinned
              </span>
            </>
          )}
          {thread.is_locked && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <Lock className="h-3.5 w-3.5" aria-hidden="true" /> Locked
              </span>
            </>
          )}
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1">
            <Reply className="h-3.5 w-3.5" aria-hidden="true" /> {totalPosts} replies
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" aria-hidden="true" /> {thread.view_count} views
          </span>
        </div>

        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="flex-1 min-w-0">
            <h1
              className="gt-display text-[26px] sm:text-[34px] text-ink mb-3"
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

          {/* flex-wrap on the pair below: the outer row's own wrap is
              neutralized by the title block's flex-1 min-w-0 (0 flex-basis
              contributes nothing to the wrap calc), so at narrow widths this
              pair — now two buttons, not one — needs its own wrap fallback
              rather than squeezing the title (code review, todo 283). */}
          {isAuthenticated && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={handleToggleBookmark}
                variant={thread.is_bookmarked ? 'outline' : 'primary'}
                loading={bookmarking}
                disabled={bookmarking}
                className="min-h-11 gap-2"
              >
                {thread.is_bookmarked ? (
                  <>
                    <BookmarkCheck className="h-3.5 w-3.5" aria-hidden="true" /> Bookmarked
                  </>
                ) : (
                  <>
                    <Bookmark className="h-3.5 w-3.5" aria-hidden="true" /> Bookmark
                  </>
                )}
              </Button>
              <Button
                onClick={handleToggleSubscription}
                variant={thread.is_subscribed ? 'outline' : 'primary'}
                loading={subscribing}
                disabled={subscribing}
                className="min-h-11 gap-2"
              >
                {thread.is_subscribed ? (
                  <>
                    <BellOff className="h-3.5 w-3.5" aria-hidden="true" /> Following
                  </>
                ) : (
                  <>
                    <Bell className="h-3.5 w-3.5" aria-hidden="true" /> Follow
                  </>
                )}
              </Button>
            </div>
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
            ? 'mb-6 rounded-md border border-line bg-surface-2 px-4 py-3 text-ink-2'
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

      {/* The topic's poll (audit M8). Above the posts for the same reason the
          ID card is: it belongs to the TOPIC, not to a post, so it must not
          paginate away. Keyed on the poll id so navigating between two poll
          threads remounts it rather than carrying the previous poll's local
          vote state across. */}
      {thread?.poll && topicId != null && (
        <PollCard
          key={thread.poll.id}
          poll={thread.poll}
          canVote={isAuthenticated}
          // topicId (parsed from the URL), NOT Number(thread.id): `id` is the
          // display-shaped string every mapper produces, and every other call
          // on this page — fetchThread, the subscribe/bookmark toggles —
          // already uses topicId as the canonical numeric id.
          onVote={(optionId) => votePoll(topicId, optionId)}
        />
      )}

      {/* Posts List — one Canopy card per post. The solution ring lives on
          PostCard's `isSolution` prop; the just-posted highlight is the same
          `.canopy-flash` ring the deep-link arrival effect uses. */}
      <div className="mb-8 flex flex-col gap-4">
        {posts.map((post) => {
          const isSolution = isSolvedPost(thread, post.id);
          return editingPostId === post.id ? (
            <div key={post.id}>
              <form
                onSubmit={handleEditSubmit}
                className="canopy-card space-y-3 rounded-md p-5 sm:p-6"
              >
                <span className="gt-label block">Edit post</span>
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
              className={justPostedId === post.id ? 'canopy-flash' : undefined}
            >
              <PostCard
                post={post}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onReact={isAuthenticated ? handleReact : undefined}
                onReport={isAuthenticated ? handleReport : undefined}
                onBlock={isAuthenticated ? handleBlockAuthor : undefined}
                onUnblock={isAuthenticated ? handleUnblockAuthor : undefined}
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
        <div className="canopy-card rounded-md mt-8 p-6 text-center">
          <p className="inline-flex items-center gap-2 text-ink-2">
            <Lock className="h-3.5 w-3.5" aria-hidden="true" /> This thread is locked — new replies
            are disabled.
          </p>
        </div>
      ) : !isAuthenticated ? (
        <div className="canopy-card rounded-md mt-8 p-6 text-center">
          <p className="text-ink-2">
            <Link to="/login" className="text-primary hover:underline">
              Log in
            </Link>{' '}
            to post a reply.
          </p>
        </div>
      ) : (
        <form onSubmit={handleReply} className="canopy-card rounded-md mt-8 p-5 sm:p-6 space-y-3">
          <p className="gt-label">Join the discussion</p>
          <h2 className="gt-h3 text-ink">Post a Reply</h2>
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

      <RailSlot>
        {participants.length > 0 && (
          <RailModule icon={<Users aria-hidden="true" />} title="In this thread">
            <ul className="flex flex-col gap-2.5">
              {participants.slice(0, 6).map((person) => (
                <li key={person.username} className="flex items-center gap-2.5">
                  <Avatar src={person.avatar || specimenAvatar(person.username)} alt="" size="sm" />
                  <Link
                    to={userProfilePath(person.username)}
                    className="min-w-0 truncate text-[13px] font-medium text-ink transition-colors hover:text-primary"
                  >
                    {person.display}
                  </Link>
                </li>
              ))}
            </ul>
          </RailModule>
        )}
        {railThreads.length > 0 && (
          <RailModule
            icon={<MessagesSquare aria-hidden="true" />}
            title={`More in ${thread.category.name}`}
          >
            <ul className="flex flex-col gap-3">
              {railThreads.map((t) => (
                <li key={t.id}>
                  <Link to={threadPath(thread.category, t)} className="group block">
                    <span className="line-clamp-2 text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
                      {t.title}
                    </span>
                    <span className="gt-label mt-0.5 block normal-case tracking-normal">
                      <Timestamp iso={t.last_activity_at} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </RailModule>
        )}
        <FromTheBlogModule />
      </RailSlot>
    </div>
  );
}
