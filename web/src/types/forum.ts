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
