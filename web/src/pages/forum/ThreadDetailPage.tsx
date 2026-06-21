import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchThread, fetchPosts } from '../../services/forumService';
import { parseLeadingId } from '../../utils/forumUrls';
import PostCard from '../../components/forum/PostCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { logger } from '../../utils/logger';
import type { Thread, Post } from '@/types';
import type { PaginatedResponse } from '@/types/forum';

/**
 * ThreadDetailPage Component
 *
 * Displays a thread with its posts (read-only for Phase 1).
 * Route: /forum/:categorySlug/:threadSlug
 *
 * Phase 2: reply/react/delete write UI removed for read-only Phase 1 —
 * restore from git history (commit 36f0a54) + the Phase 2 plan.
 */
export default function ThreadDetailPage() {
  const { categorySlug, threadSlug } = useParams<{ categorySlug: string; threadSlug: string }>();

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

  // Load thread and initial posts
  useEffect(() => {
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

  // Load more posts (cursor pagination) — Phase 2
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
      alert(`Failed to load more posts: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, topicId, thread?.id]);

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
          <div className="flex gap-2">
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
          </div>
        </div>
      </div>

      {/* Posts List */}
      <div className="space-y-4 mb-8">
        {posts.map((post) => (
          <div key={post.id} id={`post-${post.id}`}>
            <PostCard post={post} />
          </div>
        ))}
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
              : `Load More Posts (${Math.max(0, totalPosts - posts.length)} remaining)`}
          </Button>
        </div>
      )}

      {/* Read-only notice — Phase 2 will restore reply/react/delete write UI */}
      <div className="mt-8 rounded-lg border border-line bg-surface-2 p-6 text-center">
        <p className="text-ink-2">🔒 Replies are coming soon — the forum is read-only for now.</p>
      </div>
    </div>
  );
}
