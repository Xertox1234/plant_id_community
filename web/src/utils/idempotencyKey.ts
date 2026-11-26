/**
 * A fresh Idempotency-Key. `randomUUID` is unavailable on insecure origins and
 * in some test DOMs, so fall back rather than throw — a missing key only costs
 * the replay guarantee, while an exception would break the write outright.
 */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `forum-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
