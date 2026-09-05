import { useEffect, useRef } from 'react';

/**
 * Run `onSwap` when the signed-in identity changes from one real account to
 * ANOTHER — never on mount/reload (the stored → confirmed same identity), and
 * never across an expire → same-account re-login.
 *
 * Mirrors the AuthContext effect that drops sessionStorage composer drafts on
 * a passive account swap (audit 2026-09-04 L4). Clearing storage is not
 * enough on its own: a mounted composer still holds the previous account's
 * text in React state and would re-persist it under the same topic key on
 * the next keystroke (code review, PR #629). Pages own their state, so each
 * composer page calls this with its own reset.
 */
export function useIdentitySwap(userId: number | null | undefined, onSwap: () => void): void {
  const lastOwnerRef = useRef<number | null>(null);
  const onSwapRef = useRef(onSwap);
  // Written in an effect, not during render (react-hooks/refs).
  useEffect(() => {
    onSwapRef.current = onSwap;
  });
  useEffect(() => {
    const nextId = userId ?? null;
    if (nextId === null) return;
    if (lastOwnerRef.current !== null && lastOwnerRef.current !== nextId) {
      onSwapRef.current();
    }
    lastOwnerRef.current = nextId;
  }, [userId]);
}
