import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router';
import { searchForum, fetchCategories } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import PostCard from '../../components/forum/PostCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { logger } from '../../utils/logger';

/**
 * SearchPage Component
 *
 * Full-text search across forum threads and posts with filters.
 * Route: /forum/search
 *
 * Features:
 * - Debounced search input (500ms)
 * - Category, author, date range filters
 * - Separate results for threads and posts
 * - Pagination
 * - Search term highlighting in results
 */
export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchResults, setSearchResults] = useState(null);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchInput, setSearchInput] = useState('');
  const [debounceTimer, setDebounceTimer] = useState(null);

  // Get search params
  const query = searchParams.get('q') || '';
  const category = searchParams.get('category') || '';
  const author = searchParams.get('author') || '';
  const dateFrom = searchParams.get('date_from') || '';
  const dateTo = searchParams.get('date_to') || '';
  const page = parseInt(searchParams.get('page') || '1', 10);
  const pageSize = parseInt(searchParams.get('page_size') || '20', 10);

  // Initialize search input from URL
  useEffect(() => {
    if (query) {
      setSearchInput(query);
    }
  }, []);

  // Load categories for filter dropdown
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const data = await fetchCategories();
        setCategories(data.results || []);
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

        const results = await searchForum({
          q: query,
          category,
          author,
          date_from: dateFrom,
          date_to: dateTo,
          page,
          page_size: pageSize,
        });

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
          context: { query, category, author },
        });
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    performSearch();
  }, [query, category, author, dateFrom, dateTo, page, pageSize]);

  // Handle search input with debouncing
  const handleSearchInput = useCallback((e) => {
    const value = e.target.value;
    setSearchInput(value);

    // Clear existing timer
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    // Set new timer
    const timer = setTimeout(() => {
      if (value.trim()) {
        setSearchParams(prev => {
          const newParams = new URLSearchParams(prev);
          newParams.set('q', value.trim());
          newParams.set('page', '1'); // Reset to page 1
          return newParams;
        });
      } else {
        setSearchParams(prev => {
          const newParams = new URLSearchParams(prev);
          newParams.delete('q');
          return newParams;
        });
      }
    }, 500); // 500ms debounce

    setDebounceTimer(timer);
  }, [debounceTimer, setSearchParams]);

  // Handle filter changes
  const handleCategoryFilter = useCallback((e) => {
    const value = e.target.value;
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      if (value) {
        newParams.set('category', value);
      } else {
        newParams.delete('category');
      }
      newParams.set('page', '1');
      return newParams;
    });
  }, [setSearchParams]);

  const handleAuthorFilter = useCallback((e) => {
    const value = e.target.value;
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      if (value) {
        newParams.set('author', value);
      } else {
        newParams.delete('author');
      }
      newParams.set('page', '1');
      return newParams;
    });
  }, [setSearchParams]);

  // Handle pagination
  const handlePageChange = useCallback((newPage) => {
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('page', newPage.toString());
      return newParams;
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [setSearchParams]);

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setSearchParams({ q: query });
  }, [query, setSearchParams]);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(category || author || dateFrom || dateTo);
  }, [category, author, dateFrom, dateTo]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Forum Search
        </h1>
        <p className="text-gray-600">
          Search across threads and posts
        </p>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <input
            type="text"
            value={searchInput}
            onChange={handleSearchInput}
            placeholder="Search forum..."
            className="w-full px-4 py-3 pl-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            aria-label="Search query"
          />
          <svg
            className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400"
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
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-sm text-green-600 hover:text-green-700"
            >
              Clear filters
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Category Filter */}
          <div>
            <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-2">
              Category
            </label>
            <select
              id="category-filter"
              value={category}
              onChange={handleCategoryFilter}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            >
              <option value="">All Categories</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.slug}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          {/* Author Filter */}
          <div>
            <label htmlFor="author-filter" className="block text-sm font-medium text-gray-700 mb-2">
              Author
            </label>
            <input
              id="author-filter"
              type="text"
              value={author}
              onChange={handleAuthorFilter}
              placeholder="Username"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Search Results */}
      {loading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner size="large" />
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {!loading && !error && !query && (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400 mb-4"
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
          <p className="text-gray-600">Enter a search query to begin</p>
        </div>
      )}

      {!loading && !error && query && searchResults && (
        <div>
          {/* Results Summary */}
          <div className="mb-6">
            <p className="text-gray-700">
              Found{' '}
              <span className="font-semibold">{searchResults.total_threads}</span>{' '}
              thread(s) and{' '}
              <span className="font-semibold">{searchResults.total_posts}</span>{' '}
              post(s) for{' '}
              <span className="font-semibold">"{query}"</span>
            </p>
          </div>

          {/* Thread Results */}
          {searchResults.threads && searchResults.threads.length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Threads ({searchResults.total_threads})
              </h2>
              <div className="space-y-4">
                {searchResults.threads.map(thread => (
                  <ThreadCard key={thread.id} thread={thread} />
                ))}
              </div>
            </div>
          )}

          {/* Post Results */}
          {searchResults.posts && searchResults.posts.length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Posts ({searchResults.total_posts})
              </h2>
              <div className="space-y-4">
                {searchResults.posts.map(post => (
                  <PostCard key={post.id} post={post} />
                ))}
              </div>
            </div>
          )}

          {/* No Results */}
          {searchResults.total_threads === 0 && searchResults.total_posts === 0 && (
            <div className="text-center py-12">
              <svg
                className="mx-auto h-12 w-12 text-gray-400 mb-4"
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
              <p className="text-gray-600 mb-2">No results found for "{query}"</p>
              <p className="text-gray-500 text-sm">Try different keywords or remove some filters</p>
            </div>
          )}

          {/* Pagination */}
          {(searchResults.has_next_threads || searchResults.has_next_posts || page > 1) && (
            <div className="flex justify-center gap-2 mt-8">
              <Button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
                variant="secondary"
              >
                Previous
              </Button>
              <span className="px-4 py-2 text-gray-700">
                Page {page}
              </span>
              <Button
                onClick={() => handlePageChange(page + 1)}
                disabled={!searchResults.has_next_threads && !searchResults.has_next_posts}
                variant="secondary"
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
