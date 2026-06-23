/**
 * Forum Entity Types
 */

import type { User } from './auth';
import type { StreamFieldBlock as BlogStreamFieldBlock } from './blog';

/**
 * Forum category
 */
export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  thread_count?: number;
  post_count?: number;
  created_at: string;
  children?: Category[];
}

/**
 * Forum thread
 */
export interface Thread {
  id: string;
  title: string;
  slug: string;
  excerpt?: string;
  category: Category;
  author: User;
  created_at: string;
  updated_at?: string;
  last_activity_at: string;
  post_count?: number;
  view_count?: number;
  is_pinned?: boolean;
  is_locked?: boolean;
  is_active?: boolean;
}

/**
 * Forum post
 */
export interface Post {
  id: string;
  thread: string;
  // Forum posts carry a free-form trust label distinct from the auth User
  // enum, so override (not intersect) trust_level to a plain string.
  author: Omit<User, 'trust_level'> & {
    trust_level?: string;
  };
  content_raw: string;
  content_html?: string;
  content_format?: string;
  /** StreamField body blocks from wagtail_forum; rendered by StreamFieldRenderer. */
  body?: BlogStreamFieldBlock[];
  /**
   * Set only on search-result posts (from mapSearchPostToPost).
   * The topic title is carried so SearchPage can render a link without a PostCard.
   */
  topic_title?: string;
  created_at: string;
  updated_at?: string;
  edited_at?: string;
  edited_by?: {
    username: string;
    display_name?: string;
  };
  attachments?: Attachment[];
  is_edited?: boolean;
  is_first_post?: boolean;
  is_active?: boolean;
  reaction_counts?: Record<string, number>;
  /** Permission flags from the backend (wagtail_forum PostSerializer). */
  can_edit?: boolean;
  can_delete?: boolean;
}

/**
 * Post attachment (image)
 */
export interface Attachment {
  id: string;
  // The backend serializes exactly these two URL fields; the previous `image`,
  // `image_thumbnail`, `thumbnail`, `medium_url`, `large_url` aliases were all
  // redundant copies the mapper filled from these two (todo 222 / L9).
  image_url?: string; // original image URL
  thumbnail_url?: string; // thumbnail URL
  original_filename?: string;
  file_size?: number;
  mime_type?: string;
  display_order?: number;
  alt_text?: string;
  uploaded_at?: string;
  created_at?: string;
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
  first_post_format?: 'plain' | 'draftail' | 'html';
}

/**
 * Create post input
 */
export interface CreatePostInput {
  thread: string;
  content_raw: string;
  content_format?: 'plain' | 'draftail' | 'html';
}

/**
 * Update post input — body is HTML; the service wraps it as a paragraph block.
 */
export interface UpdatePostInput {
  content: string;
}

/** Create-topic input (POST /boards/{slug}/topics/). content is HTML. */
export interface CreateTopicInput {
  boardSlug: string;
  title: string;
  content: string;
}

/** Create-reply input (POST /topics/{id}/posts/). content is HTML. */
export interface CreateReplyInput {
  thread: number;
  content: string;
}

/** Thin create-topic response — the topic may be pending moderation. */
export interface CreateTopicResult {
  id: string;
  slug: string;
  status: 'published' | 'pending';
}

/** Thin create-reply response — the reply may be pending moderation. */
export interface CreateReplyResult {
  id: string;
  status: 'published' | 'pending';
}

/** Edit response — the (currently-live) post plus its moderation outcome. */
export interface EditPostResult {
  post: Post;
  status: 'published' | 'pending';
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

export interface SearchForumResponse {
  query: string;
  threads: Thread[];
  posts: Post[];
  total_threads: number;
  total_posts: number;
  page: number;
  page_size: number;
  has_next_threads: boolean;
  has_next_posts: boolean;
}

/** Result of toggling a reaction on a post (backend toggle endpoint). */
export interface ReactionToggleResult {
  /** Map of reaction_type -> count, e.g. { like: 5, love: 2 } */
  reaction_counts: Record<string, number>;
  /** Whether the current user now has this reaction active on the post. */
  reacted: boolean;
}
