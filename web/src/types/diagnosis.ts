/**
 * Plant Diagnosis & Identification Types
 */

/**
 * Diagnosis StreamField block types
 *
 * Discriminated union: each `type` literal pairs with the matching `value`
 * shape so consumers can narrow on `block.type` without unsafe casts.
 */
interface BaseDiagnosisBlock {
  id?: string;
}

/** CharBlock — simple string value */
export interface HeadingDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'heading';
  value: string;
}

/** TextBlock — simple string value */
export interface ParagraphDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'paragraph';
  value: string;
}

/** TextBlock — simple string value */
export interface PreventionTipDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'prevention_tip';
  value: string;
}

/** StructBlock — title, description, optional frequency */
export interface TreatmentStepDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'treatment_step';
  value: {
    title?: string;
    description?: string;
    frequency?: string;
  };
}

/** StructBlock — symptom name and what to look for */
export interface SymptomCheckDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'symptom_check';
  value: {
    symptom?: string;
    what_to_look_for?: string;
  };
}

/** ListBlock — array of string items */
export interface ListDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'list_block';
  value: {
    items?: string[];
  };
}

/** ImageBlock — rendered in the detail view (not creatable in the editor) */
export interface ImageDiagnosisBlock extends BaseDiagnosisBlock {
  type: 'image';
  value: {
    url?: string;
    alt_text?: string;
    caption?: string;
  };
}

export type DiagnosisBlock =
  | HeadingDiagnosisBlock
  | ParagraphDiagnosisBlock
  | PreventionTipDiagnosisBlock
  | TreatmentStepDiagnosisBlock
  | SymptomCheckDiagnosisBlock
  | ListDiagnosisBlock
  | ImageDiagnosisBlock;

/** The discriminant literal for a diagnosis StreamField block. */
export type DiagnosisBlockType = DiagnosisBlock['type'];

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

/**
 * Treatment status types
 */
export type TreatmentStatus =
  | 'not_started'
  | 'in_progress'
  | 'successful'
  | 'failed'
  | 'monitoring';

/**
 * Disease type categories
 */
export type DiseaseType = 'fungal' | 'bacterial' | 'viral' | 'pest' | 'nutrient' | 'environmental';

/**
 * Severity assessment levels
 */
export type SeverityAssessment = 'mild' | 'moderate' | 'severe' | 'critical';

/**
 * Reminder types
 */
export type ReminderType = 'check_progress' | 'treatment_step' | 'follow_up' | 'reapply';

/**
 * Diagnosis card (saved diagnosis with care instructions)
 */
export interface DiagnosisCard {
  uuid: string;
  diagnosis_result: string;
  plant_scientific_name: string;
  plant_common_name?: string;
  custom_nickname?: string;
  display_name: string; // Derived field (custom_nickname || plant_common_name || plant_scientific_name)
  disease_name: string;
  disease_type: DiseaseType;
  disease_type_display?: string; // Human-readable disease type
  severity_assessment: SeverityAssessment;
  severity_display: string; // Human-readable severity
  confidence_score: number;
  care_instructions: unknown[]; // StreamField blocks
  personal_notes?: string;
  treatment_status: TreatmentStatus;
  treatment_status_display: string; // Human-readable treatment status
  plant_recovered: boolean | null;
  share_with_community: boolean;
  is_favorite: boolean;
  saved_at: string;
  last_updated: string;
}

/**
 * Create diagnosis card input
 */
export interface CreateDiagnosisCardInput {
  diagnosis_result: string;
  plant_scientific_name: string;
  plant_common_name?: string;
  custom_nickname?: string;
  disease_name: string;
  disease_type: DiseaseType;
  severity_assessment: SeverityAssessment;
  confidence_score: number;
  care_instructions: unknown[]; // StreamField blocks
  personal_notes?: string;
  treatment_status?: TreatmentStatus;
  share_with_community?: boolean;
  is_favorite?: boolean;
}

/**
 * Update diagnosis card input
 */
export interface UpdateDiagnosisCardInput {
  custom_nickname?: string;
  care_instructions?: unknown[];
  personal_notes?: string;
  treatment_status?: TreatmentStatus;
  plant_recovered?: boolean;
  share_with_community?: boolean;
  is_favorite?: boolean;
}

/**
 * Fetch diagnosis cards options
 */
export interface FetchDiagnosisCardsOptions {
  treatment_status?: TreatmentStatus;
  is_favorite?: boolean;
  plant_recovered?: boolean;
  disease_type?: DiseaseType;
  search?: string;
  ordering?: string;
  page?: number;
}

/**
 * Diagnosis reminder
 */
export interface DiagnosisReminder {
  uuid: string;
  diagnosis_card: string;
  reminder_type: ReminderType;
  reminder_type_display: string; // Human-readable reminder type
  reminder_title: string;
  reminder_message?: string;
  scheduled_date: string;
  is_active: boolean;
  sent: boolean;
  sent_at?: string;
  snoozed_until?: string;
  cancelled?: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Create reminder input
 */
export interface CreateReminderInput {
  diagnosis_card: string;
  reminder_type: ReminderType;
  reminder_title: string;
  reminder_message?: string;
  scheduled_date: string; // ISO date string
}

/**
 * Fetch reminders options
 */
export interface FetchRemindersOptions {
  diagnosis_card?: string;
  is_active?: boolean;
  sent?: boolean;
  reminder_type?: ReminderType;
}

/**
 * Paginated diagnosis cards response
 */
export interface PaginatedDiagnosisCardsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: DiagnosisCard[];
}

/**
 * Paginated reminders response
 */
export interface PaginatedRemindersResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: DiagnosisReminder[];
}
