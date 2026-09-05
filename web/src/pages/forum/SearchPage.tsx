import { useState, useEffect, useCallback, useMemo, useRef, ChangeEvent } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Search, SearchX } from 'lucide-react';
import { searchForum, fetchCategories } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import PlantCareAskPanel from '../../components/forum/PlantCareAskPanel';
import { SearchResultsSkeleton } from '../../components/forum/ForumSkeleton';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import { logger } from '../../utils/logger';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { sanitizeSearchQuery } from '../../utils/validation';
import { threadPath } from '../../utils/forumUrls';
import PageMeta from '../../components/PageMeta';
import type { Category, SearchForumResponse } from '@/types';

/** Strip HTML tags from a string, returning plain text. */
function stripTags(html: string): string {
  return html.replace(/<[^>]*>/g, '');
}

function highlightText(text: string | undefined, query: string) {
  if (!text || !query.trim()) return text || '';

  const terms = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (terms.length === 0) return text;

  const regex = new RegExp(`(${terms.join('|')})`, 'gi');
  return text.split(regex).map((part, index) =>
    new RegExp(`^(${terms.join('|')})$`, 'i').test(part) ? (
      <mark key={`${part}-${index}`} className="bg-tertiary/30 rounded-xs px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function hasSearchMatch(text: string | undefined, query: string): boolean {
  if (!text || !query.trim()) return false;

  return query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .some((term) => text.toLowerCase().includes(term.toLowerCase()));
}

/**
 * SearchPage Component
 *
 * Full-text search across forum threads and posts with filters.
 * Route: /forum/search
 *
 * Features:
 * - Debounced search input (300ms)
 * - Category filter (board slug)
 * - Separate results for threads and posts
 * - Search term highlighting in results
 */
export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchResults, setSearchResults] = useState<SearchForumResponse | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState<string>('');
  // 1-based page across both result sections; Load More bumps it and appends.
  const [page, setPage] = useState<number>(1);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);

  // Use ref for debounce timer to prevent memory leaks
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Generation guard: a new query/category bumps this; a stale in-flight
  // performSearch or Load More re-checks it and drops its response so it can't
  // append the old query's results onto the new query's list or desync `page`.
  const announce = useAnnounce();
  const searchGenRef = useRef(0);

  // Get search params. Sanitize the query (strip control chars, cap length) as
  // client-side defense-in-depth — covers both the typed input and a direct
  // ?q=... URL before it reaches state, the API, or the rendered "results for".
  const query = sanitizeSearchQuery(searchParams.get('q') || '');
  const category = searchParams.get('category') || '';

  // Initialize search input from URL
  useEffect(() => {
    if (query) {
      setSearchInput(query);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load categories for filter dropdown
  useEffect(() => {
    const loadCategories = async () => {
      try {
        // fetchCategories already unwraps pagination to a flat Category[]; guard
        // with Array.isArray rather than the prior `as unknown as` double cast.
        const data = await fetchCategories();
        setCategories(Array.isArray(data) ? data : []);
      } catch (err) {
        logger.error('Error loading categories', {
          component: 'SearchPage',
          error: err,
        });
      }
    };

    loadCategories();
  }, []);

  // Perform search when query changes
  useEffect(() => {
    if (!query) {
      setSearchResults(null);
      return;
    }

    const gen = ++searchGenRef.current;
    const performSearch = async () => {
      try {
        setLoading(true);
        setLoadingMore(false); // a new query supersedes any in-flight Load More
        setError(null);
        setPage(1);

        const results = await searchForum({ q: query, category, page: 1 });
        if (searchGenRef.current !== gen) return;

        setSearchResults(results);
        logger.info('[SEARCH] Results loaded', {
          query,
          totalThreads: results.total_threads,
          totalPosts: results.total_posts,
        });
      } catch (err) {
        if (searchGenRef.current !== gen) return;
        logger.error('Error performing search', {
          component: 'SearchPage',
          error: err,
          context: { query, category },
        });
        const message = err instanceof Error ? err.message : 'Search failed';
        setError(message);
        // The banner is conditionally mounted, so it is never announced on
        // its own (audit 2026-09-04 M4).
        announce(message, 'assertive');
      } finally {
        if (searchGenRef.current === gen) setLoading(false);
      }
    };

    performSearch();
  }, [query, category, announce]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Handle search input with debouncing
  const handleSearchInput = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setSearchInput(value);

      // Clear existing timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // Set new timer
      debounceTimerRef.current = setTimeout(() => {
        if (value.trim()) {
          setSearchParams((prev) => {
            const newParams = new URLSearchParams(prev);
            newParams.set('q', value.trim());
            return newParams;
          });
        } else {
          setSearchParams((prev) => {
            const newParams = new URLSearchParams(prev);
            newParams.delete('q');
            return newParams;
          });
        }
      }, 300); // 300ms debounce
    },
    [setSearchParams]
  );

  // Handle filter changes
  const handleCategoryFilter = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        if (value) {
          newParams.set('category', value);
        } else {
          newParams.delete('category');
        }
        return newParams;
      });
    },
    [setSearchParams]
  );

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setSearchParams({ q: query });
  }, [query, setSearchParams]);

  // Append the next page of results. Both sections share one page counter; a
  // section that's already exhausted simply contributes nothing on the next page.
  const handleLoadMore = useCallback(async () => {
    if (!query || loadingMore) return;
    const nextPage = page + 1;
    const gen = searchGenRef.current;
    try {
      setLoadingMore(true);
      setError(null);
      const more = await searchForum({ q: query, category, page: nextPage });
      if (searchGenRef.current !== gen) return; // a newer query superseded us
      setSearchResults((prev) => {
        if (!prev) return more;
        // Dedup by id on append: offset pagination over ranked results can drift
        // if a topic/post is created or deleted between page fetches, so the same
        // row could reappear on a later page (wagtail-reviewer). Drop repeats.
        const seenThreads = new Set(prev.threads.map((t) => t.id));
        const seenPosts = new Set(prev.posts.map((p) => p.id));
        const newThreads = more.threads.filter((t) => !seenThreads.has(t.id));
        const newPosts = more.posts.filter((p) => !seenPosts.has(p.id));
        return {
          ...more,
          threads: [...prev.threads, ...newThreads],
          posts: [...prev.posts, ...newPosts],
          total_threads: prev.total_threads + newThreads.length,
          total_posts: prev.total_posts + newPosts.length,
        };
      });
      setPage(nextPage);
    } catch (err) {
      if (searchGenRef.current !== gen) return;
      logger.error('Error loading more search results', {
        component: 'SearchPage',
        error: err,
        context: { query, category, page: nextPage },
      });
      const message = err instanceof Error ? err.message : 'Search failed';
      setError(message);
      // The banner is conditionally mounted, so it is never announced on
      // its own (audit 2026-09-04 M4).
      announce(message, 'assertive');
    } finally {
      if (searchGenRef.current === gen) setLoadingMore(false);
    }
  }, [query, category, page, loadingMore, announce]);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => !!category, [category]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title={query ? `Search: ${query} · Houseplant MD` : 'Forum Search · Houseplant MD'}
        description="Search across Houseplant MD community threads and posts."
      />
      {/* Header */}
      <div className="mb-8">
        <p className="gt-label mb-2">Houseplant MD · Community</p>
        <h1 className="gt-h1 text-ink mb-2">Forum Search</h1>
        <p className="text-ink-2">Search across threads and posts</p>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <input
            type="text"
            value={searchInput}
            onChange={handleSearchInput}
            placeholder="Search forum..."
            className="w-full rounded-pill border border-line bg-surface-2/60 px-4 py-3 pl-12 text-ink transition-colors placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none"
            aria-label="Search query"
          />
          <Search
            className="absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-ink-3"
            aria-hidden="true"
          />
        </div>
      </div>

      {/* Opt-in RAG plant-care answer (todo 289 / M13) — never fired by a search. */}
      <PlantCareAskPanel initialQuestion={query} />

      {/* Filters */}
      <Card className="mb-6 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="gt-h3 text-ink">Filters</h2>
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-sm text-primary hover:text-primary/80"
            >
              Clear filters
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Category Filter */}
          <div>
            <label htmlFor="category-filter" className="block text-sm font-medium text-ink-2 mb-2">
              Category
            </label>
            <select
              id="category-filter"
              value={category}
              onChange={handleCategoryFilter}
              className="w-full rounded-sm border border-line bg-surface-2/60 px-3 py-2 text-ink focus:ring-2 focus:ring-secondary focus:outline-none"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.slug}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Search Results */}
      {loading && <SearchResultsSkeleton />}

      {error && (
        <div className="bg-error/10 border border-error/30 rounded-md p-4 mb-6">
          <p className="text-error">{error}</p>
        </div>
      )}

      {!loading && !error && !query && (
        <div className="text-center py-12">
          <Search className="mx-auto h-12 w-12 text-ink-3 mb-4" aria-hidden="true" />
          <p className="text-ink-2">Enter a search query to begin</p>
        </div>
      )}

      {!loading && !error && query && searchResults && (
        <div>
          {/* Results Summary */}
          <div className="mb-6">
            <p className="text-ink-2">
              Showing <span className="font-semibold">{searchResults.total_threads}</span> thread(s)
              and <span className="font-semibold">{searchResults.total_posts}</span> post(s) for{' '}
              <span className="font-semibold">"{query}"</span>
              {(searchResults.has_more_threads || searchResults.has_more_posts) && ' (more below)'}
            </p>
          </div>

          {/* Thread Results */}
          {searchResults.threads && searchResults.threads.length > 0 && (
            <div className="mb-8">
              <h2 className="gt-h3 text-ink mb-4">Threads ({searchResults.total_threads})</h2>
              <div className="flex flex-col gap-3">
                {searchResults.threads.map((thread) => (
                  <div key={thread.id} className="flex flex-col gap-1.5">
                    <ThreadCard thread={thread} hideAuthor />
                    {(hasSearchMatch(thread.title, query) ||
                      hasSearchMatch(thread.excerpt, query)) && (
                      <p
                        className="rounded-sm border border-tertiary/25 bg-tertiary/10 p-3 text-sm text-ink-2"
                        aria-label="Highlighted thread match"
                      >
                        {highlightText(thread.title, query)}
                        {thread.excerpt && <span> — {highlightText(thread.excerpt, query)}</span>}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Post Results */}
          {searchResults.posts && searchResults.posts.length > 0 && (
            <div className="mb-8">
              <h2 className="gt-h3 text-ink mb-4">Posts ({searchResults.total_posts})</h2>
              <div className="space-y-4">
                {searchResults.posts.map((post) => {
                  // content_raw holds the backend excerpt (may contain truncated HTML tags).
                  // Strip tags so we render plain text only — never dangerouslySetInnerHTML.
                  const plainExcerpt = stripTags(post.content_raw);
                  // Build a real thread link from the board/topic identity carried by
                  // mapSearchPostToPost, deep-linked to the specific post.
                  const topicLink =
                    post.board_id != null && post.board_slug && post.topic_slug
                      ? `${threadPath(
                          {
                            id: String(post.board_id),
                            slug: post.board_slug,
                            name: post.board_slug,
                          },
                          { id: post.thread, slug: post.topic_slug, title: post.topic_title || '' }
                        )}#post-${post.id}`
                      : `/forum`;
                  return (
                    <div key={post.id} className="canopy-card rounded-md p-4">
                      <Link
                        to={topicLink}
                        className="text-base font-semibold text-primary hover:underline"
                        aria-label={`Go to topic: ${post.topic_title || 'View topic'}`}
                      >
                        {highlightText(post.topic_title || 'View topic', query)}
                      </Link>
                      {plainExcerpt && (
                        <p className="mt-2 text-sm text-ink-2" aria-label="Highlighted post match">
                          {highlightText(plainExcerpt, query)}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* No Results */}
          {searchResults.total_threads === 0 && searchResults.total_posts === 0 && (
            <div className="text-center py-12">
              <SearchX className="mx-auto h-12 w-12 text-ink-3 mb-4" aria-hidden="true" />
              <p className="text-ink-2 mb-2">No results found for "{query}"</p>
              <p className="text-ink-3 text-sm">Try different keywords or remove some filters</p>
            </div>
          )}

          {/* Load More (honest pagination — no silent cap) */}
          {(searchResults.has_more_threads || searchResults.has_more_posts) && (
            <div className="mt-4 text-center">
              <Button
                onClick={handleLoadMore}
                variant="outline"
                loading={loadingMore}
                disabled={loadingMore}
                className="min-h-11"
              >
                {loadingMore ? 'Loading…' : 'Load more results'}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
