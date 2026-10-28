import { useEffect, useState } from 'react';
import { fetchForumCategory } from '../services/forumService';
import type { Category } from '@/types';

/**
 * The category a forum sits under, for the Category › Forum breadcrumb on the
 * thread list and thread pages (todo 665). null until known, and whenever it
 * cannot be told: the crumb is decoration, so it never delays or fails a page.
 *
 * Keyed on the forum id it was fetched for, so navigating from one forum to
 * another never shows the previous forum's category while the new one loads.
 */
export function useForumCategory(forumId: string | number | null | undefined): Category | null {
  const key = forumId == null || forumId === '' ? null : String(forumId);
  const [resolved, setResolved] = useState<{ key: string; category: Category | null } | null>(null);

  useEffect(() => {
    if (key === null) return;
    let ignore = false;
    // Promise.resolve: an auto-mocked service returns undefined, not a promise.
    Promise.resolve(fetchForumCategory(key))
      .then((category) => {
        if (!ignore) setResolved({ key, category: category ?? null });
      })
      .catch(() => {
        if (!ignore) setResolved({ key, category: null });
      });
    return () => {
      ignore = true;
    };
  }, [key]);

  return resolved !== null && resolved.key === key ? resolved.category : null;
}
