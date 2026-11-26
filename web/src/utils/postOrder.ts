import type { Post } from '@/types';

/**
 * Whether `a` comes after `b` in a thread, under the order the server pages
 * posts in: oldest first by `(created_at, id)` (PostCursorPagination).
 *
 * A live `post.created` is usually the newest reply, but not always: a reply
 * a moderator restores keeps its original `created_at` (audit 2026-11-24
 * F44). Only a post that sorts after the last one loaded may be appended.
 */
export function sortsAfter(a: Post, b: Post): boolean {
  // Parsed, not compared as strings: DRF drops zero microseconds, so two
  // ISO strings of different lengths can sort the wrong way.
  const at = Date.parse(a.created_at);
  const bt = Date.parse(b.created_at);
  // An unreadable date sorts nothing after: the pill is always order-safe.
  if (Number.isNaN(at) || Number.isNaN(bt)) return false;
  if (at !== bt) return at > bt;
  // Ids are numeric strings: "10" < "9" as text.
  return Number(a.id) > Number(b.id);
}
