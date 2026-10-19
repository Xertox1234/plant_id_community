/**
 * The live topic socket client (forum live replies, slice 3). Framework-free:
 * connect, close-code rules, backoff, heartbeat. `useTopicLive` binds it to
 * React.
 *
 * Close codes (the server accepts, then closes, so the code reaches us):
 *
 * | Code | Meaning | Client |
 * |---|---|---|
 * | 4503 | flag off (every socket until the flag flips) | stop for this visit |
 * | 4429 | socket cap | stop for this visit |
 * | 4404 | topic not visible, or removed | stop, report `gone` |
 * | 4401 | no valid user | refresh the session once, reconnect once, then stop |
 * | other (1006 …) | dropped | reconnect with backoff + jitter |
 *
 * A stopped socket never retries: retrying a 4503 would be the reconnect
 * storm the spec forbids. The page's 30 s check covers every stop.
 */
import { API_ORIGIN } from '../config/api';
import { refreshAccessToken } from './authService';
import {
  LIVE_POST_EVENT_TYPES,
  LIVE_TOPIC_EVENT_TYPES,
  type LiveEvent,
  type LiveStatus,
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

export const LIVE_CLOSE = {
  disabled: 4503,
  unauthenticated: 4401,
  notFound: 4404,
  limited: 4429,
} as const;
export const BACKOFF_BASE_MS = 1000;
export const BACKOFF_CAP_MS = 30_000;
/** A browser cannot see protocol pings, so a dead link is found by our own. */
export const PING_INTERVAL_MS = 25_000;
export const PONG_TIMEOUT_MS = 10_000;

/** `http(s)://host` → `ws(s)://host/ws/forum/topics/<id>/` (no /api/v1). */
export function toWsUrl(origin: string, topicId: number): string {
  return `${origin.replace(/^http/, 'ws')}/ws/forum/topics/${topicId}/`;
}

export function liveTopicUrl(topicId: number): string {
  return toWsUrl(API_ORIGIN, topicId);
}

export interface TopicLiveHandlers {
  onEvent: (event: LiveEvent) => void;
  onOpen: () => void;
  onStatus: (status: LiveStatus) => void;
}

export function openTopicLive(topicId: number, handlers: TopicLiveHandlers): { close(): void } {
  let ws: WebSocket | null = null;
  let attempt = 0;
  let retriedAuth = false;
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let pongTimer: ReturnType<typeof setTimeout> | null = null;

  const clearHeartbeat = () => {
    if (pingTimer) clearInterval(pingTimer);
    if (pongTimer) clearTimeout(pongTimer);
    pingTimer = null;
    pongTimer = null;
  };

  const detach = () => {
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onclose = null;
    ws.onerror = null;
    ws.close();
    ws = null;
  };

  const stop = (status: LiveStatus) => {
    closed = true;
    clearHeartbeat();
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
    handlers.onStatus(status);
  };

  const scheduleRetry = () => {
    const base = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** attempt);
    attempt += 1;
    handlers.onStatus('connecting');
    retryTimer = setTimeout(
      () => {
        retryTimer = null;
        connect();
      },
      base / 2 + Math.random() * (base / 2)
    );
  };

  const onClosed = (code: number) => {
    clearHeartbeat();
    ws = null;
    if (closed) return;
    if (code === LIVE_CLOSE.disabled || code === LIVE_CLOSE.limited) return stop('stopped');
    if (code === LIVE_CLOSE.notFound) return stop('gone');
    if (code === LIVE_CLOSE.unauthenticated) {
      if (retriedAuth) return stop('stopped');
      retriedAuth = true;
      handlers.onStatus('connecting');
      // A socket opened just before the 10-minute cookie refresh can carry a
      // stale access token: refresh once, then try once more either way.
      void refreshAccessToken().finally(() => connect());
      return;
    }
    scheduleRetry();
  };

  function connect() {
    if (closed) return;
    handlers.onStatus('connecting');
    const socket = new WebSocket(liveTopicUrl(topicId));
    ws = socket;
    socket.onopen = () => {
      attempt = 0;
      handlers.onStatus('live');
      handlers.onOpen();
      pingTimer = setInterval(() => {
        socket.send(JSON.stringify({ type: 'ping' }));
        if (pongTimer) return;
        pongTimer = setTimeout(() => {
          // No frame since the ping: the link is dead. Drop it and retry.
          pongTimer = null;
          detach();
          onClosed(1006);
        }, PONG_TIMEOUT_MS);
      }, PING_INTERVAL_MS);
    };
    socket.onmessage = (event: MessageEvent) => {
      if (pongTimer) clearTimeout(pongTimer);
      pongTimer = null;
      const parsed = parseLiveEvent(event.data);
      if (parsed && parsed !== 'pong') handlers.onEvent(parsed);
    };
    socket.onclose = (event: CloseEvent) => onClosed(event.code);
  }

  connect();
  return {
    close() {
      if (closed && !ws) {
        handlers.onStatus('off');
        return;
      }
      stop('off');
      detach();
    },
  };
}
