import type { PlantSuggestion } from '@/types';

/**
 * Generate a unique key for a plant suggestion to track save status.
 * Uses plant name and confidence to ensure uniqueness.
 *
 * @param suggestion - Plant identification suggestion
 * @returns Unique plant key for tracking
 */
export function getPlantKey(suggestion: PlantSuggestion): string {
  // `PlantSuggestion.probability` is required (todo 316) — the old
  // `?? suggestion.confidence ?? 0` fallback existed because a shared type
  // let `confidence` compile here even though suggestion items never carry
  // it (todo 313: crashed unconditionally on every real result). The split
  // makes that mistake a compile error instead, so no fallback is needed.
  const confidence = suggestion.probability.toFixed(4); // 4 decimal places for precision
  return `${suggestion.plant_name}-${confidence}`;
}
