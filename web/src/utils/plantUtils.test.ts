import { describe, it, expect } from 'vitest';
import { getPlantKey } from './plantUtils';
import type { PlantSuggestion } from '@/types';

describe('getPlantKey', () => {
  it('does not throw on a probability-only suggestion (real API shape, todo 313)', () => {
    // Real `suggestions[]` items never carry `confidence` — only
    // `probability`. This is the exact shape that crashed unconditionally
    // on every successful identification before the fix.
    const suggestion: PlantSuggestion = {
      plant_name: 'Monstera deliciosa',
      probability: 0.99,
      source: 'plant_id',
    };

    expect(() => getPlantKey(suggestion)).not.toThrow();
    expect(getPlantKey(suggestion)).toBe('Monstera deliciosa-0.9900');
  });

  it('handles a genuinely zero probability without a falsy-vs-missing mixup', () => {
    // `PlantSuggestion.probability` is required (todo 316) — this pins that
    // a real 0 reads through untouched rather than looking "missing".
    const suggestion: PlantSuggestion = {
      plant_name: 'Monstera deliciosa',
      probability: 0,
      source: 'plant_id',
    };
    expect(getPlantKey(suggestion)).toBe('Monstera deliciosa-0.0000');
  });

  // Note: constructing a suggestion with `confidence` instead of
  // `probability`, or omitting `probability` altogether, is now a
  // compile-time error (todo 316) — the fallback tests this file used to
  // have for those cases tested behavior that no longer exists by design.
});
