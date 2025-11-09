/**
 * Plant Identification Service Types
 */

/**
 * Plant identification result from API
 */
export interface PlantIdentificationResult {
  plant_name: string;
  confidence: number;
  common_names?: string[];
  description?: string;
  watering?: string;
  propagation_methods?: string;
  care_instructions?: {
    watering?: string;
    propagation?: string;
    [key: string]: unknown;
  };
  source: string;
  image_url?: string;
  // Properties for compatibility with IdentificationResults component
  scientific_name?: string;
  probability?: number;
  similar_images?: Array<{ url: string }>;
  suggestions?: PlantIdentificationResult[];
  disease_suggestions?: Array<{
    name: string;
    probability: number;
    description?: string;
  }>;
}

/**
 * User's plant collection
 */
export interface Collection {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Saved plant in user's collection
 */
export interface UserPlant {
  id: string;
  collection: string;
  nickname: string;
  notes: string;
  care_instructions_json: {
    confidence?: number;
    common_names?: string[];
    watering?: string | null;
    propagation?: string | null;
    source?: string;
    [key: string]: unknown;
  };
  created_at?: string;
  updated_at?: string;
}

/**
 * Plant identification history item
 */
export interface IdentificationHistoryItem {
  id: string;
  plant_name: string;
  confidence: number;
  image_url?: string;
  created_at: string;
  source: string;
}

/**
 * Input data for saving plant to collection
 */
export interface SavePlantInput {
  plant_name: string;
  confidence: number;
  common_names?: string[];
  description?: string;
  watering?: string;
  propagation_methods?: string;
  care_instructions?: {
    watering?: string;
    propagation?: string;
    [key: string]: unknown;
  };
  source: string;
}
