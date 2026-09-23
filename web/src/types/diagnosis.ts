/**
 * Plant disease diagnosis types (the live /diagnose flow).
 */

/**
 * Disease diagnosis request status — mirrors the backend PlantDiseaseRequest.status
 * choices (apps/plant_identification/models.py).
 */
export type DiseaseRequestStatus = 'pending' | 'processing' | 'diagnosed' | 'needs_help' | 'failed';

/**
 * One AI disease diagnosis result — mirrors PlantDiseaseResultSerializer.
 */
export interface PlantDiseaseResult {
  id: number;
  uuid: string;
  request_id: string;
  suggested_disease_name: string;
  suggested_disease_type: string;
  confidence_score: number;
  confidence_percentage: number;
  diagnosis_source: string; // "api_plant_health" | "system_message" | ...
  severity_assessment: string;
  symptoms_identified: string;
  recommended_treatments: string;
  immediate_actions: string;
  notes: string;
  is_primary: boolean;
  display_name: string;
}

/**
 * Response of GET /disease-requests/{uuid}/results/.
 */
export interface DiseaseDiagnosisResults {
  request_id: string;
  status: DiseaseRequestStatus;
  results: PlantDiseaseResult[];
}

/**
 * Response of POST /disease-requests/ (create).
 */
export interface DiseaseDiagnosisCreated {
  request_id: string;
  status: DiseaseRequestStatus;
}
