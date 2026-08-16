import { describe, expect, it } from 'vitest';
import { Bug, Camera, Droplet, LayoutDashboard, Leaf } from 'lucide-react';
import { boardIdentity, boardTone } from './forumTones';

describe('boardTone', () => {
  it('is deterministic for a given slug', () => {
    expect(boardTone('12-plant-care')).toBe(boardTone('12-plant-care'));
  });
  it('returns a valid TileTone for any slug', () => {
    const valid = ['sage', 'pollen', 'bloom', 'orchid'];
    for (const slug of ['a', 'plant-care', '99-show-and-tell', '']) {
      expect(valid).toContain(boardTone(slug));
    }
  });
  it('consults the identity map first for a known Canopy slug', () => {
    // Spec §3 pins this tone — a regression here would mean the map isn't
    // wired into boardTone, silently reverting to the hash fallback.
    expect(boardTone('plant-identification')).toBe('sage');
  });
});

describe('boardIdentity', () => {
  it.each([
    ['plant-identification', 'sage', Leaf, 'Identification'],
    ['care-problems', 'pollen', Droplet, 'Care'],
    ['pests-diseases', 'bloom', Bug, 'Pests'],
    ['garden-design', 'orchid', LayoutDashboard, 'Design'],
    ['show-tell', 'sage', Camera, 'Show & tell'],
  ] as const)('returns the spec identity for %s', (slug, tone, Icon, chipLabel) => {
    const identity = boardIdentity(slug);
    expect(identity.tone).toBe(tone);
    expect(identity.Icon).toBe(Icon);
    expect(identity.chipLabel).toBe(chipLabel);
  });

  it('falls back to a stable hash tone and Leaf icon for an unknown slug', () => {
    const first = boardIdentity('third-party-board');
    const second = boardIdentity('third-party-board');
    expect(first.tone).toBe(second.tone);
    expect(first.Icon).toBe(Leaf);
  });

  it('falls back to the caller-supplied board name for an unknown slug', () => {
    expect(boardIdentity('third-party-board', 'Third Party Board').chipLabel).toBe(
      'Third Party Board'
    );
  });

  it('falls back to the slug itself when no fallback label is given', () => {
    expect(boardIdentity('third-party-board').chipLabel).toBe('third-party-board');
  });
});
