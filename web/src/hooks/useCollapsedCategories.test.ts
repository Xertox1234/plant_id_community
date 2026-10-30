import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useCollapsedCategories, GUEST_COLLAPSED_CATEGORIES_KEY } from './useCollapsedCategories';
import * as forumService from '../services/forumService';
import type { ForumMyProfile } from '../types/forum';

vi.mock('../services/forumService');
vi.mock('../utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

const guest = { isAuthenticated: false, authLoading: false, userId: null };
const member = { isAuthenticated: true, authLoading: false, userId: 1 };

function profile(collapsed: number[]): ForumMyProfile {
  return { collapsed_categories: collapsed } as ForumMyProfile;
}

describe('useCollapsedCategories (todo 673)', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('keeps a guest’s collapsed categories in localStorage across a reload', () => {
    const first = renderHook(() => useCollapsedCategories(guest));
    expect(first.result.current.isCollapsed('3')).toBe(false);

    act(() => first.result.current.toggle('3'));

    expect(first.result.current.isCollapsed('3')).toBe(true);
    expect(JSON.parse(window.localStorage.getItem(GUEST_COLLAPSED_CATEGORIES_KEY)!)).toEqual(['3']);
    first.unmount();

    // A reload: a fresh mount reads the stored state back.
    const second = renderHook(() => useCollapsedCategories(guest));
    expect(second.result.current.isCollapsed('3')).toBe(true);
    act(() => second.result.current.toggle('3'));
    expect(second.result.current.isCollapsed('3')).toBe(false);
    expect(JSON.parse(window.localStorage.getItem(GUEST_COLLAPSED_CATEGORIES_KEY)!)).toEqual([]);
    expect(forumService.saveCollapsedCategories).not.toHaveBeenCalled();
  });

  it('starts expanded when stored guest state is corrupt', () => {
    window.localStorage.setItem(GUEST_COLLAPSED_CATEGORIES_KEY, '{not json');

    const { result } = renderHook(() => useCollapsedCategories(guest));

    expect(result.current.isCollapsed('3')).toBe(false);
  });

  it('reads a signed-in member’s state from their profile and saves each toggle to it', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue(profile([4]));
    vi.mocked(forumService.saveCollapsedCategories).mockResolvedValue([4, 9]);

    const { result } = renderHook(() => useCollapsedCategories(member));
    await waitFor(() => expect(result.current.isCollapsed('4')).toBe(true));

    act(() => result.current.toggle('9'));

    expect(result.current.isCollapsed('9')).toBe(true);
    await waitFor(() => expect(forumService.saveCollapsedCategories).toHaveBeenCalledWith([4, 9]));
    // A member's state never lands in the guest store.
    expect(window.localStorage.getItem(GUEST_COLLAPSED_CATEGORIES_KEY)).toBeNull();
  });

  it('does not read the profile while auth is still being verified', () => {
    renderHook(() => useCollapsedCategories({ ...member, authLoading: true }));

    expect(forumService.fetchMyForumProfile).not.toHaveBeenCalled();
  });

  it('keeps the toggle when the save fails', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue(profile([]));
    vi.mocked(forumService.saveCollapsedCategories).mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useCollapsedCategories(member));
    await waitFor(() => expect(forumService.fetchMyForumProfile).toHaveBeenCalled());
    act(() => result.current.toggle('2'));

    await waitFor(() => expect(forumService.saveCollapsedCategories).toHaveBeenCalled());
    expect(result.current.isCollapsed('2')).toBe(true);
  });

  it('ignores a toggle until the member’s stored set has loaded, so it cannot overwrite it', async () => {
    let resolveProfile: (p: ForumMyProfile) => void = () => {};
    vi.mocked(forumService.fetchMyForumProfile).mockReturnValue(
      new Promise((resolve) => {
        resolveProfile = resolve;
      })
    );
    vi.mocked(forumService.saveCollapsedCategories).mockResolvedValue([1, 2, 3]);

    const { result } = renderHook(() => useCollapsedCategories(member));
    await waitFor(() => expect(forumService.fetchMyForumProfile).toHaveBeenCalled());
    act(() => result.current.toggle('3'));

    // Saving [3] here would replace the stored [1, 2] on the server.
    expect(forumService.saveCollapsedCategories).not.toHaveBeenCalled();
    expect(result.current.isCollapsed('3')).toBe(false);

    await act(async () => resolveProfile(profile([1, 2])));
    act(() => result.current.toggle('3'));
    await waitFor(() =>
      expect(forumService.saveCollapsedCategories).toHaveBeenCalledWith([1, 2, 3])
    );
  });

  it('ignores a toggle while auth is still being verified', () => {
    const { result } = renderHook(() => useCollapsedCategories({ ...member, authLoading: true }));

    act(() => result.current.toggle('3'));

    expect(result.current.isCollapsed('3')).toBe(false);
    expect(window.localStorage.getItem(GUEST_COLLAPSED_CATEGORIES_KEY)).toBeNull();
    expect(forumService.saveCollapsedCategories).not.toHaveBeenCalled();
  });

  it('sends saves one after another so an older set never lands last', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue(profile([]));
    let finishFirst: () => void = () => {};
    vi.mocked(forumService.saveCollapsedCategories)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finishFirst = () => resolve([1]);
        })
      )
      .mockResolvedValueOnce([1, 2]);

    const { result } = renderHook(() => useCollapsedCategories(member));
    await waitFor(() => expect(forumService.fetchMyForumProfile).toHaveBeenCalled());
    await act(async () => {});
    act(() => result.current.toggle('1'));
    act(() => result.current.toggle('2'));

    await waitFor(() => expect(forumService.saveCollapsedCategories).toHaveBeenCalledTimes(1));
    await act(async () => finishFirst());
    await waitFor(() => expect(forumService.saveCollapsedCategories).toHaveBeenCalledTimes(2));
    expect(vi.mocked(forumService.saveCollapsedCategories).mock.calls[1][0]).toEqual([1, 2]);
  });

  it('still toggles for this visit when the stored set failed to load, without saving', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockRejectedValue(new Error('500'));

    const { result } = renderHook(() => useCollapsedCategories(member));
    await waitFor(() => expect(forumService.fetchMyForumProfile).toHaveBeenCalled());
    await act(async () => {});
    act(() => result.current.toggle('3'));

    expect(result.current.isCollapsed('3')).toBe(true);
    // The stored set is unknown, so saving would overwrite it.
    expect(forumService.saveCollapsedCategories).not.toHaveBeenCalled();
  });

  it('drops a save the previous account queued once the identity changes', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue(profile([]));
    let finishFirst: () => void = () => {};
    vi.mocked(forumService.saveCollapsedCategories)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finishFirst = () => resolve([1]);
        })
      )
      .mockResolvedValue([]);

    const { result, rerender } = renderHook((viewer) => useCollapsedCategories(viewer), {
      initialProps: member,
    });
    await act(async () => {});
    act(() => result.current.toggle('1'));
    act(() => result.current.toggle('2'));
    await waitFor(() => expect(forumService.saveCollapsedCategories).toHaveBeenCalledTimes(1));

    rerender({ ...member, userId: 2 });
    await act(async () => finishFirst());
    await act(async () => {});

    // The second save ([1, 2]) belonged to account 1 and never runs as account 2.
    expect(forumService.saveCollapsedCategories).toHaveBeenCalledTimes(1);
  });
});
