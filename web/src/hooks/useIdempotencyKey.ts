import { useCallback, useMemo, useRef } from 'react';
import { newIdempotencyKey } from '../utils/idempotencyKey';

/**
 * The Idempotency-Key of one compose action (audit F144), the rule the
 * TipTapEditor image upload and the Flutter composer already follow:
 *
 * - the SAME payload sent again (a retry after a lost response) reuses the
 *   key, so the backend replays the first result instead of posting twice;
 * - a CHANGED payload gets a new key (the server 422s a reused key with a
 *   different body);
 * - after a success, call `reset()`: the same words sent on purpose again
 *   are a new post, not a replay of the old one.
 *
 * `fingerprint` is any string that changes with the payload AND its target
 * (e.g. `JSON.stringify([topicId, body])`). Held in a ref at the page, not in
 * the composer: the reply editor is remounted (`key`) after every post.
 */
export function useIdempotencyKey(): {
  keyFor: (fingerprint: string) => string;
  reset: () => void;
} {
  const ref = useRef<{ fingerprint: string; key: string } | null>(null);
  const keyFor = useCallback((fingerprint: string) => {
    if (ref.current?.fingerprint !== fingerprint) {
      ref.current = { fingerprint, key: newIdempotencyKey() };
    }
    return ref.current.key;
  }, []);
  const reset = useCallback(() => {
    ref.current = null;
  }, []);
  return useMemo(() => ({ keyFor, reset }), [keyFor, reset]);
}
