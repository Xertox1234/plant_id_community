# Canopy PR 2 — Forum Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild all six forum pages and their components on the Canopy primitives, delete the Field Notes `.wf-*` system, retire `ForumIcons`, fill the right rail, and wire the sidebar Forum unread badge.

**Architecture:** Pure restyle-on-primitives: every page keeps its data layer (fetches, race guards, handlers, drafts, a11y contracts) byte-identical unless a step says otherwise; only render markup changes. One new context (`UnreadNotifications`) lifts the bell's poll so the sidebar badge and the bell share a single request stream. Rail modules are honest — built only from data existing endpoints return.

**Tech Stack:** React 19 + TypeScript, Tailwind 4 CSS-first tokens, lucide-react, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-13-canopy-design.md` (§3.2 wf deletion, §5 primitives, §6 Forum row, §8 motion). Branch: `feat/canopy-forum`.

## Global Constraints

- **All animation gated by `prefers-reduced-motion`** (spec §8). No `animation-timeline`/`view()` experiments are carried forward.
- **Tokens only** — no raw hex in components; colors via `--gt-*`/`--canopy-*` utilities.
- **Brand:** visible product name is **Houseplant MD** — forum `PageMeta` titles change from `· PlantID` to `· Houseplant MD`.
- **Data-layer freeze:** the forum pages' hooks, race guards (`loadGenRef`, `currentTopicIdRef`, `ignore` flags), draft persistence, and handler semantics are load-bearing and under test. Restyle the returned JSX; do not alter logic except where a step explicitly edits it (ThreadDetail flash mechanism, ThreadList sort chips).
- **No new backend endpoints** (spec: backend is touched only for PR 3's seed command). Rail modules use only `fetchPopularPosts`, `fetchThreads`, and data already on the page.
- **Honesty:** never fabricate counts, presence, or activity. "Experts online" from spec §4 is NOT built — there is no presence data; this is a recorded spec deviation (goes in the PR body).
- **Invalid-HTML guard:** no `<a>`/`<button>` nested inside an entry-level `<Link>` (browser auto-closes the outer anchor and breaks `getByRole('link')`).
- **Touch targets:** keep `min-h-11` on all touch controls the old markup had.
- **Icons:** `lucide-react` only; every decorative icon gets `aria-hidden="true"`.
- **Formatter trap:** the PostToolUse formatter strips imports unused *at format time* — add an import in the same edit as its first usage.
- **Numbers** render in Geist Mono (`font-mono` + `tabular-nums` where columns align).
- Run Playwright via `./node_modules/.bin/playwright` — never `npx playwright` (rtk proxy mangles args).
- Before each commit: `npx prettier --write <changed files>`, then `git add`. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- All commands run from `web/` unless noted.

---

### Task 1: CSS swap, forum tone util, assets, ThemePreviewPage note

**Files:**

- Modify: `web/src/index.css` (delete Field Notes block, add Canopy forum block)
- Create: `web/src/utils/forumTones.ts`
- Create: `web/src/utils/forumTones.test.ts`
- Modify: `web/src/pages/debug/ThemePreviewPage.tsx`
- Add (binary, copied): `web/public/illustrations/hero-forum.webp`, `hero-blog.webp`, `thumb-monstera.webp`, `thumb-fig.webp`

**Interfaces:**

- Produces: `.gt-label`, `.canopy-flash` (+ `canopy-flash-fade` keyframes), `.canopy-float` (+ keyframes) in CSS; `boardTone(slug: string): TileTone` from `forumTones.ts`. Consumed by every later task.

- [ ] **Step 1: Delete the Field Notes CSS block**

In `web/src/index.css`, delete **everything** from the block-header comment

```css
/* ═══════════ Field Notes · forum ledger system ═══════════
```

(including the `:root { --wf-stem: ... }` block that follows it) down **through** the container query

```css
@container (max-width: 28rem) {
  .wf-entry-title {
    font-size: 1.125rem;
  }
}
```

That removes: the `--wf-*` tokens, the whole `@layer components` wf block, all `wf-*` keyframes (`wf-anchor-fade`, `wf-press-in`, `wf-stem-draw`, `wf-node-pop`, `wf-node-pop-leaf`, `wf-rise`), the reduced-motion/`@supports (animation-timeline: view())` block, the `.wf-entry:has(...)` rules, `.wf-field:has(...)`, and `.wf-entry-title` sizing. **KEEP** the two trailing `::view-transition` blocks (`/* View transitions (list ↔ detail)... */` and the reduced-motion kill) — they are generic app chrome, not Field Notes.

- [ ] **Step 2: Add the Canopy forum block**

Insert where the deleted block was (after the `canopy-drift` keyframes, before the view-transition rules):

```css
/* ═══════════ Canopy forum (PR 2) ═══════════ */
@layer components {
  /* Mono data voice — eyebrows, stat lines, tiny badges. */
  .gt-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--gt-ink-3);
  }
  /* Deep-link / just-posted highlight. Static ring under reduced motion
     (JS removes the class after ~2.5s); faded out where motion is allowed. */
  .canopy-flash .canopy-card {
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--canopy-sage) 55%, transparent);
  }
}
@media (prefers-reduced-motion: no-preference) {
  .canopy-flash .canopy-card {
    animation: canopy-flash-fade 2.4s ease-out both;
  }
  .canopy-float {
    animation: canopy-float 7s ease-in-out infinite alternate;
  }
}
@keyframes canopy-flash-fade {
  from {
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--canopy-sage) 55%, transparent);
  }
  to {
    box-shadow: 0 0 0 2px transparent;
  }
}
@keyframes canopy-float {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-10px);
  }
}
```

- [ ] **Step 3: Write the failing test for `boardTone`**

Create `web/src/utils/forumTones.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { boardTone } from './forumTones';

describe('boardTone', () => {
  it('is deterministic for a given slug', () => {
    expect(boardTone('12-plant-care')).toBe(boardTone('12-plant-care'));
  });
  it('returns a valid TileTone for any slug', () => {
    const valid = ['sage', 'pollen', 'bloom', 'orchid'];
    for (const slug of ['a', 'plant-care', '99-show-and-tell', '']) {
      expect(valid).toContain(boardTone(slug));
    }
  });
});
```

- [ ] **Step 4: Run it to verify it fails**

Run: `npx vitest run src/utils/forumTones.test.ts`
Expected: FAIL — cannot resolve `./forumTones`.

- [ ] **Step 5: Implement `forumTones.ts`**

```ts
import type { TileTone } from '../components/ui/Tile';

const TONES: TileTone[] = ['sage', 'pollen', 'bloom', 'orchid'];

/**
 * Deterministic accent tone per board slug, so a board wears the same tile
 * color on every surface (same hash shape as specimenAvatar).
 */
export function boardTone(slug: string): TileTone {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) >>> 0;
  }
  return TONES[hash % TONES.length];
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npx vitest run src/utils/forumTones.test.ts` — Expected: PASS.

- [ ] **Step 7: ThemePreviewPage swatch legibility (PR-1 carry-in)**

In `web/src/pages/debug/ThemePreviewPage.tsx`:

- On the `probe-tertiary` div, change `className="bg-tertiary"` to `className="bg-tertiary text-abyss"`.
- In `Swatches`, replace the honey span with:

```tsx
{/* DEV-ONLY probe: shipped UI never sets body text on a solid accent ground
    (accents are chrome, not text grounds) — pair with text-abyss so the
    probe itself stays legible in both modes. */}
<span className="rounded-sm bg-tertiary px-2 text-abyss">pollen</span>
```

- [ ] **Step 8: Copy the generated art into the repo**

From repo root (assets are session-generated and unreproducible without a Runware key; `hero-blog`/`thumb-*` are committed now for PR 3 because the generator scratchpad is ephemeral — say so in the commit body):

```bash
cp /private/tmp/claude-501/-Users-williamtower-projects-plant-id-community-backend/f990524f-b19c-4d11-9385-b5af8c88880f/scratchpad/hero-forum.webp \
   /private/tmp/claude-501/-Users-williamtower-projects-plant-id-community-backend/f990524f-b19c-4d11-9385-b5af8c88880f/scratchpad/hero-blog.webp \
   /private/tmp/claude-501/-Users-williamtower-projects-plant-id-community-backend/f990524f-b19c-4d11-9385-b5af8c88880f/scratchpad/thumb-monstera.webp \
   /private/tmp/claude-501/-Users-williamtower-projects-plant-id-community-backend/f990524f-b19c-4d11-9385-b5af8c88880f/scratchpad/thumb-fig.webp \
   web/public/illustrations/
```

If the scratchpad no longer exists, skip `hero-blog`/`thumb-*` and report it; `hero-forum.webp` is required — escalate BLOCKED if missing.

- [ ] **Step 9: Verify nothing broke**

Run: `npx vitest run src/pages/debug src/utils/forumTones.test.ts` and `npx tsc --noEmit`.
Expected: PASS (deleting unused CSS cannot break class-name assertions; the 9 forum files still carry inert `wf-*` classnames until their tasks).

- [ ] **Step 10: Commit**

```bash
npx prettier --write src/index.css src/utils/forumTones.ts src/utils/forumTones.test.ts src/pages/debug/ThemePreviewPage.tsx
git add src/index.css src/utils/forumTones.ts src/utils/forumTones.test.ts src/pages/debug/ThemePreviewPage.tsx public/illustrations/
git commit -m "feat(canopy-forum): delete .wf-* system, add forum chrome CSS + tone util + art"
```

---

### Task 2: UnreadNotifications context + sidebar Forum badge

**Files:**

- Create: `web/src/contexts/UnreadNotificationsContext.tsx`
- Create: `web/src/contexts/UnreadNotificationsContext.test.tsx`
- Modify: `web/src/layouts/AppShell.tsx`
- Modify: `web/src/components/layout/NotificationBell.tsx`
- Modify: `web/src/layouts/AppShell.test.tsx` (mock `notificationService`)

**Interfaces:**

- Consumes: `fetchUnreadCount` from `services/notificationService`; `useAuth` from `contexts/AuthContext`; `CountBadge` from `components/ui/CountBadge`.
- Produces: `UnreadNotificationsProvider`, `useUnreadNotifications(): { unreadCount: number; refresh: () => void; decrement: () => void; clear: () => void }`. Default context value is `{ unreadCount: 0 }` with no-op functions, so consumers render safely without a provider (tests).

- [ ] **Step 1: Write the failing tests**

Create `web/src/contexts/UnreadNotificationsContext.test.tsx`:

```tsx
import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { UnreadNotificationsProvider, useUnreadNotifications } from './UnreadNotificationsContext';

const mockFetchUnreadCount = vi.fn();
vi.mock('../services/notificationService', () => ({
  fetchUnreadCount: (...args: unknown[]) => mockFetchUnreadCount(...args),
}));

let mockIsAuthenticated = true;
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

function Probe() {
  const { unreadCount, decrement, clear } = useUnreadNotifications();
  return (
    <div>
      <span data-testid="count">{unreadCount}</span>
      <button onClick={decrement}>dec</button>
      <button onClick={clear}>clear</button>
    </div>
  );
}

describe('UnreadNotificationsContext', () => {
  beforeEach(() => {
    mockFetchUnreadCount.mockReset();
    mockIsAuthenticated = true;
  });

  it('polls the unread count when authenticated', async () => {
    mockFetchUnreadCount.mockResolvedValue(4);
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('4'));
    expect(mockFetchUnreadCount).toHaveBeenCalled();
  });

  it('does not fetch and reports 0 when unauthenticated', async () => {
    mockIsAuthenticated = false;
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    expect(mockFetchUnreadCount).not.toHaveBeenCalled();
  });

  it('decrement floors at 0 and clear resets', async () => {
    mockFetchUnreadCount.mockResolvedValue(1);
    render(
      <UnreadNotificationsProvider>
        <Probe />
      </UnreadNotificationsProvider>
    );
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    act(() => screen.getByText('dec').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    act(() => screen.getByText('dec').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
    act(() => screen.getByText('clear').click());
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('renders with safe defaults when no provider is mounted', () => {
    render(<Probe />);
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/contexts/UnreadNotificationsContext.test.tsx` — Expected: FAIL (module missing).

- [ ] **Step 3: Implement the context**

Create `web/src/contexts/UnreadNotificationsContext.tsx`:

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { fetchUnreadCount } from '../services/notificationService';
import { useAuth } from './AuthContext';

// Generous relative to the backend's 120/m rate limit on this endpoint — the
// bell and the sidebar badge share THIS one poll (moved here from
// NotificationBell so a second consumer never means a second request stream).
export const UNREAD_POLL_INTERVAL_MS = 30_000;

interface UnreadNotificationsValue {
  unreadCount: number;
  refresh: () => void;
  decrement: () => void;
  clear: () => void;
}

const noop = () => {};
const UnreadNotificationsContext = createContext<UnreadNotificationsValue>({
  unreadCount: 0,
  refresh: noop,
  decrement: noop,
  clear: noop,
});

interface UnreadNotificationsProviderProps {
  children: ReactNode;
}

export function UnreadNotificationsProvider({ children }: UnreadNotificationsProviderProps) {
  const { isAuthenticated } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  // useRef for the timer id, not useState (CLAUDE.md gotcha: useState
  // re-renders + recreates the callback + leaks the timer on unmount).
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    if (!isAuthenticated) return;
    fetchUnreadCount()
      .then(setUnreadCount)
      .catch(() => {
        /* transient poll failure — next tick retries; nothing user-actionable */
      });
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) {
      setUnreadCount(0);
      return;
    }
    refresh();
    pollTimerRef.current = setInterval(refresh, UNREAD_POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isAuthenticated, refresh]);

  const decrement = useCallback(() => setUnreadCount((prev) => Math.max(0, prev - 1)), []);
  const clear = useCallback(() => setUnreadCount(0), []);

  return (
    <UnreadNotificationsContext.Provider value={{ unreadCount, refresh, decrement, clear }}>
      {children}
    </UnreadNotificationsContext.Provider>
  );
}

export function useUnreadNotifications(): UnreadNotificationsValue {
  return useContext(UnreadNotificationsContext);
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run src/contexts/UnreadNotificationsContext.test.tsx` — Expected: PASS.

- [ ] **Step 5: Wire AppShell — provider + sidebar badge**

In `web/src/layouts/AppShell.tsx`:

1. Add imports (same edit as their usages): `import CountBadge from '../components/ui/CountBadge';` and `import { UnreadNotificationsProvider, useUnreadNotifications } from '../contexts/UnreadNotificationsContext';`
2. In `NavItems`, consume the count and render the badge on the Forum item (spec §4: "Forum (unread count badge)"). Replace the map body:

```tsx
function NavItems({ onNavigate }: NavItemsProps) {
  const { unreadCount } = useUnreadNotifications();
  return (
    <>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate} className={navClass}>
          <Icon className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          {label}
          {to === '/forum' && unreadCount > 0 && (
            <span className="ml-auto" aria-label={`${unreadCount} unread notifications`}>
              <CountBadge count={unreadCount} />
            </span>
          )}
        </NavLink>
      ))}
    </>
  );
}
```

- (3) Wrap the shell's returned tree in the provider — in `AppShell`'s return, the outermost `<div className="min-h-screen">` becomes a child of `<UnreadNotificationsProvider>`:

```tsx
return (
  <UnreadNotificationsProvider>
    <div className="min-h-screen">
      {/* ...entire existing tree unchanged... */}
    </div>
  </UnreadNotificationsProvider>
);
```

- [ ] **Step 6: Refactor NotificationBell to consume the context**

In `web/src/components/layout/NotificationBell.tsx`:

1. Delete: the `UNREAD_POLL_INTERVAL_MS` constant, the `fetchUnreadCount` import, the `const [unreadCount, setUnreadCount] = useState(0);` line, `pollTimerRef`, `refreshUnreadCount`, and the entire poll `useEffect`.
2. Add: `import { useUnreadNotifications } from '../../contexts/UnreadNotificationsContext';` and inside the component: `const { unreadCount, decrement, clear } = useUnreadNotifications();`
3. In `handleMarkAllRead`, replace `setUnreadCount(0);` with `clear();`
4. In `handleSelectNotification`, replace `setUnreadCount((prev) => Math.max(0, prev - 1));` with `decrement();`
5. Everything else (list state, dropdown, `badgeText`, `data-testid="notification-badge"`) is unchanged.

- [ ] **Step 7: Repair AppShell tests**

In `web/src/layouts/AppShell.test.tsx`, add a `vi.mock('../services/notificationService', ...)` returning `fetchUnreadCount: vi.fn().mockResolvedValue(0)` (plus `fetchNotifications`/`markNotificationsRead` no-ops if the module mock requires them), so authenticated renders don't hit the network. Add one new test: with `fetchUnreadCount` resolving 3 and an authenticated auth mock, the Forum nav item shows `3` (`await screen.findAllByText('3')` — desktop nav; assert at least one).

- [ ] **Step 8: Run the affected suites**

Run: `npx vitest run src/layouts src/contexts/UnreadNotificationsContext.test.tsx src/components/layout` — Expected: PASS.

- [ ] **Step 9: Commit**

```bash
npx prettier --write src/contexts/UnreadNotificationsContext.tsx src/contexts/UnreadNotificationsContext.test.tsx src/layouts/AppShell.tsx src/layouts/AppShell.test.tsx src/components/layout/NotificationBell.tsx
git add <those files>
git commit -m "feat(canopy-forum): shared unread-notifications context + sidebar Forum badge"
```

---

### Task 3: ThreadCard + CategoryCard on Canopy primitives (ForumIcons → lucide)

**Files:**

- Modify: `web/src/components/forum/ThreadCard.tsx` (full rewrite below)
- Modify: `web/src/components/forum/CategoryCard.tsx` (full rewrite below)
- Modify: `web/src/components/forum/ThreadCard.test.tsx`, `CategoryCard.test.tsx` (repair presentation assertions only)

**Interfaces:**

- Consumes: `Card`, `Tile`, `Timestamp`, `boardTone`, lucide icons.
- Produces: same public props as today — `ThreadCard { thread, compact?, hideAuthor?, onTagClick?, activeTag? }`, `CategoryCard { category }`. Downstream pages keep importing them unchanged.

- [ ] **Step 1: Rewrite `CategoryCard.tsx`** (replace the whole file)

```tsx
import { memo } from 'react';
import { Link } from 'react-router-dom';
import { Leaf, MessagesSquare, Reply } from 'lucide-react';
import Card from '../ui/Card';
import Tile from '../ui/Tile';
import Timestamp from '../ui/Timestamp';
import { categoryPath } from '../../utils/forumUrls';
import { boardTone } from '../../utils/forumTones';
import type { Category } from '@/types';

interface CategoryCardProps {
  category: Category;
}

/**
 * CategoryCard — a Canopy board row.
 *
 * Gradient card with the board's accent tile, name, description, and a mono
 * stat line. Subcategory chips sit OUTSIDE the row link (nested anchors are
 * invalid HTML).
 */
function CategoryCard({ category }: CategoryCardProps) {
  const hasChildren = !!(category.children && category.children.length > 0);

  return (
    <Card interactive className="p-card">
      <Link to={categoryPath(category)} viewTransition className="flex items-start gap-4">
        <Tile tone={boardTone(category.slug)} aria-hidden="true">
          {category.icon ? (
            <span className="text-xl leading-none">{category.icon}</span>
          ) : (
            <Leaf className="h-5 w-5" />
          )}
        </Tile>
        <div className="min-w-0 flex-1">
          <h3 className="gt-h3 text-ink">{category.name}</h3>
          {category.description && (
            <p className="mt-1 line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
              {category.description}
            </p>
          )}
          <div className="gt-label mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1">
              <MessagesSquare className="h-3 w-3" aria-hidden="true" />
              {category.thread_count || 0} threads
            </span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Reply className="h-3 w-3" aria-hidden="true" />
              {category.post_count || 0} posts
            </span>
            <span aria-hidden="true">·</span>
            {category.last_post_at ? (
              <Timestamp iso={category.last_post_at} prefix="Last activity" />
            ) : (
              <span>No activity yet</span>
            )}
          </div>
        </div>
      </Link>

      {hasChildren && (
        <div className="mt-3 flex flex-wrap items-center gap-2 sm:pl-[62px]">
          <span className="gt-label">Subcategories</span>
          {category.children.map((child) => (
            <Link
              key={child.id}
              to={categoryPath(child)}
              className="gt-label inline-flex min-h-11 items-center rounded-pill border border-line px-3 transition-colors hover:border-line-2 hover:bg-surface-2 hover:text-ink-2"
            >
              {child.icon && (
                <span className="mr-1" aria-hidden="true">
                  {child.icon}
                </span>
              )}
              {child.name}
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export default memo(CategoryCard);
```

- [ ] **Step 2: Rewrite `ThreadCard.tsx`** (replace the whole file)

```tsx
import { memo } from 'react';
import { Link } from 'react-router-dom';
import { Check, Eye, Lock, Pin, Reply } from 'lucide-react';
import Card from '../ui/Card';
import Timestamp from '../ui/Timestamp';
import { threadPath } from '../../utils/forumUrls';
import type { Thread } from '@/types';

interface ThreadCardProps {
  thread: Thread;
  compact?: boolean;
  /** Pass true for search results where author data is unavailable (sentinel). */
  hideAuthor?: boolean;
  /**
   * Filter the list by a tag (audit M5). When omitted the tags still render,
   * but as inert chips — used where there is no list to filter (search).
   */
  onTagClick?: (tag: string) => void;
  /** The tag currently filtering the list, so its chip can read as active. */
  activeTag?: string;
}

/**
 * ThreadCard — a Canopy topic row: gradient card, state chips, title in the
 * display face, excerpt, mono stat line. Tags sit OUTSIDE the row link
 * (nested anchors/buttons are invalid HTML — same contract as before).
 */
function ThreadCard({
  thread,
  compact = false,
  hideAuthor = false,
  onTagClick,
  activeTag,
}: ThreadCardProps) {
  const threadUrl = threadPath(thread.category, thread);
  const tags = thread.tags ?? [];

  return (
    <Card
      interactive
      className={`${compact ? 'p-3.5' : 'p-card'} ${thread.is_locked ? 'opacity-75' : ''}`}
    >
      <Link to={threadUrl} viewTransition className="block">
        {(compact || thread.is_pinned || thread.is_locked || thread.is_solved || thread.is_unread) && (
          <div className="gt-label mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            {compact && (
              <span>
                {thread.category.icon && (
                  <span className="mr-1" aria-hidden="true">
                    {thread.category.icon}
                  </span>
                )}
                {thread.category.name}
              </span>
            )}
            {thread.is_pinned && (
              <span className="inline-flex items-center gap-1 text-tertiary">
                <Pin className="h-3 w-3" aria-hidden="true" /> Pinned
              </span>
            )}
            {thread.is_locked && (
              <span className="inline-flex items-center gap-1">
                <Lock className="h-3 w-3" aria-hidden="true" /> Locked
              </span>
            )}
            {thread.is_solved && (
              <span className="inline-flex items-center gap-1 text-secondary">
                <Check className="h-3 w-3" aria-hidden="true" /> Solved
              </span>
            )}
            {thread.is_unread && <span className="font-semibold text-primary">New</span>}
          </div>
        )}

        <h3
          className={`gt-h3 text-ink ${compact ? 'mb-0.5' : 'mb-1.5'}`}
          style={{ viewTransitionName: `thread-${thread.id}` }}
        >
          {thread.title}
        </h3>

        {!compact && thread.excerpt && (
          <p className="line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
            {thread.excerpt}
          </p>
        )}

        <div className={`gt-label flex flex-wrap items-center gap-x-2 gap-y-1 ${compact ? 'mt-1' : 'mt-2.5'}`}>
          {!hideAuthor && (
            <>
              <span className="normal-case tracking-normal text-ink-2">
                {thread.author.display_name || thread.author.username}
              </span>
              <span aria-hidden="true">·</span>
            </>
          )}
          <span className="inline-flex items-center gap-1" title={`${thread.post_count} replies`}>
            <Reply className="h-3 w-3" aria-hidden="true" /> {thread.post_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1" title={`${thread.view_count} views`}>
            <Eye className="h-3 w-3" aria-hidden="true" /> {thread.view_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <Timestamp iso={thread.last_activity_at} prefix="Last activity" />
        </div>
      </Link>

      {tags.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {tags.map((tag) =>
            onTagClick ? (
              <button
                key={tag}
                type="button"
                onClick={() => onTagClick(tag)}
                aria-pressed={tag === activeTag}
                className={`gt-label inline-flex min-h-11 items-center rounded-pill border px-3 transition-colors ${
                  tag === activeTag
                    ? 'border-secondary/60 bg-secondary/15 text-ink'
                    : 'border-line bg-transparent hover:border-line-2 hover:bg-surface-2'
                }`}
              >
                #{tag}
              </button>
            ) : (
              <span
                key={tag}
                className="gt-label inline-flex items-center rounded-pill border border-line px-3 py-1"
              >
                #{tag}
              </span>
            )
          )}
        </div>
      )}
    </Card>
  );
}

export default memo(ThreadCard);
```

Notes locked in: the pinned tint moves from a row background to the `text-tertiary` chip; the "No. {id}" record number and the "started by" prefix are Field Notes idioms and are gone — the author renders as a plain name in the stat line (still plain text inside the Link, never a nested anchor); `is_solved` renders `text-secondary` (AA in both modes per PR-1 light fixes — do NOT use `text-ok`).

- [ ] **Step 3: Run + repair the two component suites**

Run: `npx vitest run src/components/forum/ThreadCard.test.tsx src/components/forum/CategoryCard.test.tsx`.
Repair only assertions about removed presentation (record numbers, "started by", `wf-*` class checks if any). Keep and satisfy all behavior assertions: link roles/hrefs, tag `aria-pressed`, nested-anchor guards, `hideAuthor`, timestamps, pinned/locked/solved labels.

- [ ] **Step 4: Commit**

```bash
npx prettier --write src/components/forum/ThreadCard.tsx src/components/forum/CategoryCard.tsx src/components/forum/ThreadCard.test.tsx src/components/forum/CategoryCard.test.tsx
git add <those files>
git commit -m "feat(canopy-forum): ThreadCard + CategoryCard on Canopy primitives"
```

---

### Task 4: CategoryListPage — hero, stat cards, board rows, rail (+ FromTheBlogModule)

**Files:**

- Create: `web/src/components/forum/rail/FromTheBlogModule.tsx`
- Create: `web/src/components/forum/rail/FromTheBlogModule.test.tsx`
- Modify: `web/src/pages/forum/CategoryListPage.tsx`
- Modify: `web/src/pages/forum/CategoryListPage.test.tsx` (repair + extend)

**Interfaces:**

- Consumes: `HeroCard`, `StatCard`, `RailSlot`, `RailModule`, `CategoryCard` (Task 3), `boardTone`; `fetchPopularPosts(options?: { limit?: number; days?: number }): Promise<BlogPost[]>` from `services/blogService`.
- Produces: `FromTheBlogModule` (default export, no props) — reused by Tasks 5 and 7. It renders `null` while loading/empty/on error (the rail self-hides via `.app-rail:not(:has(*))` only if ALL modules render null — harmless either way).

- [ ] **Step 1: Failing test for FromTheBlogModule**

Create `web/src/components/forum/rail/FromTheBlogModule.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import FromTheBlogModule from './FromTheBlogModule';

const mockFetchPopularPosts = vi.fn();
vi.mock('../../../services/blogService', () => ({
  fetchPopularPosts: (...args: unknown[]) => mockFetchPopularPosts(...args),
}));

const post = (id: number, title: string, slug: string) => ({
  id,
  title,
  slug,
  meta: { slug, type: 'blog.BlogPage', detail_url: '', html_url: '', first_published_at: '' },
  content_blocks: [],
});

describe('FromTheBlogModule', () => {
  beforeEach(() => mockFetchPopularPosts.mockReset());

  it('renders popular posts as links', async () => {
    mockFetchPopularPosts.mockResolvedValue([post(1, 'Monstera care', 'monstera-care')]);
    render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    const link = await screen.findByRole('link', { name: /monstera care/i });
    expect(link).toHaveAttribute('href', '/blog/monstera-care');
    expect(screen.getByText('From the blog')).toBeInTheDocument();
  });

  it('renders nothing when there are no posts', async () => {
    mockFetchPopularPosts.mockResolvedValue([]);
    const { container } = render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    await waitFor(() => expect(mockFetchPopularPosts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing on fetch error', async () => {
    mockFetchPopularPosts.mockRejectedValue(new Error('nope'));
    const { container } = render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    await waitFor(() => expect(mockFetchPopularPosts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run to verify failure**, then **implement**

`npx vitest run src/components/forum/rail/FromTheBlogModule.test.tsx` → FAIL. Then create `web/src/components/forum/rail/FromTheBlogModule.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import { fetchPopularPosts } from '../../../services/blogService';
import { logger } from '../../../utils/logger';
import type { BlogPost } from '../../../types/blog';

const RAIL_POST_LIMIT = 3;

/**
 * Right-rail module: the most-read blog posts (spec §4 "From the blog").
 * Self-hides while loading, on error, and when the blog is empty — the rail
 * never shows a spinner or a fake placeholder.
 */
export default function FromTheBlogModule() {
  const [posts, setPosts] = useState<BlogPost[]>([]);

  useEffect(() => {
    let ignore = false;
    fetchPopularPosts({ limit: RAIL_POST_LIMIT })
      .then((items) => {
        if (!ignore) setPosts(items);
      })
      .catch((err) => {
        logger.error('Error loading rail blog posts', {
          component: 'FromTheBlogModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (posts.length === 0) return null;

  return (
    <RailModule icon={<BookOpen aria-hidden="true" />} title="From the blog">
      <ul className="flex flex-col gap-3">
        {posts.map((post) => (
          <li key={post.id}>
            <Link to={`/blog/${post.meta?.slug ?? post.slug}`} className="group block">
              <span className="text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
                {post.title}
              </span>
              {post.introduction && (
                <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-3">
                  {post.introduction}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </RailModule>
  );
}
```

Run the module test again → PASS.

- [ ] **Step 3: Rebuild CategoryListPage's render**

In `web/src/pages/forum/CategoryListPage.tsx`: keep lines 1–63 (state, effect, `introMarkup`) except swap the import block additions. New imports to add: `HeroCard`, `StatCard`, `RailSlot`, `RailModule`, `FromTheBlogModule`, `Timestamp`, `Button`, and lucide `{ Activity, Layers, MessagesSquare, Reply }`. Remove: nothing from the logic. Replace everything from `if (loading)` to the end with:

```tsx
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
            <Link to="/forum/new-thread">
              <Button variant="primary">Start a thread</Button>
            </Link>
            <Link to="/forum/search">
              <Button variant="ghost">Search the forum</Button>
            </Link>
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
```

Also add the imports this JSX needs that the file lacks: `Card` from `../../components/ui/Card`, `categoryPath` from `../../utils/forumUrls`. The empty-state `wf-sheet`/`wf-title`/`wf-ledger`/`wf-label` classes must all be gone from this file afterwards.

- [ ] **Step 4: Run + repair the page suite**

`npx vitest run src/pages/forum/CategoryListPage.test.tsx` — repair presentation-bound assertions (old header copy "Community Forums", `Field Notes` eyebrow). Keep behavior assertions (fetch, retry, empty state copy, intro sanitization gating). Add one assertion: the hero renders (`screen.getByText('Ask the canopy')`). Mock `../../services/blogService` in this suite (module fetches on mount inside RailSlot — note RailSlot portals to `#app-rail` which doesn't exist in jsdom page tests, so the rail content does NOT render there; the blogService mock guards against the fetch call only if the module mounts. RailSlot returns null without the container — either way, add the mock defensively).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(canopy-forum): forum home — hero, stat cards, board rows, rail modules"
```

---

### Task 5: ThreadListPage — board header, sort chips, rail

**Files:**

- Modify: `web/src/pages/forum/ThreadListPage.tsx`
- Modify: `web/src/pages/forum/ThreadListPage.test.tsx`

**Interfaces:**

- Consumes: `ThreadCard` (Task 3), `Chip`, `Tile`, `RailSlot`, `RailModule`, `FromTheBlogModule` (Task 4), `boardTone`, `Button`, lucide `{ Info, Search }`.

- [ ] **Step 1: Logic edit — sort becomes chip-driven**

Replace `handleOrderChange` (the `ChangeEvent<HTMLSelectElement>` version) with a value-based version, keeping URL semantics identical:

```tsx
  // Handle ordering change (URL/UI only) — chips call this with the sort value.
  const handleOrderChange = useCallback(
    (newOrder: string) => {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        newParams.set('order', newOrder);
        return newParams;
      });
    },
    [setSearchParams]
  );
```

Add a module-level constant above the component:

```tsx
const SORT_OPTIONS = [
  { value: '-last_activity_at', label: 'Active' },
  { value: '-created_at', label: 'Newest' },
  { value: 'created_at', label: 'Oldest' },
  { value: '-view_count', label: 'Most viewed' },
  { value: '-post_count', label: 'Most replies' },
] as const;
```

All other logic (category cache, generation guard, tag handlers, load-more) is untouched.

- [ ] **Step 2: Rebuild the render** — replace everything from the first `if (loading && !category)` to the end of the file with:

```tsx
  if (loading && !category) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !category) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <ForumErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <PageMeta
        title={`${category?.name ?? 'Forum'} · Houseplant MD`}
        description={
          category?.description || `Browse discussions in ${category?.name ?? 'the forum'}.`
        }
      />

      {/* Breadcrumb — mono data voice */}
      <nav className="gt-label mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" viewTransition className="transition-colors hover:text-primary">
              Forum
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="text-ink-2">
            {category?.name}
          </li>
        </ol>
      </nav>

      {/* Board header */}
      <div className="mb-6 flex items-start gap-4">
        {category && (
          <Tile tone={boardTone(category.slug)} aria-hidden="true">
            {category.icon ? (
              <span className="text-xl leading-none">{category.icon}</span>
            ) : (
              <Leaf className="h-5 w-5" />
            )}
          </Tile>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="gt-h1 text-ink">{category?.name}</h1>
          {category?.description && (
            <p className="mt-1.5 max-w-prose leading-relaxed text-ink-2">{category.description}</p>
          )}
          {category?.thread_count != null && (
            <p className="gt-label mt-2">{category.thread_count} threads</p>
          )}
        </div>
      </div>

      {/* Toolbar: search, sort chips, new thread */}
      <div className="mb-6 flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <form onSubmit={handleSearch} className="max-w-md flex-1">
            <div className="flex gap-2">
              <label htmlFor="board-search" className="sr-only">
                Search this board
              </label>
              <input
                id="board-search"
                type="search"
                name="search"
                placeholder="Search this board…"
                className="min-h-11 flex-1 rounded-pill border border-line bg-surface-2/60 px-4 py-2 text-[13.5px] text-ink transition-colors placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none"
              />
              <Button type="submit" variant="secondary">
                Search
              </Button>
            </div>
          </form>
          <Link to={`/forum/new-thread?category=${categorySlug}`}>
            <Button variant="primary">+ New Thread</Button>
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Sort threads">
          {SORT_OPTIONS.map((opt) => (
            <Chip
              key={opt.value}
              active={ordering === opt.value}
              onClick={() => handleOrderChange(opt.value)}
            >
              {opt.label}
            </Chip>
          ))}
        </div>
      </div>

      {/* Active tag filter (audit M5) — always visible while filtering, so an
          empty result reads as "this filter matched nothing" rather than
          "this board is empty". */}
      {activeTag && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface-2/60 px-4 py-3">
          <span className="gt-label">Filtered by tag</span>
          <span className="gt-label rounded-pill border border-secondary/60 bg-secondary/15 px-3 py-1 text-ink">
            #{activeTag}
          </span>
          <button
            type="button"
            onClick={clearTagFilter}
            className="min-h-11 rounded-pill px-3 text-sm text-ink-3 transition-colors hover:bg-surface-2"
          >
            Clear filter
          </button>
        </div>
      )}

      {/* Threads */}
      {loading ? (
        <LoadingSpinner />
      ) : threads.length === 0 ? (
        <div className="py-12 text-center text-ink-3">
          {activeTag ? (
            <>
              <p className="text-lg">No threads tagged #{activeTag}.</p>
              <p className="mt-2 text-sm">Clear the filter to see the whole board.</p>
            </>
          ) : (
            <>
              <p className="text-lg">No threads found.</p>
              <p className="mt-2 text-sm">Be the first to start a discussion!</p>
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {threads.map((thread) => (
            <ThreadCard
              key={thread.id}
              thread={thread}
              onTagClick={handleTagClick}
              activeTag={activeTag}
            />
          ))}
        </div>
      )}

      {/* Load More (cursor pagination) — honest remaining count (audit M30);
          suppressed while a tag filter is active (thread_count is unfiltered). */}
      {nextCursor && !loading && (
        <div className="mt-8 text-center">
          <Button
            onClick={handleLoadMore}
            variant="outline"
            loading={loadingMore}
            disabled={loadingMore}
            className="min-h-11"
          >
            {loadingMore
              ? 'Loading...'
              : (() => {
                  if (activeTag) return 'Load More';
                  const remaining = Math.max(0, (category?.thread_count ?? 0) - threads.length);
                  return remaining > 0 ? `Load More (${remaining} remaining)` : 'Load More';
                })()}
          </Button>
        </div>
      )}

      <RailSlot>
        {category?.description && (
          <RailModule icon={<Info aria-hidden="true" />} title="About this board">
            <p className="text-[13px] leading-relaxed text-ink-2">{category.description}</p>
            {category.thread_count != null && (
              <p className="gt-label">{category.thread_count} threads</p>
            )}
          </RailModule>
        )}
        <FromTheBlogModule />
      </RailSlot>
    </div>
  );
```

Imports to add in the same edit: `Chip`, `Tile`, `RailSlot`, `RailModule`, `FromTheBlogModule`, `boardTone`, lucide `{ Info, Leaf }`. `useCallback` list otherwise unchanged.

- [ ] **Step 3: Run + repair the page suite**

`npx vitest run src/pages/forum/ThreadListPage.test.tsx`. The sort control changed from a `<select>` (combobox role) to chips (buttons with `aria-pressed`) — rewrite those interactions as `getByRole('button', { name: 'Newest' })` clicks and assert the `order` search param / refetch behavior the old test asserted. Everything else (search redirect, tag filter, load-more counts, race guards) must pass against unchanged logic. Add `vi.mock` for `blogService` here too.

- [ ] **Step 4: Commit** — `feat(canopy-forum): board page — header tile, sort chips, rail`

---

### Task 6: PostCard + IdentificationCard on Canopy primitives

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx`
- Modify: `web/src/components/forum/IdentificationCard.tsx`
- Modify: `web/src/components/forum/PostCard.test.tsx` (repair presentation assertions only)

**Interfaces:**

- Consumes: `Card`, `Avatar`, `Timestamp`, lucide `{ Check, Flag, Link2, Pencil, Trash2 }`.
- Produces: same public `PostCardProps` as today (post, onEdit, onDelete, onReact, onReport, isSolution, onToggleSolution).

- [ ] **Step 1: Restyle PostCard's wrapper + header**

Keep every hook, handler, capability gate, and a11y contract in `PostCard.tsx`. Make exactly these presentation changes:

1. Replace the ForumIcons import with `import { Check, Flag, Link2, Pencil, Trash2 } from 'lucide-react';` and swap each usage: `IconCheck`→`Check`, `IconLink`→`Link2`, `IconPencil`→`Pencil`, `IconTrash`→`Trash2`, `IconFlag`→`Flag`. Every lucide instance gets `className="h-3.5 w-3.5" aria-hidden="true"` (replacing `size={12|13}`).
2. Add `import Card from '../ui/Card';` and `import Avatar from '../ui/Avatar';`
3. Replace the outer wrapper div:

```tsx
    <Card
      className={`group p-5 sm:p-6 ${isSolution ? 'border-secondary/60 ring-1 ring-secondary/40' : ''}`}
    >
```

(and its closing tag `</Card>`; remove `wf-sheet`/`wf-taped` entirely).

- (4) Replace the accepted-answer banner's classes: `wf-label` → `gt-label`, keep text and `text-secondary` instead of `text-primary`:

```tsx
      {isSolution && (
        <p className="gt-label mb-4 inline-flex items-center gap-1.5 text-secondary">
          <Check className="h-3.5 w-3.5" aria-hidden="true" /> Accepted answer
        </p>
      )}
```

- (5) Replace the bespoke avatar block (the `w-12 h-12 bg-primary/10 ...` div and its two `<img>` branches) with:

```tsx
          <Avatar
            src={post.author.avatar || specimenAvatar(post.author.username)}
            alt=""
            size="md"
          />
```

(the author's name sits right beside it, so the image stays decorative — same rationale as before).

- (6) Class renames through the rest of the file: every `wf-label` → `gt-label`; every `rounded-xs` on action buttons → `rounded-pill`; the trust-level badge keeps `border-sky/40 text-sky`; the "Original Post" badge keeps `border-primary/40 text-primary`; reaction pill active state becomes `border-secondary/60 bg-secondary/15 text-ink` (inactive classes unchanged). The "Reported" confirmation `wf-label italic` → `gt-label italic`.

Nothing else changes — the reaction picker, report flow, copy-link fallback, EditHistoryDialog wiring, and all `aria-*` stay byte-identical.

- [ ] **Step 2: Restyle IdentificationCard's shell**

In `IdentificationCard.tsx`, change only the outer `<section>` and header:

```tsx
    <section
      aria-labelledby="identification-heading"
      className="canopy-card mb-6 overflow-hidden rounded-md"
    >
      <div className="flex items-center gap-2 border-b border-line px-6 py-3">
        <Sparkles className="h-4 w-4 text-secondary" aria-hidden="true" />
        <h2 id="identification-heading" className="gt-label normal-case tracking-normal text-[13px] font-semibold text-ink">
          What the app suggested
        </h2>
      </div>
```

Everything else in the file is unchanged (candidates list, honesty copy, solved link).

- [ ] **Step 3: Run + repair**

`npx vitest run src/components/forum/PostCard.test.tsx src/components/forum/IdentificationCard.test.tsx`. PostCard tests are behavior-heavy (capability gates, report flow, reactions, aria-pressed) — they must pass unchanged; repair only class/emoji-free assertions if any pin the old avatar markup.

- [ ] **Step 4: Commit** — `feat(canopy-forum): PostCard + IdentificationCard on Canopy primitives`

---

### Task 7: ThreadDetailPage — header, solution highlight, flash mechanism, rail

**Files:**

- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.test.tsx`

**Interfaces:**

- Consumes: `PostCard` (Task 6), `Card`, `Avatar`, `RailSlot`, `RailModule`, `FromTheBlogModule`, `Timestamp`, `fetchThreads` (existing service), lucide `{ Bell, BellOff, Eye, Lock, MessagesSquare, Pin, Reply, Users }`, `specimenAvatar`.

- [ ] **Step 1: Logic edits (exact, and only these)**

1. **Flash class rename:** in the deep-link arrival effect, `el.classList.add('wf-anchor-flash')` → `el.classList.add('canopy-flash')` and `el.classList.remove('wf-anchor-flash')` → `el.classList.remove('canopy-flash')`. Timeout stays 2500.
2. **Press → flash unification:** the Field Notes press animation is not carried forward (spec §8 keeps one orchestrated moment, the shell's). The just-posted reply reuses the flash highlight:
   - Delete the `onAnimationEnd` prop from the post row div.
   - The row className becomes: `` className={`${justPostedId === post.id ? 'canopy-flash' : ''}`} `` combined with the id anchor (see Step 3 markup — the `wf-node-row`/`wf-node-row--solution` classes disappear).
   - Add one effect after the deep-link effect:

```tsx
  // The just-posted highlight is one-shot: clear its marker on a timer (the
  // reduced-motion rendering is a static ring, so animationend never fires).
  useEffect(() => {
    if (justPostedId == null) return;
    const timer = setTimeout(() => setJustPostedId(null), 2500);
    return () => clearTimeout(timer);
  }, [justPostedId]);
```

- (3) **Rail data:** add state + one fetch for "More in this board" (drops silently on error — the rail is optional chrome):

```tsx
  // Rail: other recent topics on this board. Best-effort — a failure just
  // leaves the module unrendered; never blocks the thread itself.
  const [boardThreads, setBoardThreads] = useState<Thread[]>([]);
  useEffect(() => {
    if (!thread?.category?.slug) return;
    let ignore = false;
    fetchThreads({ board: thread.category.slug })
      .then((data) => {
        if (ignore) return;
        setBoardThreads(
          data.items
            .filter((t) => t.id !== thread.id)
            .slice(0, 5)
            .map((t) => ({ ...t, category: thread.category }))
        );
      })
      .catch(() => {
        /* rail is optional — the thread page must not surface this */
      });
    return () => {
      ignore = true;
    };
  }, [thread?.id, thread?.category?.slug]);
```

(`fetchThreads` import joins the existing service import list. The eslint exhaustive-deps for `thread.id`/`thread.category` — depend on `thread?.id` and `thread?.category?.slug` as shown and read `thread.category` inside guarded by the early return; if the linter objects, capture `const category = thread?.category;` above the effect and depend on that.)

- (4) Participants for the rail derive from already-loaded posts (no new fetch):

```tsx
  const participants = posts.reduce<{ username: string; display: string; avatar?: string | null }[]>(
    (acc, p) => {
      if (
        p.author.username !== DELETED_AUTHOR_USERNAME &&
        !acc.some((a) => a.username === p.author.username)
      ) {
        acc.push({
          username: p.author.username,
          display: p.author.display_name || p.author.username,
          avatar: p.author.avatar,
        });
      }
      return acc;
    },
    []
  );
```

Place it just above the final `return` (after the early returns).

- [ ] **Step 2: Header + notice + posts markup**

Replace the breadcrumb/header/notice/posts-list/composer sections with the Canopy versions. Class conversions and structural changes, in full:

- ForumIcons import → `import { Bell, BellOff, Eye, Lock, MessagesSquare, Pin, Reply, Users } from 'lucide-react';` with `className="h-3.5 w-3.5" aria-hidden="true"` per instance (`size={14}` on Bell/BellOff/Lock → `h-3.5 w-3.5`).
- Breadcrumb `<nav>`: `wf-label mb-8` → `gt-label mb-6`; crumb "Forums" label → "Forum"; the rest identical (including the `normal-case tracking-normal ... truncate` current-page crumb).
- Header: replace `className="mb-8 border-b-2 border-line-2 pb-6"` with `className="mb-8 border-b border-line-2 pb-6"`. Inside it: every `wf-label` → `gt-label`; drop the `No. {thread.id}` span and its following separator; `wf-title text-2xl sm:text-4xl` on the `<h1>` → `gt-display text-[26px] sm:text-[34px]` (keep the `viewTransitionName` style); the stats/state chips and Follow button logic unchanged.
- `PageMeta` title: `· PlantID` → `· Houseplant MD` (both `title` and the og block's description text keep the rest).
- Notice live-region div: `rounded-xs` → `rounded-md` (aria/sr-only mechanics unchanged).
- Posts list wrapper: `className="wf-thread space-y-5 mb-8"` → `className="mb-8 flex flex-col gap-4"`. Each post row (non-editing branch):

```tsx
            <div
              key={post.id}
              id={`post-${post.id}`}
              className={justPostedId === post.id ? 'canopy-flash' : undefined}
            >
```

(the solution styling now lives entirely on PostCard's `isSolution` ring — the row wrapper carries no state classes.)

- Editing branch row: drop `wf-node-row`; the form becomes a `Card`:

```tsx
            <div key={post.id}>
              <form onSubmit={handleEditSubmit} className="canopy-card space-y-3 rounded-md p-5 sm:p-6">
                <span className="gt-label block">Edit post</span>
                {/* TipTapEditor + buttons unchanged */}
              </form>
            </div>
```

- Locked/logged-out/composer panels: `wf-sheet` → `canopy-card rounded-md`; `wf-label` → `gt-label`; `wf-title text-xl` → `gt-h3`; composer heading "Post a Reply" and eyebrow "Add to the record" → eyebrow becomes "Join the discussion". `IconLock` usages → `Lock`.
- Load More block and both ConfirmDialogs: unchanged.

- [ ] **Step 3: Rail markup** — before the closing `</div>` of the page (after the ConfirmDialogs), add:

```tsx
      <RailSlot>
        {participants.length > 0 && (
          <RailModule icon={<Users aria-hidden="true" />} title="In this thread">
            <ul className="flex flex-col gap-2.5">
              {participants.slice(0, 6).map((person) => (
                <li key={person.username} className="flex items-center gap-2.5">
                  <Avatar
                    src={person.avatar || specimenAvatar(person.username)}
                    alt=""
                    size="sm"
                  />
                  <Link
                    to={userProfilePath(person.username)}
                    className="min-w-0 truncate text-[13px] font-medium text-ink transition-colors hover:text-primary"
                  >
                    {person.display}
                  </Link>
                </li>
              ))}
            </ul>
          </RailModule>
        )}
        {boardThreads.length > 0 && (
          <RailModule icon={<MessagesSquare aria-hidden="true" />} title={`More in ${thread.category.name}`}>
            <ul className="flex flex-col gap-3">
              {boardThreads.map((t) => (
                <li key={t.id}>
                  <Link to={threadPath(t.category, t)} className="group block">
                    <span className="line-clamp-2 text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
                      {t.title}
                    </span>
                    <span className="gt-label mt-0.5 block normal-case tracking-normal">
                      <Timestamp iso={t.last_activity_at} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </RailModule>
        )}
        <FromTheBlogModule />
      </RailSlot>
```

Imports to add in the same edit: `RailSlot`, `RailModule`, `FromTheBlogModule`, `Avatar`, `Timestamp`, `specimenAvatar`, `threadPath` (join the existing `forumUrls` import).

- [ ] **Step 4: Run + repair the page suite**

`npx vitest run src/pages/forum/ThreadDetailPage.test.tsx` (42K of behavior tests — solution marking, moderation notices, drafts, deep-link chase, subscription races). Logic is untouched except the flash/press mechanism, so failures should be limited to: `wf-anchor-flash`/`wf-press` class assertions (rename to `canopy-flash` / delete), `onAnimationEnd` press-clearing tests (now timer-based — use `vi.useFakeTimers()` + `advanceTimersByTime(2500)` if the old test asserted clearing), "No." header text, and any `fetchThreads`-not-mocked failures from the new rail fetch (add `fetchThreads: vi.fn().mockResolvedValue({ items: [], meta: { next: null, count: 0 } })` to the existing service mock). Also mock `blogService`.

- [ ] **Step 5: Commit** — `feat(canopy-forum): thread page — Canopy header, unified flash, participants + board rail`

---

### Task 8: SearchPage + NewThreadPage

**Files:**

- Modify: `web/src/pages/forum/SearchPage.tsx`, `web/src/pages/forum/NewThreadPage.tsx`
- Modify: their `.test.tsx` files (repair presentation assertions only)

**Interfaces:**

- Consumes: `Card`, `Button`, `ThreadCard`, lucide `{ Search, SearchX }`.

- [ ] **Step 1: SearchPage restyle** (logic untouched — debounce, generation guard, dedup append all stay):

- Header block: `wf-label` → `gt-label`, eyebrow copy → "Houseplant MD · Community"; `wf-title text-3xl sm:text-4xl` → `gt-h1`; `PageMeta` `· PlantID` → `· Houseplant MD`.
- Search input: replace the inline `<svg>` magnifier with lucide `<Search className="absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-ink-3" aria-hidden="true" />`; input classes → `w-full rounded-pill border border-line bg-surface-2/60 px-4 py-3 pl-12 text-ink transition-colors placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none`.
- Filters panel: `bg-surface-2 rounded-lg shadow-sm p-6 mb-6` → wrap in `<Card className="mb-6 p-6">` (matching close tag); select classes → `w-full rounded-sm border border-line bg-surface-2/60 px-3 py-2 text-ink focus:ring-2 focus:ring-secondary focus:outline-none`.
- Thread results: heading `wf-title text-xl` → `gt-h3`; the `wf-ledger`/`wf-entry-group` wrappers become `flex flex-col gap-3`, with each result + its excerpt grouped in a plain `<div className="flex flex-col gap-1.5">`; the highlighted-match `<p>` classes → `rounded-sm border border-tertiary/25 bg-tertiary/10 p-3 text-sm text-ink-2` (keep its aria-label).
- Post results: each result div `bg-surface-2 rounded-lg border border-line-2 p-4` → `canopy-card rounded-md p-4`; heading `wf-title text-xl` → `gt-h3`.
- Empty/no-results blocks: replace both inline `<svg>`s with lucide (`Search` for "enter a query", `SearchX` for no-results), same sizing classes, `aria-hidden="true"`.
- `<mark className="bg-tertiary/30 rounded px-0.5">` stays (token-based).

- [ ] **Step 2: NewThreadPage restyle** (logic untouched — drafts, handoff, moderation pending state all stay):

- Breadcrumb: `wf-label mb-8` → `gt-label mb-6`, "Forums" → "Forum".
- Eyebrow/heading: `wf-label` → `gt-label`; `wf-title text-3xl` → `gt-h1`; `PageMeta` → `· Houseplant MD`.
- Pending-moderation panel: `wf-sheet p-6` → `canopy-card rounded-md p-6`; `wf-title text-xl` → `gt-h3`.
- Identification-attached panel: `wf-sheet p-4` → `canopy-card rounded-md p-4`.
- Every `wf-field` wrapper → plain `<div>`; every `wf-label` label class → `gt-label`; title input: keep the display-face idiom via `gt-h3` in place of `wf-title`, classes → `gt-h3 w-full rounded-sm border border-line bg-surface-2/60 px-4 py-2.5 text-xl text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none`; tags + board-picker inputs swap `border-line-2 rounded-xs ... bg-surface-2` for `border-line rounded-sm bg-surface-2/60 ... focus:ring-secondary` (keep `min-h-11`, `font-mono` on tags, aria-describedby).
- Error box: `rounded-xs` → `rounded-md`.

- [ ] **Step 3: Run + repair both suites**

`npx vitest run src/pages/forum/SearchPage.test.tsx src/pages/forum/NewThreadPage.test.tsx` — these suites test behavior (debounce, URL params, drafts, submission outcomes); expect at most copy-level repairs ("Search the record" eyebrow, breadcrumb "Forums").

- [ ] **Step 4: Commit** — `feat(canopy-forum): search + composer on Canopy primitives`

---

### Task 9: UserProfilePage, Avatar `lg`, ForumIcons deletion, residue sweep

**Files:**

- Modify: `web/src/components/ui/Avatar.tsx` (+ test), `web/src/pages/forum/UserProfilePage.tsx` (+ test)
- Delete: `web/src/components/forum/ForumIcons.tsx`

**Interfaces:**

- Produces: `Avatar` gains `size="lg"` (`h-20 w-20 rounded-[16px]`).

- [ ] **Step 1: Avatar `lg` size (test-first)**

Add to `Avatar.test.tsx`: rendering `<Avatar src="/x.jpg" alt="" size="lg" />` yields an img with class containing `h-20`. Run → FAIL. Then in `Avatar.tsx` extend the type and map: `size?: 'sm' | 'md' | 'lg'` and `lg: 'h-20 w-20 rounded-[16px]'`. Run → PASS.

- [ ] **Step 2: UserProfilePage restyle** (logic + renderedFor reset untouched):

- Header: replace the `wf-taped` double-frame avatar block with `<Avatar src={profile.avatar || specimenAvatar(profile.username)} alt="" size="lg" />`; wrap the whole header content in `<Card className="mb-8 p-6">` replacing the `border-b-2` header treatment; `wf-label` "Collector" eyebrow → `gt-label` reading `Member profile`; `wf-title text-2xl sm:text-3xl` → `gt-h1`; trust chip `wf-label ... border-sky/40 text-sky` → `gt-label rounded-pill border border-sky/40 px-2 py-0.5 text-sky`; the `@username · N posts · joined ...` line → `gt-label mt-1.5 normal-case tracking-normal`.
- Sections: headings `wf-title text-lg` → `gt-h3`; each `wf-ledger`/`wf-entry` list becomes `<ul className="divide-y divide-line">` with `<li className="flex flex-wrap items-baseline gap-x-2 px-1 py-2.5">`; row link + `gt-label` timestamp classes otherwise as today.
- `<title>` strings: `— Forum` → `· Houseplant MD` (both the not-found and profile titles).

- [ ] **Step 3: Delete ForumIcons + residue sweep**

```bash
git rm src/components/forum/ForumIcons.tsx
grep -rn "wf-" src/ e2e/ && echo "RESIDUE FOUND" || echo "clean"
grep -rn "ForumIcons" src/ && echo "RESIDUE FOUND" || echo "clean"
```

Both greps MUST print `clean`. If `wf-` residue remains in any file, that file was missed by its task — fix it here (class-rename only) and note it in the report.

- [ ] **Step 4: Run + repair** — `npx vitest run src/pages/forum/UserProfilePage.test.tsx src/components/ui/Avatar.test.tsx`, then the whole forum scope: `npx vitest run src/components/forum src/pages/forum`.

- [ ] **Step 5: Commit** — `feat(canopy-forum): profile page, Avatar lg, retire ForumIcons`

---

### Task 10: Gates, visual sweep, PR

**Files:** none new (fixes only if gates fail).

- [ ] **Step 1: Full unit suite** — `npx vitest run` (expect ≥ the 810 from PR 1; zero failures).
- [ ] **Step 2: Types + build** — `npx tsc --noEmit` and `npm run build`.
- [ ] **Step 3: E2E** — `./node_modules/.bin/playwright test e2e/green-thumb-theme.spec.ts e2e/forum.spec.js e2e/forum-authenticated.spec.js` (run whichever forum specs exist under `e2e/`; list them first with `ls e2e/`). Requires the dev servers per the repo's Playwright config.
- [ ] **Step 4: Visual sweep** — with the dev server running, screenshot `/forum`, a board, a thread, `/forum/search`, `/forum/new-thread`, and a profile at 1440px and 375px, both modes (Playwright screenshot script is fine). Check: no `wf-` unstyled residue, rail renders on forum pages ≥1280px, mobile has no horizontal scroll, hero art loads.
- [ ] **Step 5: Push + PR**

```bash
git push -u origin feat/canopy-forum
gh pr create --title "feat(canopy): forum rebuild on Canopy primitives (PR 2/5)" --body "..."
```

PR body must include: spec §6 Forum row scope; the **Experts online deviation** (no presence data — honesty rule; substituted "In this thread" participants + "Active now" boards); the press-animation retirement (spec §8); assets committed ahead for PR 3 and why; the carry-ins closed (sidebar CountBadge, RailSlot modules, ForumIcons retirement, ThemePreviewPage note); test/gate results. Do NOT merge — the user reviews first. End body with the standard Claude Code attribution line.

---

## Deviations from spec (record in PR body)

1. **"Experts online" rail module not built** — requires presence data no endpoint provides; fabricating it violates the project honesty rule (audit M30 lineage). Substitutes: "In this thread" participants (real, from loaded posts) and "Active now" boards (real, from `last_post_at`).
2. **Field Notes press animation retired**, replaced by the unified `canopy-flash` highlight (spec §8 carries forward one orchestrated moment — the shell's ambient, not the forum press).
3. **`hero-blog.webp` + 2 thumbs committed in this PR** though used only in PR 3 — the generating scratchpad is session-ephemeral and the art is unreproducible without a Runware key.

## Self-review notes

- Spec §6 coverage: CategoryList (hero + board rows + stat cards + rail; the "chips" element lands as the sub-board link chips on each row plus the ThreadList sort chips — a standalone top-level chip row would duplicate the board rows two lines below it) T4; ThreadList T5; ThreadDetail (gradient post cards, sage solution, reaction pills) T6+T7; Search T8; NewThread T8; UserProfile T9; `.wf-*` deletion T1; ForumIcons retirement T3/T6/T9 (deleted in T9 after last usage).
- Type consistency: `boardTone(slug: string): TileTone` (T1) consumed T3/T5; `useUnreadNotifications()` shape fixed in T2 and consumed only there; `FromTheBlogModule` prop-less in T4, consumed T5/T7.
- Interim state: after T1 the forum renders unstyled-but-functional (wf classnames inert) — acceptable mid-branch; T10 gates the finished state.
