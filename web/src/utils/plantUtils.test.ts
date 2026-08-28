import { describe, it, expect } from 'vitest';
import { getPlantKey } from './plantUtils';
import type { PlantIdentificationResult } from '@/types';

describe('getPlantKey', () => {
  it('does not throw on a probability-only suggestion (real API shape, todo 313)', () => {
    // Real `suggestions[]` items never carry `confidence` — only
    // `probability`. This is the exact shape that crashed unconditionally
    // on every successful identification before the fix.
    const suggestion: PlantIdentificationResult = {
      plant_name: 'Monstera deliciosa',
      probability: 0.99,
      source: 'plant_id',
    };

    expect(() => getPlantKey(suggestion)).not.toThrow();
    expect(getPlantKey(suggestion)).toBe('Monstera deliciosa-0.9900');
  });

  it('falls back to confidence when probability is absent', () => {
    const suggestion: PlantIdentificationResult = {
      plant_name: 'Monstera deliciosa',
      confidence: 0.5,
      source: 'plant_id',
    };
    expect(getPlantKey(suggestion)).toBe('Monstera deliciosa-0.5000');
  });

  it('falls back to 0 when neither is present', () => {
    const suggestion: PlantIdentificationResult = {
      plant_name: 'Monstera deliciosa',
      source: 'plant_id',
    };
    expect(getPlantKey(suggestion)).toBe('Monstera deliciosa-0.0000');
  });
});
