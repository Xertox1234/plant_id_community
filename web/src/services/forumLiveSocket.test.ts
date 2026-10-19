import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import {
  BACKOFF_CAP_MS,
  LIVE_CLOSE,
  PING_INTERVAL_MS,
  PONG_TIMEOUT_MS,
  liveTopicUrl,
  openTopicLive,
  parseLiveEvent,
  toWsUrl,
} from './forumLiveSocket';
import { refreshAccessToken } from './authService';
import { installFakeWebSocket, type FakeWs } from '../tests/fakeWebSocket';
import type { LiveEvent, LiveStatus } from '../types/forumLive';

vi.mock('./authService', () => ({ refreshAccessToken: vi.fn() }));

const frame = (obj: unknown) => JSON.stringify(obj);

describe('parseLiveEvent', () => {
  it.each(['post.created', 'post.updated', 'post.removed'] as const)('parses %s', (type) => {
    expect(parseLiveEvent(frame({ v: 1, type, topic_id: 12, post_id: 7 }))).toEqual({
      type,
      topicId: 12,
      postId: '7',
    });
  });

  it.each(['topic.updated', 'topic.removed'] as const)('parses %s', (type) => {
    expect(parseLiveEvent(frame({ v: 1, type, topic_id: 12 }))).toEqual({ type, topicId: 12 });
  });

  it('maps a pong', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'pong' }))).toBe('pong');
  });

  it('null for v !== 1', () => {
    expect(
      parseLiveEvent(frame({ v: 2, type: 'post.created', topic_id: 1, post_id: 2 }))
    ).toBeNull();
  });

  it('null for an unknown type', () => {
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.reacted', topic_id: 1, post_id: 2 }))
    ).toBeNull();
  });

  it('null for bad JSON', () => {
    expect(parseLiveEvent('{not json')).toBeNull();
  });

  it('null for non-string data (a Blob/ArrayBuffer)', () => {
    expect(parseLiveEvent(new ArrayBuffer(4))).toBeNull();
    expect(parseLiveEvent(new Blob(['x']))).toBeNull();
  });

  it('null for a post event with no integer post_id', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1 }))).toBeNull();
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1, post_id: '2' }))
    ).toBeNull();
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.created', topic_id: 1, post_id: 2.5 }))
    ).toBeNull();
  });

  it('null for a non-integer topic_id', () => {
    expect(parseLiveEvent(frame({ v: 1, type: 'topic.updated', topic_id: '12' }))).toBeNull();
    expect(parseLiveEvent(frame({ v: 1, type: 'topic.updated' }))).toBeNull();
  });

  it('null for a JSON value that is not an object', () => {
    expect(parseLiveEvent('null')).toBeNull();
    expect(parseLiveEvent('[1]')).toBeNull();
  });

  it('ignores extra fields', () => {
    expect(
      parseLiveEvent(frame({ v: 1, type: 'post.removed', topic_id: 3, post_id: 4, body: 'x' }))
    ).toEqual({ type: 'post.removed', topicId: 3, postId: '4' });
  });
});

describe('toWsUrl', () => {
  it('maps http to ws and https to wss, with no /api/v1', () => {
    expect(toWsUrl('http://localhost:8000', 12)).toBe('ws://localhost:8000/ws/forum/topics/12/');
    expect(toWsUrl('https://api.houseplant-md.com', 12)).toBe(
      'wss://api.houseplant-md.com/ws/forum/topics/12/'
    );
  });

  it('liveTopicUrl uses the configured API origin', () => {
    expect(liveTopicUrl(5)).toMatch(/^wss?:\/\/[^/]+\/ws\/forum\/topics\/5\/$/);
  });
});

describe('openTopicLive', () => {
  let sockets: FakeWs[];
  let onEvent: Mock<(event: LiveEvent) => void>;
  let onOpen: Mock<() => void>;
  let onStatus: Mock<(status: LiveStatus) => void>;

  const start = (topicId = 12) => openTopicLive(topicId, { onEvent, onOpen, onStatus });
  const lastStatus = () => onStatus.mock.calls.at(-1)?.[0];

  beforeEach(() => {
    vi.useFakeTimers();
    sockets = installFakeWebSocket();
    onEvent = vi.fn<(event: LiveEvent) => void>();
    onOpen = vi.fn<() => void>();
    onStatus = vi.fn<(status: LiveStatus) => void>();
    vi.mocked(refreshAccessToken).mockResolvedValue(true);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('reports connecting, then live on open, and calls onOpen', () => {
    start();
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe(liveTopicUrl(12));
    expect(lastStatus()).toBe('connecting');
    sockets[0].open();
    expect(lastStatus()).toBe('live');
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('delivers parsed events and drops null ones', () => {
    start();
    sockets[0].open();
    sockets[0].message({ v: 1, type: 'post.created', topic_id: 12, post_id: 3 });
    sockets[0].message('{bad');
    sockets[0].message({ v: 1, type: 'pong' });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: 'post.created', topicId: 12, postId: '3' });
  });

  it.each([
    [LIVE_CLOSE.disabled, 'stopped'],
    [LIVE_CLOSE.limited, 'stopped'],
    [LIVE_CLOSE.notFound, 'gone'],
  ])('does not reconnect after %i', async (code, status) => {
    start();
    sockets[0].open();
    sockets[0].serverClose(code);
    await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS * 4);
    expect(sockets).toHaveLength(1);
    expect(lastStatus()).toBe(status);
  });

  it('does not reconnect after a 4503 that arrives before any open', async () => {
    start();
    sockets[0].serverClose(LIVE_CLOSE.disabled);
    await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS * 4);
    expect(sockets).toHaveLength(1);
    expect(lastStatus()).toBe('stopped');
  });

  it('4401 refreshes once and reconnects once; a second 4401 stops', async () => {
    start();
    sockets[0].serverClose(LIVE_CLOSE.unauthenticated);
    await vi.advanceTimersByTimeAsync(0);
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(2);
    sockets[1].serverClose(LIVE_CLOSE.unauthenticated);
    await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS * 4);
    expect(sockets).toHaveLength(2);
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
    expect(lastStatus()).toBe('stopped');
  });

  it('1006 reconnects with backoff, resetting after a successful open', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    start();
    sockets[0].serverClose(1006);
    await vi.advanceTimersByTimeAsync(749);
    expect(sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(sockets).toHaveLength(2);
    sockets[1].serverClose(1006);
    await vi.advanceTimersByTimeAsync(1499);
    expect(sockets).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(sockets).toHaveLength(3);
    sockets[2].open();
    sockets[2].serverClose(1006);
    await vi.advanceTimersByTimeAsync(750);
    expect(sockets).toHaveLength(4);
    expect(lastStatus()).toBe('connecting');
  });

  it('backoff is capped', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(1);
    start();
    for (let i = 0; i < 10; i += 1) {
      sockets[sockets.length - 1].serverClose(1006);
      await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS);
    }
    const before = sockets.length;
    sockets[sockets.length - 1].serverClose(1006);
    await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS);
    expect(sockets.length).toBe(before + 1);
  });

  it('pings every 25 s and reconnects when no frame arrives within 10 s', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    start();
    sockets[0].open();
    await vi.advanceTimersByTimeAsync(PING_INTERVAL_MS);
    expect(sockets[0].sent).toEqual([JSON.stringify({ type: 'ping' })]);
    await vi.advanceTimersByTimeAsync(PONG_TIMEOUT_MS);
    expect(sockets[0].closedByClient).toBe(true);
    expect(lastStatus()).toBe('connecting');
    await vi.advanceTimersByTimeAsync(750);
    expect(sockets).toHaveLength(2);
  });

  it('any frame clears the pong timer', async () => {
    start();
    sockets[0].open();
    await vi.advanceTimersByTimeAsync(PING_INTERVAL_MS);
    sockets[0].message({ v: 1, type: 'pong' });
    await vi.advanceTimersByTimeAsync(PONG_TIMEOUT_MS);
    expect(sockets[0].closedByClient).toBe(false);
    expect(sockets).toHaveLength(1);
    expect(lastStatus()).toBe('live');
  });

  it('close() stops everything', async () => {
    const live = start();
    sockets[0].open();
    live.close();
    expect(sockets[0].closedByClient).toBe(true);
    expect(lastStatus()).toBe('off');
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(BACKOFF_CAP_MS * 4);
    expect(sockets).toHaveLength(1);
  });

  it('close() during the 4401 refresh never reconnects', async () => {
    let resolveRefresh: (ok: boolean) => void = () => {};
    vi.mocked(refreshAccessToken).mockReturnValue(
      new Promise((resolve) => {
        resolveRefresh = resolve;
      })
    );
    const live = start();
    sockets[0].serverClose(LIVE_CLOSE.unauthenticated);
    live.close();
    resolveRefresh(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(sockets).toHaveLength(1);
    expect(lastStatus()).toBe('off');
  });
});
