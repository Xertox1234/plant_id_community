/**
 * Central Type Definitions Export
 *
 * Import types from here for consistency:
 * import type { User, Thread, BlogPost } from '@/types';
 */

// API types
export type {
  ApiResponse,
  WagtailApiResponse,
  DRFPaginatedResponse,
  ApiError,
} from './api';

// Authentication types
export type {
  User,
  LoginCredentials,
  SignupData,
  AuthResponse,
} from './auth';

// Forum types
export type {
  Category,
  Thread,
  Post,
  Attachment,
  CreateThreadData,
  CreatePostData,
} from './forum';

// Blog types
export type {
  StreamFieldBlock,
  ParagraphBlock,
  HeadingBlock,
  ImageBlock,
  QuoteBlock,
  CodeBlock,
  ListBlock,
  BlogPost,
} from './blog';

// Diagnosis types
export type {
  PlantIdentification,
  DiagnosisRequest,
  DiagnosisResponse,
  HealthAssessment,
  Disease,
} from './diagnosis';
