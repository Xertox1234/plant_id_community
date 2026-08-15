/**
 * Deterministic 31x rolling hash shared by the look-assignment utils
 * (specimen avatars, board tones). One implementation, so the two hashes can
 * never drift apart and a given key always maps to the same bucket everywhere.
 */
export function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}
