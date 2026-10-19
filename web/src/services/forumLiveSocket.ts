/**
 * The live topic socket client (forum live replies, slice 3).
 */
import {
  LIVE_POST_EVENT_TYPES,
  LIVE_TOPIC_EVENT_TYPES,
  type LiveEvent,
  type LivePostEventType,
  type LiveTopicEventType,
} from '../types/forumLive';

function isPostType(type: string): type is LivePostEventType {
  return (LIVE_POST_EVENT_TYPES as readonly string[]).includes(type);
}

function isTopicType(type: string): type is LiveTopicEventType {
  return (LIVE_TOPIC_EVENT_TYPES as readonly string[]).includes(type);
}

function isId(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

/**
 * One server frame → an event, `'pong'`, or null for anything else (bad JSON,
 * a binary frame, another protocol version, an unknown type, a missing id).
 * Unknown input is ignored, never fetched on.
 */
export function parseLiveEvent(data: unknown): LiveEvent | 'pong' | null {
  if (typeof data !== 'string') return null;
  let raw: unknown;
  try {
    raw = JSON.parse(data);
  } catch {
    return null;
  }
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null;
  const msg = raw as Record<string, unknown>;
  if (msg.v !== 1 || typeof msg.type !== 'string') return null;
  if (msg.type === 'pong') return 'pong';
  if (!isId(msg.topic_id)) return null;
  const { type, topic_id: topicId, post_id: postId } = msg;
  if (isPostType(type)) {
    return isId(postId) ? { type, topicId, postId: String(postId) } : null;
  }
  if (isTopicType(type)) return { type, topicId };
  return null;
}
