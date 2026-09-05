import type { Category, EventHeroTopic, RecentTopic, Thread } from '../types/forum';

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

/** Direct-message thread with a member (todo 339); `/messages` is the inbox. */
export function conversationPath(username: string): string {
  return `/messages/${encodeURIComponent(username)}`;
}

/**
 * Path for a topics/recent row: /forum/{board.id}-{board.slug}/{id}-{slug}.
 *
 * Delegates to `threadPath` (which itself composes `categoryPath`) instead of
 * re-authoring the template — `RecentTopic.board.id`/`RecentTopic.id` are
 * `number` while `Category.id`/`Thread.id` are `string`, so the id fields are
 * cast to `string` at the call site rather than widening either helper's
 * parameter types repo-wide. Output stays byte-identical to the old literal
 * template for the normal case (board.slug/topic.slug always populated), and
 * both helpers' own slug/id-parsing rules now apply here too, so this can
 * never drift from `categoryPath`/`threadPath`'s format.
 */
export function recentTopicPath(topic: RecentTopic): string {
  return threadPath(
    { id: String(topic.board.id), slug: topic.board.slug, name: topic.board.name },
    { id: String(topic.id), slug: topic.slug, title: topic.title }
  );
}

/** Path for the landing-page event hero's featured topic (todo 304) — same
 * id-coercion shape as `recentTopicPath`, since `EventHeroTopic` carries the
 * same numeric `id`/`board.id` fields DRF returns. */
export function eventHeroTopicPath(topic: EventHeroTopic): string {
  return threadPath(
    { id: String(topic.board.id), slug: topic.board.slug, name: topic.board.name },
    { id: String(topic.id), slug: topic.slug, title: topic.title }
  );
}
