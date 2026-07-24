import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Scroll the window to the top whenever the pathname changes.
 *
 * SPA route changes otherwise preserve the previous page's scroll offset —
 * arriving on a new forum page mid-scroll (audit M31). A change of only the
 * query string (sort, Load More) leaves the pathname untouched, so those stay
 * in place; a URL hash (deep link to #post-N) suppresses the reset so anchor
 * scrolling still works.
 */
export function useScrollToTop(): void {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) return;
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [pathname, hash]);
}
