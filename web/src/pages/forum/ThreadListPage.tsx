import { useState, useEffect, useCallback, useRef, FormEvent } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import { fetchThreads, fetchCategory } from '../../services/forumService';
import { parseLeadingId } from '../../utils/forumUrls';
import ThreadCard from '../../components/forum/ThreadCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { logger } from '../../utils/logger';
import type { Thread, Category } from '@/types';

/**
 * ThreadListPage Component
 *
 * Displays threads in a category with search, filters, and cursor pagination.
 * Route: /forum/:categorySlug
 */
export default function ThreadListPage() {
  const { categorySlug } = useParams<{ categorySlug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [category, setCategory] = useState<Category | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);

  // Sort is URL-driven AND passed to the backend (fetchThreads → ?sort=). The
  // search box redirects to the dedicated /forum/search page (handleSearch), so
  // there is no in-page search state to track.
  const ordering = searchParams.get('order') || '-last_activity_at';

  // Track the resolved board slug so Load More can reuse it without re-fetching category
  const boardSlugRef = useRef<string | null>(null);
  // Cache the resolved category (keyed on its forum id) so a pure sort change
  // reuses it instead of re-fetching the boards list on every dropdown change.
  const categoryCacheRef = useRef<{ forumId: number; category: Category } | null>(null);
  // Monotonic request generation. A newer load (board nav or sort change) bumps
  // it; in-flight loads and Load More re-check it after each await and drop a
  // stale response, so a slow old-sort request can't clobber the current list or
  // cursor (mirrors ThreadDetailPage's currentTopicIdRef race guard).
  const loadGenRef = useRef(0);

  // Load category (once per board) + threads (on board or sort change).
  useEffect(() => {
    const loadData = async () => {
      if (!categorySlug) return;

      const forumId = parseLeadingId(categorySlug);
      if (forumId == null) {
        setError('Invalid category URL');
        setLoading(false);
        return;
      }

      const gen = ++loadGenRef.current;
      try {
        setLoading(true);
        setLoadingMore(false); // a fresh load supersedes any in-flight Load More
        setError(null);

        // Resolve the board once; a pure sort change reuses the cached category.
        let categoryData =
          categoryCacheRef.current?.forumId === forumId ? categoryCacheRef.current.category : null;
        if (!categoryData) {
          categoryData = await fetchCategory(forumId);
          if (loadGenRef.current !== gen) return;
          categoryCacheRef.current = { forumId, category: categoryData };
          boardSlugRef.current = categoryData.slug;
          setCategory(categoryData);
        }

        const threadsData = await fetchThreads({ board: categoryData.slug, sort: ordering });
        if (loadGenRef.current !== gen) return;
        // Stamp the resolved category onto each thread so threadPath builds
        // correct URLs (/forum/{id}-{slug}/...) instead of /forum/-topic/...
        setThreads(threadsData.items.map((t) => ({ ...t, category: categoryData })));
        setNextCursor(threadsData.meta.next ?? null);
      } catch (err) {
        if (loadGenRef.current !== gen) return;
        logger.error('Error loading thread list data', {
          component: 'ThreadListPage',
          error: err,
          context: { categorySlug },
        });
        setError(err instanceof Error ? err.message : 'Failed to load threads');
      } finally {
        if (loadGenRef.current === gen) setLoading(false);
      }
    };

    loadData();
  }, [categorySlug, ordering]);

  // The board page has no in-place search. Submitting redirects to the global
  // /forum/search page, pre-filtered to this board — real full-text search lives
  // there (paginated, highlighted). This keeps the control honest instead of
  // rendering a form that quietly does nothing.
  const handleSearch = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const searchQuery = (new FormData(e.currentTarget).get('search') as string)?.trim();
      if (!searchQuery) return;
      const params = new URLSearchParams({ q: searchQuery });
      if (boardSlugRef.current) params.set('category', boardSlugRef.current);
      navigate(`/forum/search?${params}`);
    },
    [navigate]
  );

  // Handle ordering change (URL/UI only)
  const handleOrderChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newOrder = e.target.value;
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        newParams.set('order', newOrder);
        return newParams;
      });
    },
    [setSearchParams]
  );

  // Load more threads using the cursor from the last response
  const handleLoadMore = useCallback(async () => {
    const boardSlug = boardSlugRef.current;
    if (!nextCursor || !boardSlug) return;

    // Tie this append to the current load generation: if a board nav or sort
    // change supersedes us mid-flight, drop the stale page so we don't append
    // old-sort rows or overwrite the cursor that belongs to the new ordering.
    const gen = loadGenRef.current;
    try {
      setLoadingMore(true);
      const threadsData = await fetchThreads({ board: boardSlug, cursor: nextCursor });
      if (loadGenRef.current !== gen) return;
      // Stamp category so Load More threads also get correct threadPath URLs.
      setThreads((prev) => [
        ...prev,
        ...threadsData.items.map((t) => ({ ...t, category: category! })),
      ]);
      setNextCursor(threadsData.meta.next ?? null);
    } catch (err) {
      if (loadGenRef.current !== gen) return;
      logger.error('Error loading more threads', {
        component: 'ThreadListPage',
        error: err,
        context: { categorySlug },
      });
    } finally {
      if (loadGenRef.current === gen) setLoadingMore(false);
    }
  }, [nextCursor, categorySlug, category]);

  if (loading && !category) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !category) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-ink-2" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-ink">
            {category?.name}
          </li>
        </ol>
      </nav>

      {/* Category Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          {category?.icon && (
            <span className="text-4xl" aria-hidden="true">
              {category.icon}
            </span>
          )}
          <h1 className="text-4xl font-bold text-ink">{category?.name}</h1>
        </div>

        {category?.description && <p className="text-lg text-ink-2">{category.description}</p>}
      </div>

      {/* Toolbar */}
      <div className="mb-6 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="flex gap-2">
            <input
              type="search"
              name="search"
              placeholder="Search this board…"
              aria-label="Search this board"
              className="flex-1 px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink"
            />
            <Button type="submit" variant="primary">
              Search
            </Button>
          </div>
        </form>

        {/* Sort & New Thread Button */}
        <div className="flex gap-2">
          <select
            value={ordering}
            onChange={handleOrderChange}
            className="min-h-11 px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary bg-surface-2 text-ink"
          >
            <option value="-last_activity_at">Recent Activity</option>
            <option value="-created_at">Newest First</option>
            <option value="created_at">Oldest First</option>
            <option value="-view_count">Most Viewed</option>
            <option value="-post_count">Most Replies</option>
          </select>

          <Link to={`/forum/new-thread?category=${categorySlug}`}>
            <Button variant="primary">+ New Thread</Button>
          </Link>
        </div>
      </div>

      {/* Threads List */}
      {loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-ink-3">
          <p className="text-lg">No threads found.</p>
          <p className="text-sm mt-2">Be the first to start a discussion!</p>
        </div>
      ) : (
        <div className="space-y-4">
          {threads.map((thread) => (
            <ThreadCard key={thread.id} thread={thread} />
          ))}
        </div>
      )}

      {/* Load More (cursor pagination) */}
      {nextCursor && (
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
