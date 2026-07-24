import type { Category, Thread } from '../types/forum';

/** Lowercase, hyphenate, strip non-alphanumerics. Falls back to "topic" when empty. */
export function slugifyTitle(input: string): string {
  const slug = (input || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'topic';
}

/** Extract the leading integer id from an "id-slug" route param. Returns null if absent. */
export function parseLeadingId(param: string | undefined): number | null {
  if (!param) return null;
  const id = parseInt(param.split('-')[0], 10);
  return Number.isNaN(id) ? null : id;
}

/** /forum/{id}-{slug} — id is the lookup key, slug is decorative. */
export function categoryPath(category: Pick<Category, 'id' | 'slug' | 'name'>): string {
  const slug = category.slug || slugifyTitle(category.name);
  return `/forum/${category.id}-${slug}`;
}

/** /forum/{catId}-{catSlug}/{topicId}-{topicSlug} */
export function threadPath(
  category: Pick<Category, 'id' | 'slug' | 'name'>,
  thread: Pick<Thread, 'id' | 'slug' | 'title'>
): string {
  const tSlug = thread.slug || slugifyTitle(thread.title);
  return `${categoryPath(category)}/${thread.id}-${tSlug}`;
}

/** Fragment identifier for a specific post inside a thread page. */
export function postAnchor(postId: number | string): string {
  return `#post-${postId}`;
}

/** Public forum profile page for a username (todo 257 H7). */
export function userProfilePath(username: string): string {
  return `/forum/users/${encodeURIComponent(username)}`;
}
