import type { PlantIdentificationResult } from '@/types'

/**
 * Generate a unique key for a plant suggestion to track save status.
 * Uses plant name and confidence to ensure uniqueness.
 *
 * @param suggestion - Plant identification suggestion
 * @returns Unique plant key for tracking
 */
export function getPlantKey(suggestion: PlantIdentificationResult): string {
  const confidence = suggestion.confidence.toFixed(4) // 4 decimal places for precision
  return `${suggestion.plant_name}-${confidence}`
}
