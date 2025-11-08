import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { fetchThreads, fetchCategory } from '../../services/forumService';
import ThreadCard from '../../components/forum/ThreadCard';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { logger } from '../../utils/logger';

/**
 * ThreadListPage Component
 *
 * Displays threads in a category with search, filters, and pagination.
 * Route: /forum/:categorySlug
 */
export default function ThreadListPage() {
  const { categorySlug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [category, setCategory] = useState(null);
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalCount, setTotalCount] = useState(0);

  // Get search params
  const page = parseInt(searchParams.get('page') || '1', 10);
  const search = searchParams.get('search') || '';
  const ordering = searchParams.get('order') || '-last_activity_at';

  const limit = 20;

  // Load category and threads
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load category info and threads in parallel
        const [categoryData, threadsData] = await Promise.all([
          fetchCategory(categorySlug),
          fetchThreads({
            category: categorySlug,
            page,
            limit,
            search,
            ordering
          }),
        ]);

        setCategory(categoryData);
        setThreads(threadsData.items);
        setTotalCount(threadsData.meta.count);
      } catch (err) {
        logger.error('Error loading thread list data', {
          component: 'ThreadListPage',
          error: err,
          context: { categorySlug, page, search },
        });
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [categorySlug, page, search, ordering]);

  // Handle search form submission
  const handleSearch = useCallback((e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const searchQuery = formData.get('search');

    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      if (searchQuery) {
        newParams.set('search', searchQuery);
      } else {
        newParams.delete('search');
      }
      newParams.set('page', '1'); // Reset to page 1
      return newParams;
    });
  }, [setSearchParams]);

  // Handle ordering change
  const handleOrderChange = useCallback((e) => {
    const newOrder = e.target.value;
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('order', newOrder);
      newParams.set('page', '1'); // Reset to page 1
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

  // Calculate pagination
  const totalPages = useMemo(() => {
    return Math.ceil(totalCount / limit);
  }, [totalCount, limit]);

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
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-gray-600" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-green-600">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-gray-900">
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
          <h1 className="text-4xl font-bold text-gray-900">
            {category?.name}
          </h1>
        </div>

        {category?.description && (
          <p className="text-lg text-gray-600">
            {category.description}
          </p>
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
              placeholder="Search threads..."
              defaultValue={search}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
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
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
          >
            <option value="-last_activity_at">Recent Activity</option>
            <option value="-created_at">Newest First</option>
            <option value="created_at">Oldest First</option>
            <option value="-view_count">Most Viewed</option>
            <option value="-post_count">Most Replies</option>
          </select>

          <Link to={`/forum/new-thread?category=${categorySlug}`}>
            <Button variant="primary">
              + New Thread
            </Button>
          </Link>
        </div>
      </div>

      {/* Active Filters */}
      {search && (
        <div className="mb-4 flex items-center gap-2">
          <span className="text-sm text-gray-600">
            Searching for: <strong>{search}</strong>
          </span>
          <button
            onClick={() => {
              setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                newParams.delete('search');
                newParams.set('page', '1');
                return newParams;
              });
            }}
            className="text-sm text-red-600 hover:text-red-700 underline"
          >
            Clear
          </button>
        </div>
      )}

      {/* Threads List */}
      {loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No threads found.</p>
          <p className="text-sm mt-2">
            {search ? 'Try a different search query.' : 'Be the first to start a discussion!'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {threads.map(thread => (
            <ThreadCard key={thread.id} thread={thread} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-8 flex justify-center items-center gap-2">
          <Button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            variant="outline"
          >
            Previous
          </Button>

          <span className="px-4 py-2 text-gray-700">
            Page {page} of {totalPages}
          </span>

          <Button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            variant="outline"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
