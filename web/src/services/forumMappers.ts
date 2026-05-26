import { slugifyTitle } from '../utils/forumUrls';
import type { Category, Thread, Post, Attachment } from '../types/forum';

// Backend response shapes (machina-flavored). Kept local — internal to the service layer.
export interface BackendUser {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
}
export interface BackendForum {
  id: number;
  name: string;
  description?: string;
  topics_count?: number;
  posts_count?: number;
  last_activity?: string | null;
  slug?: string | null;
}
export interface BackendTopic {
  id: number;
  subject: string;
  poster: BackendUser | null;
  forum: { id: number; name: string; slug?: string | null } | null;
  created: string;
  posts_count?: number;
  last_post_on?: string | null;
  replies_count?: number;
  views_count?: number;
}
export interface BackendPost {
  id: number;
  content: string;
  poster: BackendUser | null;
  created: string;
  updated?: string;
  content_format?: string;
}
export interface BackendImage {
  id: number;
  image_url?: string | null;
  thumbnail_url?: string | null;
  large_thumbnail_url?: string | null;
  upload_order?: number;
  alt_text?: string;
  original_filename?: string;
  file_size?: number;
  created_at?: string;
}

type ForumAuthor = Thread['author'];

const DELETED_USER = {
  id: '',
  username: '[deleted]',
  display_name: '[deleted]',
} as unknown as ForumAuthor;

export function mapUser(u: BackendUser | null): ForumAuthor {
  if (!u) return DELETED_USER;
  const fullName = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
  // Translation boundary: the backend user shape is narrower than the auth `User`
  // type the forum reuses, and forum ids are strings. Cast through `unknown`.
  return {
    id: String(u.id),
    username: u.username,
    display_name: fullName || u.username,
  } as unknown as ForumAuthor;
}

export function mapForumToCategory(f: BackendForum): Category {
  return {
    id: String(f.id),
    name: f.name,
    slug: f.slug || slugifyTitle(f.name),
    description: f.description,
    thread_count: f.topics_count ?? 0,
    post_count: f.posts_count ?? 0,
    created_at: f.last_activity || '',
  };
}

export function mapTopicToThread(t: BackendTopic): Thread {
  const category: Category = t.forum
    ? {
        id: String(t.forum.id),
        name: t.forum.name,
        slug: t.forum.slug || slugifyTitle(t.forum.name),
        created_at: '',
      }
    : { id: '', name: '', slug: '', created_at: '' };
  return {
    id: String(t.id),
    title: t.subject,
    slug: slugifyTitle(t.subject),
    category,
    author: mapUser(t.poster),
    created_at: t.created,
    last_activity_at: t.last_post_on || t.created,
    post_count: t.posts_count ?? 0,
    view_count: t.views_count ?? 0,
    is_pinned: false,
    is_locked: false,
    is_active: true,
  };
}

export function mapPostToPost(p: BackendPost, threadId: string): Post {
  return {
    id: String(p.id),
    thread: threadId,
    author: mapUser(p.poster),
    content_raw: p.content,
    content_html: p.content,
    content_format: p.content_format || 'html',
    created_at: p.created,
    updated_at: p.updated,
    is_active: true,
    reaction_counts: {},
  };
}

export function mapImageToAttachment(img: BackendImage): Attachment {
  return {
    id: String(img.id),
    image: img.image_url || undefined,
    image_url: img.image_url || undefined,
    thumbnail_url: img.thumbnail_url || undefined,
    image_thumbnail: img.thumbnail_url || undefined,
    thumbnail: img.thumbnail_url || undefined,
    large_url: img.large_thumbnail_url || undefined,
    display_order: img.upload_order,
    alt_text: img.alt_text,
    original_filename: img.original_filename,
    file_size: img.file_size,
    created_at: img.created_at,
    uploaded_at: img.created_at,
  };
}
