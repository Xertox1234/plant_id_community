import type { LucideIcon } from 'lucide-react';
import { Bug, Camera, Droplet, LayoutDashboard, Leaf } from 'lucide-react';
import type { TileTone } from '../components/ui/Tile';
import { hashString } from './hashString';

const TONES: TileTone[] = ['sage', 'pollen', 'bloom', 'orchid'];

interface BoardIdentity {
  tone: TileTone;
  Icon: LucideIcon;
  chipLabel: string;
}

/**
 * Deliberate identities for the five Canopy boards (spec §3) — tone, icon,
 * and short chip label are design decisions, not derivations. Unknown slugs
 * fall back to the hash tone + Leaf so third-party boards still render.
 */
const BOARD_IDENTITY: Record<string, BoardIdentity> = {
  'plant-identification': { tone: 'sage', Icon: Leaf, chipLabel: 'Identification' },
  'care-problems': { tone: 'pollen', Icon: Droplet, chipLabel: 'Care' },
  'pests-diseases': { tone: 'bloom', Icon: Bug, chipLabel: 'Pests' },
  'garden-design': { tone: 'orchid', Icon: LayoutDashboard, chipLabel: 'Design' },
  'show-tell': { tone: 'sage', Icon: Camera, chipLabel: 'Show & tell' },
};

export function boardIdentity(slug: string, fallbackLabel = ''): BoardIdentity {
  return (
    BOARD_IDENTITY[slug] ?? {
      tone: TONES[hashString(slug) % TONES.length],
      Icon: Leaf,
      chipLabel: fallbackLabel || slug,
    }
  );
}

/** Deterministic accent tone per board slug (map first, hash fallback). */
export function boardTone(slug: string): TileTone {
  return boardIdentity(slug).tone;
}
