/**
 * Frontend Constants
 *
 * Centralized constants for the web frontend.
 * Matches backend values from backend/apps/forum/constants.py
 */

// =============================================================================
// FORUM IMAGE UPLOAD LIMITS
// =============================================================================
// Matches backend: MAX_ATTACHMENTS_PER_POST = 6
export const MAX_IMAGES = 6;

// Matches backend: MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

// Matches backend: ALLOWED_IMAGE_MIME_TYPES
export const ALLOWED_IMAGE_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/gif',
  'image/webp'
];

// =============================================================================
// VALIDATION ERROR MESSAGES
// =============================================================================
export const MAX_IMAGES_ERROR = `Maximum ${MAX_IMAGES} images allowed`;
export const MAX_FILE_SIZE_MB = MAX_FILE_SIZE / 1024 / 1024;
export const FILE_SIZE_ERROR = `File too large. Maximum size: ${MAX_FILE_SIZE_MB}MB`;
export const INVALID_TYPE_ERROR = `Invalid file type. Allowed: ${ALLOWED_IMAGE_TYPES.join(', ')}`;
