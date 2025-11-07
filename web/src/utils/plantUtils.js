/**
 * Generate a unique key for a plant suggestion to track save status.
 * Uses plant name, scientific name, and probability to ensure uniqueness.
 *
 * @param {Object} suggestion - Plant identification suggestion
 * @param {string} suggestion.plant_name - Common name of the plant
 * @param {string} [suggestion.scientific_name] - Scientific name (optional)
 * @param {number} suggestion.probability - Confidence score (0-1)
 * @returns {string} Unique plant key for tracking
 */
export function getPlantKey(suggestion) {
  const scientificName = suggestion.scientific_name || 'unknown'
  const probability = suggestion.probability.toFixed(4) // 4 decimal places for precision
  return `${suggestion.plant_name}-${scientificName}-${probability}`
}
