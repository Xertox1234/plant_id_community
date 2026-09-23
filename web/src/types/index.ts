/**
 * Central Type Definitions Export
 *
 * Import types from here for consistency:
 * import type { User, Thread, BlogPost } from '@/types';
 */

// API types
export type { ApiResponse, WagtailApiResponse, DRFPaginatedResponse, ApiError } from './api';

// Authentication types
export type { User, LoginCredentials, SignupData, AuthResponse } from './auth';

// Forum types
export type {
  Category,
  Thread,
  Post,
  LinkPreview,
  SearchForumResponse,
  ThreadIdentification,
  IdentificationCandidate,
  CreateIdentificationInput,
  ForumMyStats,
  RecentTopic,
  ForumExpert,
  EventHero,
  EventHeroTopic,
  ThreadPoll,
  ThreadPollOption,
  CreatePollInput,
  PlantCareAnswer,
  PlantCareSource,
  PlantCareReferralReason,
} from './forum';

// Blog types
export type {
  StreamFieldBlock,
  ParagraphBlock,
  HeadingBlock,
  QuoteBlock,
  CodeBlock,
  BlogPost,
  BlogCategory,
  RelatedPostSummary,
  BlogComment,
  BlogCommentAuthor,
} from './blog';

// Plant Identification types
export type {
  PlantIdentificationResult,
  PlantSuggestion,
  Collection,
  UserPlant,
  SavePlantInput,
} from './plantId';

// Diagnosis types
export type {
  DiseaseRequestStatus,
  PlantDiseaseResult,
  DiseaseDiagnosisResults,
  DiseaseDiagnosisCreated,
} from './diagnosis';
