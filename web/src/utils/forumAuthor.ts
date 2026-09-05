/**
 * Shared forum-author constants and helpers — single source for values that
 * were being re-declared per component (react-typescript review, todo 257
 * slice B; `authorName` was duplicated by both message pages, todo 350).
 */
import type { ForumAuthor } from '../types/forum';

/** The sentinel username the backend sends for a deleted author (M41). */
export const DELETED_AUTHOR_USERNAME = '[deleted]';

/** The name a forum author is shown under: their display name, else their username. */
export function authorName(author: Pick<ForumAuthor, 'display_name' | 'username'>): string {
  return author.display_name || author.username;
}

/** Forum trust levels mirror the backend ForumProfile.TrustLevel enum (0–4). */
export const TRUST_LEVEL_LABELS: Record<number, string> = {
  0: 'New',
  1: 'Basic',
  2: 'Member',
  3: 'Regular',
  4: 'Leader',
};
