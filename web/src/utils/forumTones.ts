import type { TileTone } from '../components/ui/Tile';
import { hashString } from './hashString';

const TONES: TileTone[] = ['sage', 'pollen', 'bloom', 'orchid'];

/**
 * Deterministic accent tone per board slug, so a board wears the same tile
 * color on every surface (same hash as specimenAvatar, via hashString).
 */
export function boardTone(slug: string): TileTone {
  return TONES[hashString(slug) % TONES.length];
}
