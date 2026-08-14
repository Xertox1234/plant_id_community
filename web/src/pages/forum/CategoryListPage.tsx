import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { fetchForumIndex } from '../../services/forumService';
import { createSafeMarkup, SANITIZE_PRESETS } from '../../utils/sanitize';
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
  // CMS-authored welcome copy (ForumIndex.intro, audit L2). Sanitized
  // server-side too — this is the second layer, not the only one.
  const [intro, setIntro] = useState<string>('');
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

        const { categories: boards, intro: welcome } = await fetchForumIndex();
        if (ignore) return;
        setCategories(boards);
        setIntro(welcome);
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

  // Sanitize once so the render can gate on the result rather than the input.
  const introMarkup = useMemo(() => createSafeMarkup(intro, SANITIZE_PRESETS.STANDARD), [intro]);

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
        <p className="wf-label mb-2">Plant ID Community · Field Notes</p>
        <h1 className="wf-title text-3xl sm:text-4xl text-ink mb-2">Community Forums</h1>
        <p className="text-ink-2 max-w-prose leading-relaxed">
          Connect with fellow plant enthusiasts, share knowledge, and get help with your plants.
        </p>
        {/* CMS welcome copy (audit L2) — an editor's own onboarding words, which
            no hardcoded string can replace. Sanitized here as well as on the
            server; STANDARD matches the backend's intro allowlist (headings,
            lists, links — no media). Gated on the SANITIZED html, not the raw
            string: an intro made only of disallowed markup is truthy but
            sanitizes to '', which would render an empty padded box. */}
        {introMarkup.__html && (
          <div
            className="prose prose-sm max-w-none mt-4 text-ink-2"
            dangerouslySetInnerHTML={introMarkup}
          />
        )}
      </div>

      {/* Categories List */}
      {categories.length === 0 ? (
        /* Empty state (audit L2). A brand-new community lands here, so it says
           what the forum is for and offers a way out, rather than "check back
           soon" — which reads as broken. */
        <div className="wf-sheet text-center py-12 px-6">
          <p className="wf-title text-lg text-ink">No boards yet</p>
          <p className="text-sm mt-2 max-w-prose mx-auto text-ink-2">
            This community is just getting started. Boards are where plant questions, care tips and
            ID help get discussed — they&rsquo;ll show up here as soon as a moderator adds one.
          </p>
          <Link
            to="/identify"
            className="inline-block mt-4 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          >
            Identify a plant in the meantime →
          </Link>
        </div>
      ) : (
        <div className="wf-ledger">
          {categories.map((category) => (
            <CategoryCard key={category.id} category={category} />
          ))}
        </div>
      )}
    </div>
  );
}
