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
 * Forum author — the unified object every topic/post/notification-actor payload
 * shares (backend serialize_forum_author, todo 257 H26/M41). A deleted author is
 * the `[deleted]` sentinel object, never null. `trust_level` is the backend
 * ForumProfile integer enum (0=New … 4=Leader) or null when the author has no
 * profile; `avatar` is an absolute image URL or null.
 */
export interface ForumAuthor {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
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
  author: ForumAuthor;
  created_at: string;
  updated_at?: string;
  last_activity_at: string;
  post_count?: number;
  view_count?: number;
  is_pinned?: boolean;
  is_locked?: boolean;
  is_active?: boolean;
  is_subscribed?: boolean;
  is_unread?: boolean;
}

/**
 * Forum post
 */
export interface Post {
  id: string;
  thread: string;
  // Same unified ForumAuthor object as Thread.author (todo 257 H26): username,
  // display_name, avatar, and the ForumProfile integer trust_level.
  author: ForumAuthor;
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
  /** Search-result-only link identity (mapSearchPostToPost). */
  topic_slug?: string;
  board_id?: number;
  board_slug?: string;
  created_at: string;
  updated_at?: string;
  edited_at?: string;
  edited_by?: {
    username: string;
    display_name?: string;
  };
  is_edited?: boolean;
  is_first_post?: boolean;
  is_active?: boolean;
  reaction_counts?: Record<string, number>;
  /** Permission flags from the backend (wagtail_forum PostSerializer). */
  can_edit?: boolean;
  can_delete?: boolean;
  can_report?: boolean;
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
  /** Board slug — sent to the backend as ?board= */
  category?: string;
  /** 1-based page; only sent to the backend when > 1. */
  page?: number;
}

export interface SearchForumResponse {
  query: string;
  threads: Thread[];
  posts: Post[];
  /** Length of THIS response's threads/posts (per page), not a grand total. */
  total_threads: number;
  total_posts: number;
  /** Whether a further page of thread/post results exists. */
  has_more_threads: boolean;
  has_more_posts: boolean;
}

/** Result of toggling a reaction on a post (backend toggle endpoint). */
export interface ReactionToggleResult {
  /** Map of reaction_type -> count, e.g. { like: 5, love: 2 } */
  reaction_counts: Record<string, number>;
  /** Whether the current user now has this reaction active on the post. */
  reacted: boolean;
}
