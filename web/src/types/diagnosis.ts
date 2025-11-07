/**
 * Plant Diagnosis & Identification Types
 */

/**
 * Plant identification result
 */
export interface PlantIdentification {
  id: string;
  common_name: string;
  scientific_name: string;
  confidence: number;
  thumbnail?: string;
  similar_images?: string[];
}

/**
 * Plant diagnosis request
 */
export interface DiagnosisRequest {
  image: File | string;
  latitude?: number;
  longitude?: number;
}

/**
 * Plant diagnosis response
 */
export interface DiagnosisResponse {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  identifications: PlantIdentification[];
  health_assessment?: HealthAssessment;
  created_at: string;
  completed_at?: string;
}

/**
 * Plant health assessment
 */
export interface HealthAssessment {
  is_healthy: boolean;
  diseases: Disease[];
  overall_health: number;
}

/**
 * Disease identification
 */
export interface Disease {
  name: string;
  confidence: number;
  description?: string;
  treatment?: string;
}
