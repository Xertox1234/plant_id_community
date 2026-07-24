/**
 * Shared forum-author constants — single source for values that were being
 * re-declared per component (react-typescript review, todo 257 slice B).
 */

/** The sentinel username the backend sends for a deleted author (M41). */
export const DELETED_AUTHOR_USERNAME = '[deleted]';

/** Forum trust levels mirror the backend ForumProfile.TrustLevel enum (0–4). */
export const TRUST_LEVEL_LABELS: Record<number, string> = {
  0: 'New',
  1: 'Basic',
  2: 'Member',
  3: 'Regular',
  4: 'Leader',
};
