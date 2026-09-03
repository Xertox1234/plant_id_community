import type { ReactNode } from 'react';
import Card from '../ui/Card';

/**
 * ForumSkeleton — pulse-block loading states for the forum pages.
 *
 * Each page composition renders exactly ONE `role="status"` root
 * (SkeletonStatus): the page tests query `getByRole('status')`, which throws
 * on zero or multiple matches. The blocks inside are decorative and hidden
 * from assistive tech. Only the loaded page's UNCONDITIONAL structure is
 * mirrored — auth-gated or data-gated chrome (bookmark/follow buttons,
 * reaction bars, tag chips, subcategory pills, the reply composer, the rail)
 * is left out so the skeleton never promises something the loaded page may
 * not show. No skeleton renders a heading: e2e/forum-responsive.spec.ts gates
 * its overflow check on the loaded page's h1.
 *
 * Widths are fluid (fractions, w-full + max-w-*) so nothing can overflow at
 * 375px. Cards reuse <Card> so the chrome is pixel-identical to the loaded
 * cards and only the content pulses.
 */

type Radius = 'xs' | 'sm' | 'md' | 'lg' | 'pill';

// Radius is a prop, not part of className, so two rounded-* utilities can
// never land on the same element (stylesheet order, not class order, would
// decide the winner). Full class names keep Tailwind's scanner happy.
const RADIUS: Record<Radius, string> = {
  xs: 'rounded-xs',
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  pill: 'rounded-pill',
};

const BOARD_ROWS = 4;
const THREAD_ROWS = 5;
const POST_ROWS = 3;
const SEARCH_ROWS = 4;
const SORT_CHIPS = 5;

interface SkeletonBlockProps {
  /** Size/shape utilities only: h-*, w-*, max-w-*, margins, flex-none. */
  className?: string;
  rounded?: Radius;
}

/** The pulse primitive. Text lines: h-3 (mono label), h-4 (body), h-5 (h3), h-8 (h1). */
export function SkeletonBlock({ className = '', rounded = 'xs' }: SkeletonBlockProps) {
  return (
    <div className={`bg-surface-3 motion-safe:animate-pulse ${RADIUS[rounded]} ${className}`} />
  );
}

interface SkeletonStatusProps {
  children: ReactNode;
  /** Screen-reader text. */
  label?: string;
}

/**
 * The accessible root. `role="status"` is what the page tests query, so this
 * node must NOT be aria-hidden — only the decorative container below it is.
 */
export function SkeletonStatus({ children, label = 'Loading…' }: SkeletonStatusProps) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

/* ───────── shapes ───────── */

/** Mirrors ThreadCard (non-compact, no state chips/tags): title, 2-line excerpt, stat row. */
export function ThreadCardSkeleton() {
  return (
    <Card className="p-card">
      <SkeletonBlock className="mb-1.5 h-5 w-3/4" />
      <SkeletonBlock className="h-4 w-full max-w-prose" />
      <SkeletonBlock className="mt-2 h-4 w-5/6 max-w-prose" />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SkeletonBlock className="h-3 w-20" />
        <SkeletonBlock className="h-3 w-10" />
        <SkeletonBlock className="h-3 w-10" />
        <SkeletonBlock className="h-3 w-28" />
      </div>
    </Card>
  );
}

/** Mirrors PostCard: avatar + name/timestamp, three body lines. */
export function PostCardSkeleton() {
  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <SkeletonBlock rounded="sm" className="h-[38px] w-[38px] flex-none" />
        <div className="min-w-0 flex-1">
          <SkeletonBlock className="h-4 w-32 max-w-full" />
          <SkeletonBlock className="mt-1.5 h-3 w-24 max-w-full" />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <SkeletonBlock className="h-4 w-full" />
        <SkeletonBlock className="h-4 w-11/12" />
        <SkeletonBlock className="h-4 w-2/3" />
      </div>
    </Card>
  );
}

/** Mirrors CategoryCard (no subcategory chips): tile, name, 2-line description, stat row. */
export function CategoryCardSkeleton() {
  return (
    <Card className="p-card">
      <div className="flex items-start gap-4">
        <SkeletonBlock rounded="sm" className="h-[46px] w-[46px] flex-none" />
        <div className="min-w-0 flex-1">
          <SkeletonBlock className="h-5 w-2/5" />
          <SkeletonBlock className="mt-2 h-4 w-full max-w-prose" />
          <SkeletonBlock className="mt-2 h-4 w-3/4 max-w-prose" />
          <SkeletonBlock className="mt-3 h-3 w-1/2" />
        </div>
      </div>
    </Card>
  );
}

/* ───────── page compositions (one status root each) ───────── */

/** CategoryListPage first paint: hero, anonymous 3-up stats, "Boards" heading, chips, rows. */
export function CategoryListSkeleton() {
  return (
    <SkeletonStatus>
      {/* HeroCard: same Card classes, copy column + art column */}
      <Card className="rounded-lg p-8 md:p-10">
        <div className="grid items-center gap-8 md:grid-cols-[1.25fr_0.75fr]">
          <div className="flex flex-col items-start gap-3.5">
            <SkeletonBlock className="h-3 w-40 max-w-full" />
            <SkeletonBlock className="h-8 w-3/4 md:h-10" />
            <SkeletonBlock className="h-4 w-full max-w-[44ch]" />
            <SkeletonBlock className="h-4 w-2/3 max-w-[44ch]" />
            <div className="mt-2 flex flex-wrap gap-2.5">
              <SkeletonBlock rounded="pill" className="h-11 w-36" />
              <SkeletonBlock rounded="pill" className="h-11 w-36" />
            </div>
          </div>
          <SkeletonBlock
            rounded="lg"
            className="aspect-square w-full max-w-[200px] justify-self-start md:max-w-[260px] md:justify-self-end"
          />
        </div>
      </Card>

      {/* StatCard ×3 — the anonymous grid; the signed-in 4-up grid has its own fetch */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Card key={i} className="flex flex-col gap-3 p-card">
            <SkeletonBlock rounded="sm" className="h-9 w-9" />
            <div>
              <SkeletonBlock className="h-6 w-16" />
              <SkeletonBlock className="mt-1.5 h-3 w-20" />
            </div>
          </Card>
        ))}
      </div>

      {/* "Boards" heading, filter chips, board rows */}
      <SkeletonBlock className="mt-8 h-5 w-24" />
      <div className="mt-6 flex flex-wrap items-center gap-2">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonBlock key={i} rounded="pill" className="h-11 w-24" />
        ))}
      </div>
      <div className="mt-6 flex flex-col gap-3">
        {Array.from({ length: BOARD_ROWS }, (_, i) => (
          <CategoryCardSkeleton key={i} />
        ))}
      </div>
    </SkeletonStatus>
  );
}

interface ThreadListSkeletonProps {
  /**
   * First load: also mirror the breadcrumb, board header and toolbar.
   * List-only reloads (sort / tag / search) keep the real chrome mounted.
   */
  withHeader?: boolean;
}

/** ThreadListPage: optional board chrome, then thread rows. */
export function ThreadListSkeleton({ withHeader = false }: ThreadListSkeletonProps) {
  return (
    <SkeletonStatus>
      {withHeader && (
        <>
          {/* Breadcrumb */}
          <SkeletonBlock className="mb-6 h-3 w-40 max-w-full" />

          {/* Board header: tile, name, description, thread count */}
          <div className="mb-6 flex items-start gap-4">
            <SkeletonBlock rounded="sm" className="h-[46px] w-[46px] flex-none" />
            <div className="min-w-0 flex-1">
              <SkeletonBlock className="h-8 w-1/2" />
              <SkeletonBlock className="mt-2.5 h-4 w-full max-w-prose" />
              <SkeletonBlock className="mt-3 h-3 w-24" />
            </div>
          </div>

          {/* Toolbar: search pill + New Thread, then the sort chips */}
          <div className="mb-6 flex flex-col gap-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex max-w-md flex-1 gap-2">
                <SkeletonBlock rounded="pill" className="h-11 flex-1" />
                <SkeletonBlock rounded="pill" className="h-11 w-20 flex-none" />
              </div>
              <SkeletonBlock rounded="pill" className="h-11 w-32" />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {Array.from({ length: SORT_CHIPS }, (_, i) => (
                <SkeletonBlock key={i} rounded="pill" className="h-11 w-24" />
              ))}
            </div>
          </div>
        </>
      )}

      <div className="flex flex-col gap-3">
        {Array.from({ length: THREAD_ROWS }, (_, i) => (
          <ThreadCardSkeleton key={i} />
        ))}
      </div>
    </SkeletonStatus>
  );
}

/** ThreadDetailPage: breadcrumb, header block closed by the rule, post cards. */
export function ThreadDetailSkeleton() {
  return (
    <SkeletonStatus>
      {/* Breadcrumb */}
      <SkeletonBlock className="mb-6 h-3 w-64 max-w-full" />

      {/* Header: mono meta row, display title, "started by" line */}
      <div className="mb-8 border-b border-line-2 pb-6">
        <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
          <SkeletonBlock className="h-3 w-20" />
          <SkeletonBlock className="h-3 w-16" />
          <SkeletonBlock className="h-3 w-16" />
        </div>
        <SkeletonBlock className="mb-3 h-7 w-4/5 sm:h-9" />
        <SkeletonBlock className="h-4 w-48 max-w-full" />
      </div>

      {/* Posts */}
      <div className="mb-8 flex flex-col gap-4">
        {Array.from({ length: POST_ROWS }, (_, i) => (
          <PostCardSkeleton key={i} />
        ))}
      </div>
    </SkeletonStatus>
  );
}

/** SearchPage results area (page chrome stays mounted): summary line, heading, rows. */
export function SearchResultsSkeleton() {
  return (
    <SkeletonStatus>
      <SkeletonBlock className="mb-6 h-5 w-full max-w-lg" />
      <SkeletonBlock className="mb-4 h-5 w-32" />
      <div className="flex flex-col gap-3">
        {Array.from({ length: SEARCH_ROWS }, (_, i) => (
          <ThreadCardSkeleton key={i} />
        ))}
      </div>
    </SkeletonStatus>
  );
}

/** UserProfilePage: identity card, then two activity sections. */
export function UserProfileSkeleton() {
  return (
    <SkeletonStatus label="Loading profile…">
      <Card className="mb-8 p-6">
        <SkeletonBlock className="mb-3 h-3 w-28" />
        <div className="flex items-center gap-5">
          <SkeletonBlock rounded="md" className="h-20 w-20 flex-none" />
          <div className="min-w-0 flex-1">
            <SkeletonBlock className="h-8 w-1/2" />
            <SkeletonBlock className="mt-2.5 h-3 w-3/4 max-w-xs" />
          </div>
        </div>
      </Card>
      {Array.from({ length: 2 }, (_, section) => (
        <div key={section} className="mb-8">
          <SkeletonBlock className="mb-2 h-5 w-32" />
          <div className="divide-y divide-line">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="flex flex-wrap items-baseline gap-x-2 px-1 py-2.5">
                <SkeletonBlock className="h-4 w-1/2" />
                <SkeletonBlock className="h-3 w-24" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </SkeletonStatus>
  );
}
