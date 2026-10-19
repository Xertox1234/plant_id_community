import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useTopicLive } from './useTopicLive';
import { liveTopicUrl } from '../services/forumLiveSocket';
import { installFakeWebSocket, type FakeWs } from '../tests/fakeWebSocket';

vi.mock('../services/authService', () => ({ refreshAccessToken: vi.fn() }));

type Props = { topicId: number | null; enabled: boolean };

describe('useTopicLive', () => {
  let sockets: FakeWs[];

  beforeEach(() => {
    sockets = installFakeWebSocket();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const setup = (initial: Props, onEvent = vi.fn(), onOpen = vi.fn()) =>
    renderHook((props: Props) => useTopicLive({ ...props, onEvent, onOpen }), {
      initialProps: initial,
    });

  it('opens one socket when enabled', () => {
    const { result } = setup({ topicId: 12, enabled: true });
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe(liveTopicUrl(12));
    expect(result.current.status).toBe('connecting');
    act(() => sockets[0].open());
    expect(result.current.status).toBe('live');
    expect(result.current.connected).toBe(true);
  });

  it('no socket when disabled', () => {
    const { result } = setup({ topicId: 12, enabled: false });
    expect(sockets).toHaveLength(0);
    expect(result.current.status).toBe('off');
    expect(result.current.connected).toBe(false);
  });

  it('no socket without a topic id', () => {
    setup({ topicId: null, enabled: true });
    expect(sockets).toHaveLength(0);
  });

  it('disabling closes the socket', () => {
    const { result, rerender } = setup({ topicId: 12, enabled: true });
    act(() => sockets[0].open());
    rerender({ topicId: 12, enabled: false });
    expect(sockets[0].closedByClient).toBe(true);
    expect(result.current.status).toBe('off');
  });

  it('changing topicId closes the old socket and opens one for the new id', () => {
    const { rerender } = setup({ topicId: 12, enabled: true });
    rerender({ topicId: 13, enabled: true });
    expect(sockets[0].closedByClient).toBe(true);
    expect(sockets).toHaveLength(2);
    expect(sockets[1].url).toBe(liveTopicUrl(13));
  });

  it('new callback identities do not reconnect', () => {
    const { rerender } = renderHook(
      ({ cb }: { cb: () => void }) =>
        useTopicLive({ topicId: 12, enabled: true, onEvent: cb, onOpen: cb }),
      { initialProps: { cb: vi.fn() } }
    );
    rerender({ cb: vi.fn() });
    rerender({ cb: vi.fn() });
    expect(sockets).toHaveLength(1);
  });

  it('unmount closes', () => {
    const { unmount } = setup({ topicId: 12, enabled: true });
    unmount();
    expect(sockets[0].closedByClient).toBe(true);
  });

  it('delivers events and opens to the latest callbacks', () => {
    const first = vi.fn();
    const latest = vi.fn();
    const latestOpen = vi.fn();
    const { rerender } = renderHook(
      ({ onEvent, onOpen }: { onEvent: () => void; onOpen: () => void }) =>
        useTopicLive({ topicId: 12, enabled: true, onEvent, onOpen }),
      { initialProps: { onEvent: first, onOpen: vi.fn() } }
    );
    rerender({ onEvent: latest, onOpen: latestOpen });
    act(() => sockets[0].open());
    act(() => sockets[0].message({ v: 1, type: 'topic.updated', topic_id: 12 }));
    expect(first).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledWith({ type: 'topic.updated', topicId: 12 });
    expect(latestOpen).toHaveBeenCalledTimes(1);
  });
});
