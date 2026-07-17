import { useState, useEffect, useCallback, useMemo, useRef, ChangeEvent } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { searchForum, fetchCategories } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { logger } from '../../utils/logger';
import { sanitizeSearchQuery } from '../../utils/validation';
import { threadPath } from '../../utils/forumUrls';
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
      <mark key={`${part}-${index}`} className="bg-tertiary/30 rounded px-0.5">
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

  // Use ref for debounce timer to prevent memory leaks
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

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

    const performSearch = async () => {
      try {
        setLoading(true);
        setError(null);

        const results = await searchForum({ q: query, category });

        setSearchResults(results);
        logger.info('[SEARCH] Results loaded', {
          query,
          totalThreads: results.total_threads,
          totalPosts: results.total_posts,
        });
      } catch (err) {
        logger.error('Error performing search', {
          component: 'SearchPage',
          error: err,
          context: { query, category },
        });
        setError(err instanceof Error ? err.message : 'Search failed');
      } finally {
        setLoading(false);
      }
    };

    performSearch();
  }, [query, category]);

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

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => !!category, [category]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-ink mb-2">Forum Search</h1>
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
            className="w-full px-4 py-3 pl-12 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink"
            aria-label="Search query"
          />
          <svg
            className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-ink-3"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-surface-2 rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-ink">Filters</h2>
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
              className="w-full px-3 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink"
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
      </div>

      {/* Search Results */}
      {loading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <div className="bg-error/10 border border-error/30 rounded-lg p-4 mb-6">
          <p className="text-error">{error}</p>
        </div>
      )}

      {!loading && !error && !query && (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-ink-3 mb-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <p className="text-ink-2">Enter a search query to begin</p>
        </div>
      )}

      {!loading && !error && query && searchResults && (
        <div>
          {/* Results Summary */}
          <div className="mb-6">
            <p className="text-ink-2">
              Found <span className="font-semibold">{searchResults.total_threads}</span> thread(s)
              and <span className="font-semibold">{searchResults.total_posts}</span> post(s) for{' '}
              <span className="font-semibold">"{query}"</span>
            </p>
          </div>

          {/* Thread Results */}
          {searchResults.threads && searchResults.threads.length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-ink mb-4">
                Threads ({searchResults.total_threads})
              </h2>
              <div className="space-y-4">
                {searchResults.threads.map((thread) => (
                  <div key={thread.id}>
                    <ThreadCard thread={thread} hideAuthor />
                    {(hasSearchMatch(thread.title, query) ||
                      hasSearchMatch(thread.excerpt, query)) && (
                      <p
                        className="mt-2 text-sm text-ink-2 bg-tertiary/10 border border-tertiary/20 rounded-lg p-3"
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
              <h2 className="text-xl font-semibold text-ink mb-4">
                Posts ({searchResults.total_posts})
              </h2>
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
                    <div key={post.id} className="bg-surface-2 rounded-lg border border-line-2 p-4">
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
              <svg
                className="mx-auto h-12 w-12 text-ink-3 mb-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-ink-2 mb-2">No results found for "{query}"</p>
              <p className="text-ink-3 text-sm">Try different keywords or remove some filters</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
