import { useEffect, useState } from 'react';

/**
 * Tracks a CSS media query. Reads synchronously on first render (no
 * false-then-true flash for queries that already match), then re-syncs and
 * subscribes in an effect so viewport changes — and a changed `query` — land.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const handleChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    mql.addEventListener('change', handleChange);
    return () => mql.removeEventListener('change', handleChange);
  }, [query]);

  return matches;
}
