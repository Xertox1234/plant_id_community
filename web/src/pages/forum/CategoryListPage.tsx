import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Layers, MessagesSquare, Reply } from 'lucide-react';
import { fetchForumIndex } from '../../services/forumService';
import { createSafeMarkup, SANITIZE_PRESETS } from '../../utils/sanitize';
import CategoryCard from '../../components/forum/CategoryCard';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import HeroCard from '../../components/ui/HeroCard';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import ButtonLink from '../../components/ui/ButtonLink';
import Timestamp from '../../components/ui/Timestamp';
import RailSlot from '../../components/layout/RailSlot';
import RailModule from '../../components/ui/RailModule';
import FromTheBlogModule from '../../components/forum/rail/FromTheBlogModule';
import PageMeta from '../../components/PageMeta';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import { categoryPath } from '../../utils/forumUrls';
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
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <ForumErrorState
          title="Error loading categories"
          message={error}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      </div>
    );
  }

  const totalThreads = categories.reduce((sum, c) => sum + (c.thread_count || 0), 0);
  const totalPosts = categories.reduce((sum, c) => sum + (c.post_count || 0), 0);
  const activeBoards = categories
    .filter((c) => c.last_post_at)
    .sort((a, b) => (b.last_post_at! > a.last_post_at! ? 1 : -1))
    .slice(0, 4);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <PageMeta
        title="Community Forum · Houseplant MD"
        description="Connect with fellow plant enthusiasts, share knowledge, and get help with your plants in the Houseplant MD community."
      />

      {/* HeroCard's title renders as an h2 by design — the page still needs
          exactly one h1 for the document outline. */}
      <h1 className="sr-only">Community forum</h1>

      <HeroCard
        eyebrow="Houseplant MD · Community"
        title="Ask the canopy"
        description="Get help with an ailing plant, show off a thriving one, and swap care notes with people who love the same leaves you do."
        actions={
          <>
            <ButtonLink to="/forum/new-thread" variant="primary">
              Start a thread
            </ButtonLink>
            <ButtonLink to="/forum/search" variant="ghost">
              Search the forum
            </ButtonLink>
          </>
        }
        art={
          <img
            src="/illustrations/hero-forum.webp"
            alt=""
            width={280}
            height={280}
            className="canopy-float w-[200px] md:w-[260px]"
          />
        }
      />

      {/* CMS welcome copy (audit L2) — an editor's own onboarding words.
          Sanitized here as well as on the server; gated on the SANITIZED html,
          not the raw string. */}
      {introMarkup.__html && (
        <div
          className="prose prose-sm mt-6 max-w-none text-ink-2"
          dangerouslySetInnerHTML={introMarkup}
        />
      )}

      {categories.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            icon={<Layers className="h-4 w-4" aria-hidden="true" />}
            value={categories.length}
            label="Boards"
            tone="sage"
          />
          <StatCard
            icon={<MessagesSquare className="h-4 w-4" aria-hidden="true" />}
            value={totalThreads}
            label="Threads"
            tone="pollen"
          />
          <StatCard
            icon={<Reply className="h-4 w-4" aria-hidden="true" />}
            value={totalPosts}
            label="Posts"
            tone="orchid"
          />
        </div>
      )}

      {categories.length === 0 ? (
        /* Empty state (audit L2): says what the forum is for and offers a way
           out, rather than "check back soon" — which reads as broken. */
        <Card className="mt-6 px-6 py-12 text-center">
          <p className="gt-h3 text-ink">No boards yet</p>
          <p className="mx-auto mt-2 max-w-prose text-sm text-ink-2">
            This community is just getting started. Boards are where plant questions, care tips and
            ID help get discussed — they&rsquo;ll show up here as soon as a moderator adds one.
          </p>
          <Link
            to="/identify"
            className="mt-4 inline-block text-sm font-medium text-primary transition-colors hover:text-primary/80"
          >
            Identify a plant in the meantime →
          </Link>
        </Card>
      ) : (
        <div className="mt-6 flex flex-col gap-3">
          {categories.map((category) => (
            <CategoryCard key={category.id} category={category} />
          ))}
        </div>
      )}

      <RailSlot>
        {activeBoards.length > 0 && (
          <RailModule icon={<Activity aria-hidden="true" />} title="Active now">
            <ul className="flex flex-col gap-3">
              {activeBoards.map((board) => (
                <li key={board.id}>
                  <Link to={categoryPath(board)} className="group block">
                    <span className="text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
                      {board.name}
                    </span>
                    <span className="gt-label mt-0.5 block normal-case tracking-normal">
                      <Timestamp iso={board.last_post_at!} prefix="Last activity" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </RailModule>
        )}
        <FromTheBlogModule />
      </RailSlot>
    </div>
  );
}
