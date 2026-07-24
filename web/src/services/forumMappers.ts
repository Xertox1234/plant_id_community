import type { StreamFieldBlock } from '../types/blog';
import type { Category, Thread, Post, ForumAuthor } from '../types/forum';

// ---------------------------------------------------------------------------
// Backend shapes — wagtail_forum API contract
// ---------------------------------------------------------------------------

export interface BackendBoard {
  id: number;
  title: string;
  slug: string;
  description?: string;
  topic_count?: number;
  post_count?: number;
}

export interface BackendTopicListItem {
  id: number;
  title: string;
  slug: string;
  // Unified author object (todo 257 H26) — a deleted author is the `[deleted]`
  // sentinel object, never null. last_post_author is object-or-null.
  author: BackendAuthor;
  is_pinned: boolean;
  is_closed: boolean;
  locked: boolean;
  reply_count: number;
  view_count: number;
  last_post_at: string | null;
  last_post_author: BackendAuthor | null;
  is_unread: boolean;
}

export interface BackendTopicDetail {
  id: number;
  title: string;
  slug: string;
  board: { id: number; slug: string; title: string };
  author: BackendAuthor;
  is_pinned: boolean;
  is_closed: boolean;
  locked: boolean;
  reply_count: number;
  view_count: number;
  created_at: string;
  last_post_at: string | null;
  last_post_author: BackendAuthor | null;
  opening_post_id: number | null;
  is_subscribed: boolean;
}

// StreamFieldBlock re-exported for consumers that import backend shapes from this module.
export type { StreamFieldBlock } from '../types/blog';

// The unified author object every topic/post payload carries (backend
// serialize_forum_author, todo 257 H26/M41). A deleted author is the
// `[deleted]` sentinel object, never null.
export interface BackendAuthor {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
}

export interface BackendPost {
  id: number;
  topic_id: number;
  author: BackendAuthor;
  body: StreamFieldBlock[];
  created_at: string;
  updated_at?: string;
  edited_at?: string | null;
  is_opening_post: boolean;
  status: 'live' | 'pending';
  reaction_counts: Record<string, number>;
  can_edit: boolean;
  can_delete: boolean;
  can_report: boolean;
}

export interface BackendSearchTopic {
  id: number;
  slug: string;
  title: string;
  reply_count: number;
  view_count: number;
  last_post_at: string | null;
  board_id: number;
  board_slug: string;
}

export interface BackendSearchPost {
  id: number;
  topic_id: number;
  topic_title: string;
  topic_slug: string;
  board_id: number;
  board_slug: string;
  excerpt: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Map the backend author object to the unified ForumAuthor used by both
 * Thread.author and Post.author (todo 257 H26). The backend already sends the
 * `[deleted]` sentinel object for a deleted author, so this mostly passes
 * through; the null branch covers `last_post_author` and the search payloads,
 * which carry no author. No casts — the shapes line up exactly.
 */
function mapAuthor(a: BackendAuthor | null): ForumAuthor {
  if (!a) {
    return { username: '[deleted]', display_name: '[deleted]', avatar: null, trust_level: null };
  }
  return {
    username: a.username,
    display_name: a.display_name || a.username,
    avatar: a.avatar,
    trust_level: a.trust_level,
  };
}

// ---------------------------------------------------------------------------
// Mappers
// ---------------------------------------------------------------------------

export function mapBoardToCategory(b: BackendBoard): Category {
  return {
    id: String(b.id),
    name: b.title,
    slug: b.slug,
    description: b.description,
    thread_count: b.topic_count ?? 0,
    post_count: b.post_count ?? 0,
    created_at: '',
  };
}

export function mapTopicListItemToThread(t: BackendTopicListItem): Thread {
  return {
    id: String(t.id),
    title: t.title,
    slug: t.slug,
    // No category info on the list item — caller must supply or leave empty
    category: { id: '', name: '', slug: '', created_at: '' },
    author: mapAuthor(t.author),
    // list item has no created_at; use last_post_at as best proxy
    created_at: t.last_post_at || '',
    last_activity_at: t.last_post_at || '',
    post_count: t.reply_count,
    view_count: t.view_count,
    is_pinned: t.is_pinned,
    // Same rule as the detail mapper: the write guard is is_closed OR locked.
    is_locked: t.is_closed || t.locked,
    is_active: true,
    is_unread: t.is_unread,
  };
}

export function mapTopicDetailToThread(t: BackendTopicDetail): Thread {
  const category: Category = {
    id: String(t.board.id),
    name: t.board.title,
    slug: t.board.slug,
    created_at: '',
  };
  return {
    id: String(t.id),
    title: t.title,
    slug: t.slug,
    category,
    author: mapAuthor(t.author),
    created_at: t.created_at,
    last_activity_at: t.last_post_at || t.created_at,
    post_count: t.reply_count,
    view_count: t.view_count,
    is_pinned: t.is_pinned,
    is_locked: t.is_closed || t.locked,
    is_active: true,
    is_subscribed: t.is_subscribed,
  };
}

export function mapPostToPost(p: BackendPost, threadId: string): Post {
  return {
    id: String(p.id),
    thread: threadId,
    author: mapAuthor(p.author),
    content_raw: '', // StreamField body — no plain-text equivalent; Task 6 renders body blocks
    content_html: undefined,
    content_format: 'draftail',
    body: p.body,
    created_at: p.created_at,
    updated_at: p.updated_at,
    edited_at: p.edited_at ?? undefined,
    is_first_post: p.is_opening_post,
    is_active: p.status === 'live',
    reaction_counts: p.reaction_counts ?? {},
    can_edit: p.can_edit,
    can_delete: p.can_delete,
    can_report: p.can_report,
  };
}

export function mapSearchTopicToThread(t: BackendSearchTopic): Thread {
  return {
    id: String(t.id),
    title: t.title,
    slug: t.slug,
    category: { id: String(t.board_id), name: '', slug: t.board_slug, created_at: '' },
    // Search payload carries no author (BackendSearchTopic) → sentinel author.
    author: mapAuthor(null),
    // Search payload carries no creation time; only last activity. Don't alias
    // last_post_at as created_at (that misrepresents it downstream).
    created_at: '',
    last_activity_at: t.last_post_at || '',
    post_count: t.reply_count,
    view_count: t.view_count,
    is_active: true,
  };
}

export function mapSearchPostToPost(p: BackendSearchPost): Post {
  return {
    id: String(p.id),
    thread: String(p.topic_id),
    // Search payload carries no author (BackendSearchPost) → sentinel author.
    author: mapAuthor(null),
    content_raw: p.excerpt,
    content_format: 'plain',
    body: [],
    created_at: '',
    is_active: true,
    reaction_counts: {},
    can_edit: false,
    can_delete: false,
    can_report: false,
    topic_title: p.topic_title,
    topic_slug: p.topic_slug,
    board_id: p.board_id,
    board_slug: p.board_slug,
  };
}
