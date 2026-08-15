/**
 * Forum Entity Types
 */

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
  /** ISO timestamp of the newest live topic's activity; null when nobody has posted. */
  last_post_at?: string | null;
  children?: Category[];
}

/**
 * The forum home payload — boards plus the `ForumIndex` welcome copy the CMS
 * owns. One backend response (`GET boards/`), because both render on the same
 * screen and always change together (todo 278 L2).
 */
export interface ForumIndexPayload {
  categories: Category[];
  /** Sanitized HTML from the CMS; `''` when no intro is set. */
  intro: string;
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
 * One suggested species inside an attached identification snapshot (audit M6).
 * `confidence` is 0–1, not a percentage.
 */
export interface IdentificationCandidate {
  name: string;
  scientific_name?: string;
  confidence: number;
}

/**
 * The plant-ID snapshot a topic carries (audit M6) — detail payload ONLY.
 *
 * Author-supplied, not a verified determination: the backend records what the
 * app suggested to the person who posted, so the card must be labelled as such
 * and never presented as an authoritative ID. `image` is null when the photo
 * was never attached or has since been deleted (the FK is SET_NULL) — the card
 * falls back to text-only rather than disappearing.
 */
export interface ThreadIdentification {
  image: {
    id: number;
    url: string;
    alt: string;
    width: number;
    height: number;
  } | null;
  provider: string;
  candidates: IdentificationCandidate[];
  created_at: string;
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
  /** Secondary discovery taxonomy beside the board (audit M5). Normalized lowercase. */
  tags?: string[];
  /**
   * Accepted-answer state (audit H6). `is_solved` drives the Solved badge on
   * both the list and the thread; `solved_post_id` is the id of the accepted
   * post so the thread can highlight it. The backend clears both when the
   * accepted post stops being visible, so a true `is_solved` always points at
   * a readable post.
   */
  is_solved?: boolean;
  solved_post_id?: number | null;
  /** Detail-only: whether the CURRENT viewer may accept/clear an answer here. */
  can_mark_solution?: boolean;
  /**
   * Detail-only: the plant-ID snapshot attached at compose time (audit M6).
   * Absent on list/search payloads by design — the card renders above the
   * opening post and nowhere else.
   */
  identification?: ThreadIdentification | null;
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
  /** Reaction types the current user has active on this post (M23); [] when
   * logged out. Drives the reaction buttons' aria-pressed / pressed styling. */
  reacted?: string[];
  /** Permission flags from the backend (wagtail_forum PostSerializer). */
  can_edit?: boolean;
  can_delete?: boolean;
  can_report?: boolean;
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
 * Update post input — body is HTML; the service wraps it as a paragraph block.
 */
export interface UpdatePostInput {
  content: string;
}

/**
 * The write shape of an identification snapshot (audit M6). Distinct from the
 * read shape `ThreadIdentification`: the request carries a bare `image_id` the
 * caller already uploaded via `uploadPostImage`, while the response carries the
 * resolved rendition object.
 */
export interface CreateIdentificationInput {
  image_id?: number | null;
  provider?: string;
  candidates: IdentificationCandidate[];
}

/** Create-topic input (POST /boards/{slug}/topics/). content is HTML. */
export interface CreateTopicInput {
  boardSlug: string;
  title: string;
  content: string;
  /** Optional secondary taxonomy (audit M5). Server normalizes + bounds them. */
  tags?: string[];
  /**
   * Optional plant-ID snapshot to attach (audit M6) — the "Ask the community"
   * flow. The server bounds candidate count/length and requires `image_id` to
   * be an image THIS user uploaded to the forum collection.
   */
  identification?: CreateIdentificationInput | null;
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

/** A public forum profile (GET /forum/users/{username}/, todo 257 H7). */
export interface ForumUserProfile {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  bio: string;
  signature: string;
  /** Lifetime denormalized post count — not the length of recent_posts. */
  post_count: number;
  joined_at: string | null;
  recent_topics: {
    id: number;
    slug: string;
    title: string;
    board_id: number;
    board_slug: string;
    reply_count: number;
    created_at: string;
  }[];
  recent_posts: {
    id: number;
    topic_id: number;
    topic_slug: string;
    topic_title: string;
    board_id: number;
    board_slug: string;
    created_at: string;
  }[];
}

/** GET me/stats/ — all-time counts ("Your season" cards). */
export interface ForumMyStats {
  posts: number;
  solutions_accepted: number;
  identifications_shared: number;
}

/** GET topics/recent/ row — the landing rail's "Active now" shape. */
export interface RecentTopic {
  id: number;
  slug: string;
  title: string;
  board: { id: number; name: string; slug: string };
  reply_count: number;
  last_post_at: string | null;
  is_pinned: boolean;
  thumbnail_url: string | null;
}

/** GET users/experts/ row — serialize_forum_author + title. */
export interface ForumExpert {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  title: string;
}
