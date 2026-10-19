/**
 * Live forum events (forum live replies, slice 3). The server broadcasts ids
 * only; the client refetches through REST, which applies visibility and the
 * per-viewer fields. Wire format: `{"v":1,"type":T,"topic_id":int,"post_id":int}`.
 */

export const LIVE_POST_EVENT_TYPES = ['post.created', 'post.updated', 'post.removed'] as const;
export const LIVE_TOPIC_EVENT_TYPES = ['topic.updated', 'topic.removed'] as const;

export type LivePostEventType = (typeof LIVE_POST_EVENT_TYPES)[number];
export type LiveTopicEventType = (typeof LIVE_TOPIC_EVENT_TYPES)[number];

/** `postId` is a string because the page's `Post.id` is. */
export type LiveEvent =
  | { type: LivePostEventType; topicId: number; postId: string }
  | { type: LiveTopicEventType; topicId: number };

/**
 * - `off`: not running (disabled, unmounted, or closed by the page);
 * - `connecting` / `live`: opening, or open;
 * - `stopped`: refused for this visit (flag off, socket cap, auth after one
 *   refresh) — the page keeps its 30 s check;
 * - `gone`: the topic is no longer visible (4404).
 */
export type LiveStatus = 'off' | 'connecting' | 'live' | 'stopped' | 'gone';

export interface LiveToastSpec {
  id: string;
  message: string;
  actions: { label: string; onClick: () => void }[];
}
