import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchMyForumProfile, saveCollapsedCategories } from '../services/forumService';
import { logger } from '../utils/logger';

/** localStorage key for a guest's collapsed categories (todo 673). */
export const GUEST_COLLAPSED_CATEGORIES_KEY = 'forum:collapsed-categories';

function readGuest(): Set<string> {
  try {
    const raw = window.localStorage.getItem(GUEST_COLLAPSED_CATEGORIES_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    // Private window, blocked storage or a corrupt value: start expanded.
    return new Set();
  }
}

function writeGuest(ids: Set<string>): void {
  try {
    window.localStorage.setItem(GUEST_COLLAPSED_CATEGORIES_KEY, JSON.stringify([...ids]));
  } catch {
    // Storage unavailable: the toggle still works for this visit.
  }
}

interface Viewer {
  isAuthenticated: boolean;
  /** True while AuthProvider is still verifying the session. */
  authLoading?: boolean;
  /** The signed-in identity; a change re-reads that member's state. */
  userId?: string | number | null;
}

/**
 * Which forum-index categories are collapsed (todo 673; phpBB's
 * collapsible-categories extension). A signed-in member's state lives on
 * their forum profile (`collapsed_categories`), so it follows them across
 * sessions and devices; a guest's lives in localStorage.
 *
 * Toggling is optimistic: a failed save is logged and the row stays as the
 * member left it for this visit.
 */
export function useCollapsedCategories({ isAuthenticated, authLoading, userId }: Viewer) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() =>
    isAuthenticated ? new Set() : readGuest()
  );
  // Mirrors the state so a toggle computes from the latest set without
  // being recreated on every change.
  const collapsedRef = useRef(collapsed);
  // A member's save PUTs the whole set, so a toggle before their stored set
  // has loaded would overwrite it with just that one id. Toggles wait for it.
  const loadedRef = useRef(!isAuthenticated);
  // Saves run one after another, so an older set never lands last.
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  const signedIn = isAuthenticated && !authLoading;

  const apply = useCallback((next: Set<string>) => {
    collapsedRef.current = next;
    setCollapsed(next);
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      loadedRef.current = true;
      apply(readGuest());
      return;
    }
    // Keyed on the identity: never show the previous account's state.
    let ignore = false;
    loadedRef.current = false;
    apply(new Set());
    Promise.resolve()
      .then(() => fetchMyForumProfile())
      .then((profile) => {
        if (ignore) return;
        apply(new Set((profile?.collapsed_categories ?? []).map(String)));
        loadedRef.current = true;
      })
      .catch((err) => {
        if (ignore) return;
        logger.error('Error loading collapsed categories', {
          component: 'useCollapsedCategories',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, [isAuthenticated, authLoading, userId, apply]);

  const toggle = useCallback(
    (categoryId: string) => {
      // Until auth resolves we don't know whose state this is, and a member's
      // stored set must load before a toggle can change it.
      if (authLoading || !loadedRef.current) return;
      const next = new Set(collapsedRef.current);
      if (next.has(categoryId)) next.delete(categoryId);
      else next.add(categoryId);
      apply(next);
      if (!signedIn) {
        writeGuest(next);
        return;
      }
      const ids = [...next].map(Number).filter((n) => Number.isInteger(n) && n > 0);
      saveChainRef.current = saveChainRef.current
        .then(() => saveCollapsedCategories(ids))
        .then(
          () => undefined,
          (err) => {
            logger.error('Error saving collapsed categories', {
              component: 'useCollapsedCategories',
              error: err,
            });
          }
        );
    },
    [apply, signedIn, authLoading]
  );

  const isCollapsed = useCallback((categoryId: string) => collapsed.has(categoryId), [collapsed]);

  return { isCollapsed, toggle };
}
