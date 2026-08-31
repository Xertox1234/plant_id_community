import { useEffect, useRef, useState, useCallback, FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Flame, Search } from 'lucide-react';
import HeroCard from '../components/ui/HeroCard';
import Chip from '../components/ui/Chip';
import Button from '../components/ui/Button';
import ButtonLink from '../components/ui/ButtonLink';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { Pagination } from '../components/ui/Pagination';
import RailSlot from '../components/layout/RailSlot';
import RailModule from '../components/ui/RailModule';
import BlogCard from '../components/BlogCard';
import PageMeta from '../components/PageMeta';
import {
  fetchBlogPosts,
  fetchPopularPosts,
  fetchCategories,
  API_URL,
} from '../services/blogService';
import { logger } from '../utils/logger';
import { useScrollToTop } from '../hooks/useScrollToTop';
import type { BlogPost, BlogCategory } from '@/types';

const POSTS_PER_PAGE = 8; // 2-col grid → even pages

/**
 * BlogListPage — Canopy blog index (PR 3, spec §7).
 *
 * Locked hero copy (artifact parity) → chips + search toolbar → 2-col card
 * grid → Pagination. Rail: popular posts. Sort dropdown and category
 * sidebar retired (spec §2.2); search kept — no regressions.
 */
export default function BlogListPage() {
  useScrollToTop();
  const [searchParams, setSearchParams] = useSearchParams();
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [categories, setCategories] = useState<BlogCategory[]>([]);
  const [popular, setPopular] = useState<BlogPost[]>([]);
  const [latestSlug, setLatestSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const category = searchParams.get('category') || '';

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const { items, meta } = await fetchBlogPosts({
          page,
          limit: POSTS_PER_PAGE,
          search,
          category,
        });
        if (cancelled) return;
        setPosts(items);
        setTotalCount(meta.total_count);
      } catch (err) {
        if (cancelled) return;
        logger.error('Error loading blog posts', {
          component: 'BlogListPage',
          error: err,
          context: { page, search, category },
        });
        setError(err instanceof Error ? err.message : 'Failed to load blog posts');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [page, search, category]);

  useEffect(() => {
    let cancelled = false;
    const loadOnce = async () => {
      try {
        const [latest, popularPosts, cats] = await Promise.all([
          fetchBlogPosts({ page: 1, limit: 1 }),
          fetchPopularPosts({ limit: 5, days: 30 }),
          fetchCategories(),
        ]);
        if (cancelled) return;
        setLatestSlug(latest.items[0]?.slug ?? null);
        setPopular(popularPosts);
        setCategories(cats);
      } catch (err) {
        if (cancelled) return;
        // Rail/hero garnish only — the grid is the page; log and continue.
        logger.error('Error loading blog sidebar data', {
          component: 'BlogListPage',
          error: err,
        });
      }
    };
    loadOnce();
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollToGrid = useCallback(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    gridRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
  }, []);

  const setParam = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams);
      mutate(next);
      next.delete('page'); // any filter change resets to page 1
      setSearchParams(next);
    },
    [searchParams, setSearchParams]
  );

  const handleCategory = useCallback(
    (slug: string) => {
      setParam((p) => {
        if (slug) p.set('category', slug);
        else p.delete('category');
      });
    },
    [setParam]
  );

  const handleSearch = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const value = (new FormData(e.currentTarget).get('search') as string).trim();
      setParam((p) => {
        if (value) p.set('search', value);
        else p.delete('search');
      });
    },
    [setParam]
  );

  const clearFilters = useCallback(() => {
    setSearchParams({});
    scrollToGrid();
  }, [setSearchParams, scrollToGrid]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      const next = new URLSearchParams(searchParams);
      next.set('page', newPage.toString());
      setSearchParams(next);
      window.scrollTo({
        top: 0,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      });
    },
    [searchParams, setSearchParams]
  );

  const totalPages = Math.max(1, Math.ceil(totalCount / POSTS_PER_PAGE));
  const hasFilters = Boolean(search || category);

  return (
    <div className="flex flex-col gap-8">
      <PageMeta
        title="Blog — Houseplant MD"
        description="Guides, experiments, and honest failures from the community garden."
        rssFeedUrl={`${API_URL}/blog/rss/`}
        atomFeedUrl={`${API_URL}/blog/atom/`}
      />

      {/* HeroCard's title renders as an h2 by design — the page still needs
          its own h1 for the document outline. */}
      <h1 className="sr-only">Blog</h1>
      <HeroCard
        eyebrow="The blog · new posts weekly"
        title="Do less to your plants."
        description="Guides, experiments, and honest failures from the community garden. This month: why most houseplants are killed by kindness."
        actions={
          <>
            {latestSlug ? (
              <ButtonLink to={`/blog/${latestSlug}`}>Read the latest</ButtonLink>
            ) : (
              <Button onClick={scrollToGrid}>Read the latest</Button>
            )}
            <Button variant="ghost" onClick={clearFilters}>
              All topics →
            </Button>
          </>
        }
        art={
          <img
            src="/illustrations/hero-blog.webp"
            alt=""
            width={280}
            height={280}
            className="canopy-float w-[200px] md:w-[260px]"
          />
        }
      />

      {/* Toolbar: category chips + search (spec §2.2 — search kept). */}
      <div
        ref={gridRef}
        className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      >
        <div className="flex flex-wrap gap-2">
          <Chip active={!category} onClick={() => handleCategory('')}>
            All
          </Chip>
          {categories.map((cat) => (
            <Chip
              key={cat.id}
              active={category === cat.slug}
              onClick={() => handleCategory(cat.slug)}
            >
              {cat.name}
            </Chip>
          ))}
        </div>
        <form onSubmit={handleSearch} className="relative md:w-64" role="search">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3"
          />
          <input
            key={search}
            type="search"
            name="search"
            defaultValue={search}
            aria-label="Search articles"
            placeholder="Search articles…"
            className="w-full rounded-pill border border-line bg-surface-2/60 py-2 pl-10 pr-4 text-[13px] text-ink placeholder:text-ink-3 transition-colors hover:bg-surface-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
          />
        </form>
      </div>

      {/* Active-search count + clear (spec §7). */}
      {hasFilters && !loading && !error && (
        <div className="flex items-center gap-3 font-mono text-[12px] text-ink-3">
          <span>
            {totalCount} {totalCount === 1 ? 'article' : 'articles'}
            {search && <> for “{search}”</>}
          </span>
          <button
            type="button"
            onClick={clearFilters}
            className="text-ink-2 underline underline-offset-2 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
          >
            Clear filters
          </button>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <div className="rounded-md border border-error/30 bg-error/10 p-6 text-center text-[13.5px] text-error">
          Couldn’t load the blog — {error}
        </div>
      )}

      {!loading && !error && posts.length === 0 && (
        <div className="canopy-card rounded-md p-10 text-center">
          <p className="text-[15px] font-semibold text-ink">No articles found</p>
          <p className="mt-1 text-[13.5px] text-ink-2">
            Try a different search, or browse every topic.
          </p>
          {hasFilters && (
            <Button variant="outline" className="mt-4" onClick={clearFilters}>
              Clear all filters
            </Button>
          )}
        </div>
      )}

      {!loading && !error && posts.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {posts.map((p) => (
              <BlogCard key={p.id} post={p} />
            ))}
          </div>
          {totalPages > 1 && (
            <Pagination
              page={page}
              onPageChange={handlePageChange}
              hasPrevious={page > 1}
              hasNext={page < totalPages}
              totalPages={totalPages}
            />
          )}
        </>
      )}

      {popular.length > 0 && (
        <RailSlot>
          <RailModule icon={<Flame />} title="Popular this month">
            <div className="flex flex-col gap-1.5">
              {popular.map((p) => (
                <BlogCard key={p.id} post={p} compact />
              ))}
            </div>
          </RailModule>
        </RailSlot>
      )}
    </div>
  );
}
