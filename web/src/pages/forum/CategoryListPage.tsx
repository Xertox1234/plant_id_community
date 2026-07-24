import { useState, useEffect } from 'react';
import { fetchCategoryTree } from '../../services/forumService';
import CategoryCard from '../../components/forum/CategoryCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import PageMeta from '../../components/PageMeta';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import type { Category } from '@/types';

/**
 * CategoryListPage Component
 *
 * Forum homepage - displays all top-level categories.
 * Route: /forum
 */
export default function CategoryListPage() {
  useScrollToTop();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Bumping this re-runs the load effect — drives both the initial fetch and
  // the error-state Retry, each run getting its own `ignore` cleanup flag.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    // react.dev's prescribed race guard: a stale response (unmount, or a retry
    // superseding an in-flight request) is dropped instead of setting state.
    let ignore = false;
    const loadCategories = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await fetchCategoryTree();
        if (!ignore) setCategories(data);
      } catch (err) {
        if (ignore) return;
        logger.error('Error loading forum categories', {
          component: 'CategoryListPage',
          error: err,
        });
        setError(err instanceof Error ? err.message : 'Failed to load categories');
      } finally {
        if (!ignore) setLoading(false);
      }
    };

    loadCategories();
    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ForumErrorState
          title="Error loading categories"
          message={error}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title="Community Forums · PlantID"
        description="Connect with fellow plant enthusiasts, share knowledge, and get help with your plants in the Plant Community forums."
      />
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-ink mb-2">Community Forums</h1>
        <p className="text-lg text-ink-2">
          Connect with fellow plant enthusiasts, share knowledge, and get help with your plants.
        </p>
      </div>

      {/* Categories List */}
      {categories.length === 0 ? (
        <div className="text-center py-12 text-ink-3">
          <p className="text-lg">No categories available yet.</p>
          <p className="text-sm mt-2">Check back soon!</p>
        </div>
      ) : (
        <div className="space-y-4">
          {categories.map((category) => (
            <CategoryCard key={category.id} category={category} />
          ))}
        </div>
      )}
    </div>
  );
}
