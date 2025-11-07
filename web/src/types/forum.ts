/**
 * Forum Entity Types
 */

import type { User } from './auth';

/**
 * Forum category
 */
export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  thread_count: number;
  post_count: number;
  created_at: string;
}

/**
 * Forum thread
 */
export interface Thread {
  id: string;
  title: string;
  slug: string;
  category: Category;
  author: User;
  created_at: string;
  updated_at: string;
  post_count: number;
  is_pinned: boolean;
  is_locked: boolean;
}

/**
 * Forum post
 */
export interface Post {
  id: string;
  thread: string;
  author: User;
  content_raw: string;
  content_html?: string;
  created_at: string;
  updated_at: string;
  attachments: Attachment[];
  is_edited: boolean;
}

/**
 * Post attachment (image)
 */
export interface Attachment {
  id: string;
  image: string;
  thumbnail?: string;
  uploaded_at: string;
}

/**
 * Thread creation data
 */
export interface CreateThreadData {
  title: string;
  category: string;
  content: string;
}

/**
 * Post creation data
 */
export interface CreatePostData {
  thread: string;
  content: string;
  attachments?: File[];
}

/**
 * Paginated list response
 */
export interface PaginatedResponse<T> {
  items: T[];
  meta: {
    count: number;
    next?: string | null;
    previous?: string | null;
  };
}

/**
 * Fetch threads options
 */
export interface FetchThreadsOptions {
  page?: number;
  limit?: number;
  category?: string;
  search?: string;
  ordering?: string;
}

/**
 * Fetch posts options
 */
export interface FetchPostsOptions {
  thread: string;
  page?: number;
  limit?: number;
  ordering?: string;
}

/**
 * Create thread data
 */
export interface CreateThreadInput {
  title: string;
  category: string;
  excerpt: string;
  first_post_content: string;
  first_post_format?: 'plain' | 'markdown' | 'rich';
}

/**
 * Create post input
 */
export interface CreatePostInput {
  thread: string;
  content_raw: string;
  content_format?: 'plain' | 'markdown' | 'rich';
}

/**
 * Update post input
 */
export interface UpdatePostInput {
  content_raw: string;
  content_format: string;
}

/**
 * Add reaction input
 */
export interface AddReactionInput {
  post: string;
  reaction_type: 'like' | 'love' | 'helpful' | 'thanks';
}

/**
 * Reaction
 */
export interface Reaction {
  id: string;
  post: string;
  user: User;
  reaction_type: string;
  created_at: string;
}

/**
 * Search forum options
 */
export interface SearchForumOptions {
  q: string;
  category?: string;
  author?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}
