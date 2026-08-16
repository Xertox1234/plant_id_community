import type { Category } from '../types/forum';

/**
 * Which boards the chip row's current selection actually resolves to. Pure
 * and derived — deliberately NOT a `useEffect` that syncs `activeBoard` back
 * to `null` after the fact. A sync effect would still let a stale selection
 * (its board no longer present in a fresh `categories` payload — refetched,
 * renamed, or dropped) render a blank filtered area for one pass before the
 * effect corrects it on the next; deriving straight from `categories` means
 * that render never happens at all.
 *
 * `effectiveBoard` collapses a stale `activeBoard` (a slug no longer present
 * in `categories`) to `null` — the SAME value both the "All" chip and every
 * per-board chip in `CategoryListPage` read their `active` state from, so a
 * stale selection can never leave the chip row and the filtered list
 * disagreeing about what's selected (raw `activeBoard` itself is left
 * untouched in the page's own state; only the derived read is collapsed).
 *
 * Lives in its own module (not `CategoryListPage.tsx`) so it stays a plain
 * function export the page can import — a page component file may only
 * export components (react-refresh/only-export-components).
 *
 * Exported for a direct unit test: the browser scenario this guards against
 * (select a chip, then a refetch drops that board) has no reachable trigger
 * in the current UI to exercise end-to-end — `CategoryListPage`'s only
 * refetch path is `ForumErrorState`'s Retry, which is only reachable from an
 * *error* render, and that render replaces the whole board section (no chips
 * to have selected beforehand). See CategoryListPage.test.tsx's "stale
 * activeBoard filter" describe block.
 */
export function resolveBoardFilter(
  categories: Category[],
  activeBoard: string | null
): { effectiveBoard: string | null; visibleCategories: Category[] } {
  const activeBoardExists = activeBoard !== null && categories.some((c) => c.slug === activeBoard);
  const effectiveBoard = activeBoardExists ? activeBoard : null;
  return {
    effectiveBoard,
    visibleCategories: effectiveBoard
      ? categories.filter((c) => c.slug === effectiveBoard)
      : categories,
  };
}
