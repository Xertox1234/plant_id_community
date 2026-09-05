/**
 * Forum notification types (todo 253 slice 1, audit C2).
 * Mirrors wagtail_forum/api/serializers.py NotificationSerializer.
 */

export interface NotificationActor {
  username: string;
  display_name: string;
  // Unified author object (todo 257 H26): the actor now carries an avatar
  // (absolute URL or null), same shape as every topic/post author.
  avatar: string | null;
  trust_level: number | null;
}

export interface NotificationTopicRef {
  id: number;
  slug: string;
  title: string;
  board_id: number;
  board_slug: string;
}

/**
 * 'mention' added in slice 4; 'quote' in todo 342 (someone quoted your post);
 * later slices add moderation/subscription.
 */
export type ForumNotificationVerb = 'reply' | 'mention' | 'quote';

export interface ForumNotification {
  id: number;
  verb: ForumNotificationVerb;
  actor: NotificationActor | null;
  topic: NotificationTopicRef | null;
  /** The post this notification is about, for deep links; null for post-less verbs.
   * For `quote` this is the QUOTING post (the deep-link target), like a reply. */
  post_id: number | null;
  /** For `quote`: the post of yours that was quoted (todo 342); null otherwise. */
  quoted_post_id: number | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationListResponse {
  results: ForumNotification[];
  next: string | null;
  previous: string | null;
}

export interface UnreadCountResponse {
  count: number;
}

export interface MarkReadResponse {
  updated: number;
}
