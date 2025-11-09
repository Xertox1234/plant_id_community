import type { PlantSuggestion } from '@/types'

/**
 * Generate a unique key for a plant suggestion to track save status.
 * Uses plant name, scientific name, and probability to ensure uniqueness.
 *
 * @param suggestion - Plant identification suggestion
 * @returns Unique plant key for tracking
 */
export function getPlantKey(suggestion: PlantSuggestion): string {
  const scientificName = suggestion.scientific_name || 'unknown'
  const probability = suggestion.probability.toFixed(4) // 4 decimal places for precision
  return `${suggestion.plant_name}-${scientificName}-${probability}`
}
