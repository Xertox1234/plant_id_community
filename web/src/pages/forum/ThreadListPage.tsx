import { useState, useEffect, useCallback, useRef, FormEvent } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import { fetchThreads, fetchCategory } from '../../services/forumService';
import { parseLeadingId } from '../../utils/forumUrls';
import ThreadCard from '../../components/forum/ThreadCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import PageMeta from '../../components/PageMeta';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import type { Thread, Category } from '@/types';

/**
 * ThreadListPage Component
 *
 * Displays threads in a category with search, filters, and cursor pagination.
 * Route: /forum/:categorySlug
 */
export default function ThreadListPage() {
  useScrollToTop();
  const { categorySlug } = useParams<{ categorySlug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [category, setCategory] = useState<Category | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  // Bumped by the error-state Retry to re-run the load effect (the effect's
  // own loadGenRef already drops stale responses — M22 was handled here).
  const [reloadKey, setReloadKey] = useState(0);

  // Sort is URL-driven AND passed to the backend (fetchThreads → ?sort=). The
  // search box redirects to the dedicated /forum/search page (handleSearch), so
  // there is no in-page search state to track.
  const ordering = searchParams.get('order') || '-last_activity_at';
  // Tag filter (audit M5) — URL-driven like `order`, so it survives a reload and
  // is shareable, and passed through to the backend's ?tag= filter.
  const activeTag = searchParams.get('tag') || '';

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
        // Drop the old cursor too: it addresses the PREVIOUS result set (other
        // sort/tag), so a Load More clicked during this reload would append
        // wrong-filter rows and then overwrite the new cursor with a stale one.
        // The generation guard alone cannot catch that click — handleLoadMore
        // reads loadGenRef AT CLICK TIME, which is already this reload's gen.
        setNextCursor(null);
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

        const threadsData = await fetchThreads({
          board: categoryData.slug,
          sort: ordering,
          tag: activeTag || undefined,
        });
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
  }, [categorySlug, ordering, activeTag, reloadKey]);

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

  // Toggle the tag filter. Clicking the active tag clears it, so the chip is a
  // real toggle rather than a one-way trip. The cursor is deliberately NOT
  // carried over — a new filter means a new result set, so it restarts at page 1.
  const handleTagClick = useCallback(
    (tag: string) => {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        if (newParams.get('tag') === tag) newParams.delete('tag');
        else newParams.set('tag', tag);
        return newParams;
      });
    },
    [setSearchParams]
  );

  const clearTagFilter = useCallback(() => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev);
      newParams.delete('tag');
      return newParams;
    });
  }, [setSearchParams]);

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
        <ForumErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title={`${category?.name ?? 'Forum'} · PlantID`}
        description={
          category?.description || `Browse discussions in ${category?.name ?? 'the forum'}.`
        }
      />
      {/* Breadcrumb — collection path, in the ledger's mono voice */}
      <nav className="wf-label mb-8" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" viewTransition className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="text-ink-2">
            {category?.name}
          </li>
        </ol>
      </nav>

      {/* Category Header */}
      <div className="mb-8">
        <p className="wf-label mb-2">
          Board
          {category?.thread_count != null && <> · {category.thread_count} topics</>}
        </p>
        <div className="flex items-baseline gap-3 mb-2">
          {category?.icon && (
            <span className="text-3xl" aria-hidden="true">
              {category.icon}
            </span>
          )}
          <h1 className="wf-title text-3xl sm:text-4xl text-ink">{category?.name}</h1>
        </div>

        {category?.description && (
          <p className="text-ink-2 max-w-prose leading-relaxed">{category.description}</p>
        )}
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
              className="flex-1 px-4 py-2 border border-line-2 rounded-xs focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink placeholder:text-ink-3"
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
            className="min-h-11 px-4 py-2 border border-line-2 rounded-xs focus:ring-2 focus:ring-primary bg-surface-2 text-ink"
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

      {/* Active tag filter (audit M5) — always visible while filtering, so an
          empty result reads as "this filter matched nothing" rather than "this
          board is empty". */}
      {activeTag && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xs border border-line bg-surface-2 px-4 py-3">
          <span className="wf-label">Filtered by tag</span>
          <span className="wf-label rounded-full border border-primary/50 bg-primary/10 px-3 py-1 text-primary">
            #{activeTag}
          </span>
          <button
            type="button"
            onClick={clearTagFilter}
            className="min-h-11 rounded-xs px-3 text-sm text-ink-3 hover:bg-surface-3"
          >
            Clear filter
          </button>
        </div>
      )}

      {/* Threads List */}
      {loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-ink-3">
          {activeTag ? (
            <>
              <p className="text-lg">No threads tagged #{activeTag}.</p>
              <p className="text-sm mt-2">Clear the filter to see the whole board.</p>
            </>
          ) : (
            <>
              <p className="text-lg">No threads found.</p>
              <p className="text-sm mt-2">Be the first to start a discussion!</p>
            </>
          )}
        </div>
      ) : (
        <div className="wf-ledger">
          {threads.map((thread) => (
            <ThreadCard
              key={thread.id}
              thread={thread}
              onTagClick={handleTagClick}
              activeTag={activeTag}
            />
          ))}
        </div>
      )}

      {/* Load More (cursor pagination). Honest remaining count from the board's
          topic_count when known; a bare label otherwise, never a fake "0 left"
          (audit M30 — the service used to hardcode meta.count to 0). The count is
          suppressed entirely while a tag filter is active: thread_count is the
          board's UNFILTERED total, so "380 remaining" on a 25-result filter would
          be exactly the dishonest number M30 removed. */}
      {nextCursor && !loading && (
        <div className="mt-8 text-center">
          <Button
            onClick={handleLoadMore}
            variant="outline"
            loading={loadingMore}
            disabled={loadingMore}
            className="min-h-11"
          >
            {loadingMore
              ? 'Loading...'
              : (() => {
                  if (activeTag) return 'Load More';
                  const remaining = Math.max(0, (category?.thread_count ?? 0) - threads.length);
                  return remaining > 0 ? `Load More (${remaining} remaining)` : 'Load More';
                })()}
          </Button>
        </div>
      )}
    </div>
  );
}
