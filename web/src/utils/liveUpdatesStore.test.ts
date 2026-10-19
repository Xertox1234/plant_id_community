import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  LIVE_UPDATES_KEY,
  MISSING_OUT_KEY,
  MISSING_OUT_QUIET_MS,
  mayShowMissingOut,
  markMissingOutShown,
  readLiveUpdatesEnabled,
  takeLiveIntro,
  useLiveUpdatesEnabled,
} from './liveUpdatesStore';

describe('liveUpdatesStore', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('defaults to on when nothing is stored', () => {
    expect(readLiveUpdatesEnabled()).toBe(true);
  });

  it('defaults to on when localStorage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(readLiveUpdatesEnabled()).toBe(true);
  });

  it("stores 'off' and reads it back", () => {
    const { result } = renderHook(() => useLiveUpdatesEnabled());
    act(() => result.current[1](false));
    expect(localStorage.getItem(LIVE_UPDATES_KEY)).toBe('off');
    expect(result.current[0]).toBe(false);
    expect(readLiveUpdatesEnabled()).toBe(false);
  });

  it('a storage event from another tab updates the hook', () => {
    const { result } = renderHook(() => useLiveUpdatesEnabled());
    expect(result.current[0]).toBe(true);
    act(() => {
      localStorage.setItem(LIVE_UPDATES_KEY, 'off');
      window.dispatchEvent(new StorageEvent('storage', { key: LIVE_UPDATES_KEY, newValue: 'off' }));
    });
    expect(result.current[0]).toBe(false);
  });

  it('takeLiveIntro is true once, then false', () => {
    expect(takeLiveIntro()).toBe(true);
    expect(takeLiveIntro()).toBe(false);
  });

  it('mayShowMissingOut is false after markMissingOutShown in the same session', () => {
    const now = 1_000_000_000_000;
    expect(mayShowMissingOut(now)).toBe(true);
    markMissingOutShown(now);
    expect(mayShowMissingOut(now + MISSING_OUT_QUIET_MS * 2)).toBe(false);
  });

  it('mayShowMissingOut is false within 24 h of the stored time even in a new session', () => {
    const now = 1_000_000_000_000;
    localStorage.setItem(MISSING_OUT_KEY, String(now - MISSING_OUT_QUIET_MS + 1));
    expect(mayShowMissingOut(now)).toBe(false);
  });

  it('mayShowMissingOut is true again after 24 h in a new session', () => {
    const now = 1_000_000_000_000;
    markMissingOutShown(now - MISSING_OUT_QUIET_MS);
    sessionStorage.clear();
    expect(mayShowMissingOut(now)).toBe(true);
  });

  describe('when the browser blocks storage', () => {
    beforeEach(() => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('denied');
      });
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('denied');
      });
    });

    it('turning it off still reads back off for this page', () => {
      const { result } = renderHook(() => useLiveUpdatesEnabled());
      act(() => result.current[1](false));
      expect(result.current[0]).toBe(false);
      act(() => result.current[1](true));
      expect(result.current[0]).toBe(true);
    });

    it('the missing-out toast is still at most once', () => {
      const now = 2_000_000_000_000;
      expect(mayShowMissingOut(now)).toBe(true);
      markMissingOutShown(now);
      expect(mayShowMissingOut(now + 30_000)).toBe(false);
    });
  });
});
