import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Read a single-use credential from the query string once, then take it out of
 * the address bar (todo 706, audit 2026-11-10 M7).
 *
 * `/verify-email?key=…` and `/unsubscribe?token=…` carry a signed token. Left
 * in the URL it stays in the address bar, in history, in anything that copies
 * the URL (a shared screenshot, a bookmark) and in error reports. The value is
 * captured on the first render and held in state, so the page keeps working
 * after the URL loses it; the URL is then replaced (not pushed), so Back does
 * not bring the token back either. Other query parameters and the hash stay.
 */
export function useOneTimeSearchParam(name: string): string {
  const [params, setParams] = useSearchParams();
  const [value] = useState(() => params.get(name) ?? '');
  const present = params.has(name);

  useEffect(() => {
    if (!present) return;
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete(name);
        return next;
      },
      { replace: true, preventScrollReset: true }
    );
  }, [present, name, setParams]);

  return value;
}
