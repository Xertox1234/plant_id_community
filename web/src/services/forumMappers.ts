import type { StreamFieldBlock } from '../types/blog';
import type { Category, Thread, Post } from '../types/forum';

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
  author: string | null;
  is_pinned: boolean;
  is_closed: boolean;
  locked: boolean;
  reply_count: number;
  view_count: number;
  last_post_at: string | null;
  last_post_author: string | null;
}

export interface BackendTopicDetail {
  id: number;
  title: string;
  slug: string;
  board: { id: number; slug: string; title: string };
  author: string | null;
  is_pinned: boolean;
  is_closed: boolean;
  locked: boolean;
  reply_count: number;
  view_count: number;
  created_at: string;
  last_post_at: string | null;
  last_post_author: string | null;
  opening_post_id: number | null;
  is_subscribed: boolean;
}

// StreamFieldBlock re-exported for consumers that import backend shapes from this module.
export type { StreamFieldBlock } from '../types/blog';

export interface BackendPostAuthor {
  username: string;
  display_name: string;
  trust_level: string | null;
}

export interface BackendPost {
  id: number;
  topic_id: number;
  author: BackendPostAuthor;
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
}

export interface BackendSearchPost {
  id: number;
  topic_id: number;
  topic_title: string;
  excerpt: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ForumAuthor = Thread['author'];

/** Build a forum author from a plain string username (topic list/detail). */
function authorFromString(username: string | null): ForumAuthor {
  if (!username) {
    return { id: '', username: '[deleted]', display_name: '[deleted]' } as unknown as ForumAuthor;
  }
  return { id: '', username, display_name: username } as unknown as ForumAuthor;
}

/** Build a forum author from the post author object. */
function authorFromObject(a: BackendPostAuthor): ForumAuthor {
  if (a.username === '[deleted]') {
    return { id: '', username: '[deleted]', display_name: '[deleted]' } as unknown as ForumAuthor;
  }
  return {
    id: '',
    username: a.username,
    display_name: a.display_name || a.username,
    trust_level: a.trust_level ?? undefined,
  } as unknown as ForumAuthor;
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
    author: authorFromString(t.author),
    // list item has no created_at; use last_post_at as best proxy
    created_at: t.last_post_at || '',
    last_activity_at: t.last_post_at || '',
    post_count: t.reply_count,
    view_count: t.view_count,
    is_pinned: t.is_pinned,
    // Same rule as the detail mapper: the write guard is is_closed OR locked.
    is_locked: t.is_closed || t.locked,
    is_active: true,
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
    author: authorFromString(t.author),
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
    author: authorFromObject(p.author),
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
    category: { id: '', name: '', slug: '', created_at: '' },
    author: authorFromString(null),
    created_at: '',
    last_activity_at: '',
    is_active: true,
  };
}

export function mapSearchPostToPost(p: BackendSearchPost): Post {
  return {
    id: String(p.id),
    thread: String(p.topic_id),
    author: authorFromString(null),
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
  };
}
