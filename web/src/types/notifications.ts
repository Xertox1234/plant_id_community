/**
 * Forum notification types (todo 253 slice 1, audit C2).
 * Mirrors wagtail_forum/api/serializers.py NotificationSerializer.
 */

export interface NotificationActor {
  username: string;
  display_name: string;
  trust_level: number | null;
}

export interface NotificationTopicRef {
  id: number;
  slug: string;
  title: string;
  board_id: number;
  board_slug: string;
}

/** 'mention' added in slice 4; later slices add moderation/subscription. */
export type ForumNotificationVerb = 'reply' | 'mention';

export interface ForumNotification {
  id: number;
  verb: ForumNotificationVerb;
  actor: NotificationActor | null;
  topic: NotificationTopicRef | null;
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
