import { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Layers, MessagesSquare, Reply } from 'lucide-react';
import {
  fetchForumIndex,
  fetchRecentTopics,
  fetchMyStats,
  fetchEventHero,
} from '../../services/forumService';
import { createSafeMarkup, SANITIZE_PRESETS } from '../../utils/sanitize';
import CategoryCard from '../../components/forum/CategoryCard';
import SeasonStatsGrid from '../../components/forum/SeasonStatsGrid';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import HeroCard from '../../components/ui/HeroCard';
import StatCard from '../../components/ui/StatCard';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import ButtonLink from '../../components/ui/ButtonLink';
import Chip from '../../components/ui/Chip';
import RailSlot from '../../components/layout/RailSlot';
import CommunityExpertsModule from '../../components/forum/rail/CommunityExpertsModule';
import ActiveNowModule from '../../components/forum/rail/ActiveNowModule';
import FromTheBlogModule from '../../components/forum/rail/FromTheBlogModule';
import PageMeta from '../../components/PageMeta';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';
import { eventHeroTopicPath } from '../../utils/forumUrls';
import { boardIdentity } from '../../utils/forumTones';
import { resolveBoardFilter } from '../../utils/forumBoardFilter';
import type { Category, ForumMyStats, RecentTopic, EventHeroTopic } from '@/types';

// The landing rail's recent-activity fetch, passed through to
// ActiveNowModule (which re-slices its own display to 3 regardless of how
// many rows this carries). Previously inflated to 20 to keep a client-side
// event-hero inference from evicting a still-pinned topic out of the window
// — that inference is retired (todo 304, backend-owned event signal now),
// so this is back to a small display-only fetch.
const RECENT_TOPICS_FETCH_LIMIT = 5;

/**
 * CategoryListPage Component
 *
 * Forum homepage - displays all top-level categories.
 * Route: /forum
 */
export default function CategoryListPage() {
  useScrollToTop();
  const { isAuthenticated } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  // CMS-authored welcome copy (ForumIndex.intro, audit L2). Sanitized
  // server-side too — this is the second layer, not the only one.
  const [intro, setIntro] = useState<string>('');
  // The landing rail's recent-activity feed (ActiveNowModule).
  const [recentTopics, setRecentTopics] = useState<RecentTopic[]>([]);
  // The CMS-featured "Community event" hero (todo 304) — backend-owned, no
  // recency-window coupling. null covers "not fetched yet", "fetch failed",
  // and "no event currently featured"; all three render the evergreen hero.
  const [eventHero, setEventHero] = useState<EventHeroTopic | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Bumping this re-runs the load effect — drives both the initial fetch and
  // the error-state Retry, each run getting its own `ignore` cleanup flag.
  const [reloadKey, setReloadKey] = useState(0);
  // Client-side board filter for the chip row — null means "All".
  const [activeBoard, setActiveBoard] = useState<string | null>(null);
  // "Your season" — null covers both "not fetched yet" and "fetch failed",
  // both of which hide the row rather than erroring the page.
  const [myStats, setMyStats] = useState<ForumMyStats | null>(null);
  const boardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // react.dev's prescribed race guard: a stale response (unmount, or a retry
    // superseding an in-flight request) is dropped instead of setting state.
    let ignore = false;
    const loadCategories = async () => {
      try {
        setLoading(true);
        setError(null);

        const [{ categories: boards, intro: welcome }, recent, event] = await Promise.all([
          fetchForumIndex(),
          // ActiveNowModule's feed — a nice-to-have on top of the board
          // list, not a dependency of it, so a failure here must never
          // surface the page's error state.
          fetchRecentTopics(RECENT_TOPICS_FETCH_LIMIT).catch((err) => {
            logger.error('Error loading recent topics', {
              component: 'CategoryListPage',
              error: err,
            });
            return [];
          }),
          // The event hero (todo 304) — same "nice-to-have, never fails the
          // page" treatment. A fetch failure or {topic: null} both fall
          // through to the evergreen hero.
          fetchEventHero().catch((err) => {
            logger.error('Error loading event hero', {
              component: 'CategoryListPage',
              error: err,
            });
            return { topic: null };
          }),
        ]);
        if (ignore) return;
        setCategories(boards);
        setIntro(welcome);
        setRecentTopics(recent);
        setEventHero(event.topic);
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

  // "Your season" stats — a separate effect (and its own ignore guard) so an
  // unauthenticated visitor never triggers the auth-only request, and so a
  // failure here can never fail the board list above.
  useEffect(() => {
    let ignore = false;
    if (!isAuthenticated) {
      setMyStats(null);
      return;
    }
    fetchMyStats()
      .then((stats) => {
        if (!ignore) setMyStats(stats);
      })
      .catch((err) => {
        if (ignore) return;
        logger.error('Error loading forum stats', {
          component: 'CategoryListPage',
          error: err,
        });
        setMyStats(null);
      });
    return () => {
      ignore = true;
    };
  }, [isAuthenticated]);

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
  const { effectiveBoard, visibleCategories } = resolveBoardFilter(categories, activeBoard);

  // Same hero art either way — hoisted so both HeroCard branches share it.
  const heroArt = (
    <img
      src="/illustrations/hero-forum.webp"
      alt=""
      width={280}
      height={280}
      className="canopy-float w-[200px] md:w-[260px]"
    />
  );

  const scrollToBoards = () => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    boardsRef.current?.scrollIntoView({
      behavior: reduceMotion ? 'auto' : 'smooth',
      block: 'start',
    });
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <PageMeta
        title="Community Forum · Houseplant MD"
        description="Connect with fellow plant enthusiasts, share knowledge, and get help with your plants in the Houseplant MD community."
      />

      {/* HeroCard's title renders as an h2 by design — the page still needs
          exactly one h1 for the document outline. */}
      <h1 className="sr-only">Community forum</h1>

      {eventHero ? (
        <HeroCard
          eyebrow={eventHero.eyebrow}
          title={eventHero.title}
          description={eventHero.description}
          actions={
            <>
              <ButtonLink to={eventHeroTopicPath(eventHero)} variant="primary">
                Join the conversation
              </ButtonLink>
              <Button variant="ghost" onClick={scrollToBoards}>
                Browse boards
              </Button>
            </>
          }
          art={heroArt}
        />
      ) : (
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
          art={heroArt}
        />
      )}

      {/* CMS welcome copy (audit L2) — an editor's own onboarding words.
          Sanitized here as well as on the server; gated on the SANITIZED html,
          not the raw string. */}
      {introMarkup.__html && (
        <div
          className="prose prose-sm mt-6 max-w-none text-ink-2"
          dangerouslySetInnerHTML={introMarkup}
        />
      )}

      {isAuthenticated
        ? myStats && (
            <>
              <h2 className="gt-h3 mt-8">Your season</h2>
              <SeasonStatsGrid stats={myStats} className="mt-6" />
            </>
          )
        : categories.length > 0 && (
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

      <div ref={boardsRef}>
        <h2 className="gt-h3 mt-8">Boards</h2>

        {categories.length > 1 && (
          <div
            className="mt-6 flex flex-wrap items-center gap-2"
            role="group"
            aria-label="Filter boards"
          >
            <Chip
              // effectiveBoard rather than a bare `activeBoard === null`
              // check: a stale selection (its board no longer in the fetched
              // list) collapses to null here too, so "All" and the filtered
              // list below always agree about what's selected — identical to
              // the old check whenever activeBoard is genuinely null or
              // genuinely present.
              active={effectiveBoard === null}
              onClick={() => setActiveBoard(null)}
              className="min-h-11"
            >
              All
            </Chip>
            {categories.map((c) => (
              <Chip
                key={c.id}
                active={effectiveBoard === c.slug}
                onClick={() => setActiveBoard((prev) => (prev === c.slug ? null : c.slug))}
                className="min-h-11"
              >
                {boardIdentity(c.slug, c.name).chipLabel}
              </Chip>
            ))}
          </div>
        )}

        {categories.length === 0 ? (
          /* Empty state (audit L2): says what the forum is for and offers a way
             out, rather than "check back soon" — which reads as broken. */
          <Card className="mt-6 px-6 py-12 text-center">
            <p className="gt-h3 text-ink">No boards yet</p>
            <p className="mx-auto mt-2 max-w-prose text-sm text-ink-2">
              This community is just getting started. Boards are where plant questions, care tips
              and ID help get discussed — they&rsquo;ll show up here as soon as a moderator adds
              one.
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
            {visibleCategories.map((category) => (
              <CategoryCard key={category.id} category={category} />
            ))}
          </div>
        )}
      </div>

      <RailSlot>
        <CommunityExpertsModule />
        <ActiveNowModule topics={recentTopics} />
        <FromTheBlogModule />
      </RailSlot>
    </div>
  );
}
