import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { fetchBookmarks } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import PageMeta from '../../components/PageMeta';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import type { Thread } from '@/types';

/**
 * SavedThreadsPage Component
 *
 * The member's own saved threads, newest-saved first (audit M2).
 * Route: /forum/saved (auth-gated — the endpoint 401s for anonymous).
 *
 * Every row carries its own board, so unlike ThreadListPage there is no single
 * category to stamp on: `fetchBookmarks` maps each row's category from the
 * board the backend sends.
 */
export default function SavedThreadsPage() {
  useScrollToTop();

  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  // Bumped by the error-state Retry to re-run the load effect.
  const [reloadKey, setReloadKey] = useState(0);
  // Monotonic request generation — a Retry mid-flight must not let the stale
  // response overwrite the newer one's list or cursor (mirrors ThreadListPage).
  const loadGenRef = useRef(0);

  useEffect(() => {
    const gen = ++loadGenRef.current;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchBookmarks();
        if (loadGenRef.current !== gen) return;
        setThreads(data.items);
        setNextCursor(data.meta.next ?? null);
      } catch (err) {
        if (loadGenRef.current !== gen) return;
        logger.error('Error loading saved threads', {
          component: 'SavedThreadsPage',
          error: err,
        });
        setError(err instanceof Error ? err.message : 'Failed to load saved threads');
      } finally {
        if (loadGenRef.current === gen) setLoading(false);
      }
    };
    load();
  }, [reloadKey]);

  const handleLoadMore = useCallback(async () => {
    if (!nextCursor) return;
    const gen = loadGenRef.current;
    try {
      setLoadingMore(true);
      const data = await fetchBookmarks(nextCursor);
      if (loadGenRef.current !== gen) return;
      setThreads((prev) => [...prev, ...data.items]);
      setNextCursor(data.meta.next ?? null);
    } catch (err) {
      if (loadGenRef.current !== gen) return;
      logger.error('Error loading more saved threads', {
        component: 'SavedThreadsPage',
        error: err,
      });
    } finally {
      if (loadGenRef.current === gen) setLoadingMore(false);
    }
  }, [nextCursor]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title="Saved threads · PlantID"
        description="Threads you have saved to come back to."
      />

      <nav className="mb-6 text-sm text-ink-2" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-ink">
            Saved
          </li>
        </ol>
      </nav>

      <div className="mb-8">
        <h1 className="text-4xl font-bold text-ink">Saved threads</h1>
        <p className="mt-2 text-lg text-ink-2">
          Threads you saved, most recent first. Saving is private — it does not follow the thread or
          notify anyone.
        </p>
      </div>

      {error ? (
        <ForumErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-ink-3">
          <p className="text-lg">Nothing saved yet.</p>
          <p className="text-sm mt-2">
            Use the 🔖 Save button on any thread to keep it here for later.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {threads.map((thread) => (
            <ThreadCard key={thread.id} thread={thread} />
          ))}
        </div>
      )}

      {/* No remaining-count here, unlike the board list: nothing reports a total
          number of bookmarks, and cursor pagination omits one — a computed
          "N remaining" would be invented (the same dishonesty audit M30
          removed from the board list). */}
      {nextCursor && !loading && !error && (
        <div className="mt-8 text-center">
          <Button
            onClick={handleLoadMore}
            variant="outline"
            loading={loadingMore}
            disabled={loadingMore}
            className="min-h-11"
          >
            {loadingMore ? 'Loading...' : 'Load More'}
          </Button>
        </div>
      )}
    </div>
  );
}
