import type { PlantIdentificationResult } from '@/types';

/**
 * Generate a unique key for a plant suggestion to track save status.
 * Uses plant name and confidence to ensure uniqueness.
 *
 * @param suggestion - Plant identification suggestion
 * @returns Unique plant key for tracking
 */
export function getPlantKey(suggestion: PlantIdentificationResult): string {
  // Items in `suggestions[]` only ever carry `probability`, never
  // `confidence` (that field is top-level-result-only) — fall back the same
  // way IdentifyPage.handleAskCommunity does, rather than assume either is
  // present (todo 313: this crashed unconditionally on every real result).
  const raw = suggestion.probability ?? suggestion.confidence ?? 0;
  const confidence = raw.toFixed(4); // 4 decimal places for precision
  return `${suggestion.plant_name}-${confidence}`;
}
