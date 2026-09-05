import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useIdentitySwap } from './useIdentitySwap';

describe('useIdentitySwap', () => {
  it('fires only on a change between two real accounts', () => {
    const onSwap = vi.fn();
    const { rerender } = renderHook(({ id }) => useIdentitySwap(id, onSwap), {
      initialProps: { id: null as number | null },
    });
    rerender({ id: 1 }); // first real identity after mount: a reload, not a swap
    expect(onSwap).not.toHaveBeenCalled();
    rerender({ id: null }); // session expired
    rerender({ id: 1 }); // same account back in
    expect(onSwap).not.toHaveBeenCalled();
    rerender({ id: 2 }); // another account in this tab
    expect(onSwap).toHaveBeenCalledTimes(1);
    rerender({ id: 2 });
    expect(onSwap).toHaveBeenCalledTimes(1);
  });

  it('uses the latest callback without re-subscribing', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(({ id, cb }) => useIdentitySwap(id, cb), {
      initialProps: { id: 1 as number | null, cb: first },
    });
    rerender({ id: 1, cb: second });
    rerender({ id: 2, cb: second });
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
