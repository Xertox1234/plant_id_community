import type { TileTone } from '../components/ui/Tile';

const TONES: TileTone[] = ['sage', 'pollen', 'bloom', 'orchid'];

/**
 * Deterministic accent tone per board slug, so a board wears the same tile
 * color on every surface (same hash shape as specimenAvatar).
 */
export function boardTone(slug: string): TileTone {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) >>> 0;
  }
  return TONES[hash % TONES.length];
}
