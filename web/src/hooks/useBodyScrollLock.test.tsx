import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { useBodyScrollLock } from './useBodyScrollLock';

function Locker({ active }: { active: boolean }) {
  useBodyScrollLock(active);
  return null;
}

describe('useBodyScrollLock', () => {
  beforeEach(() => {
    document.body.style.overflow = '';
  });

  it('locks the body while active and restores when it stops being active', () => {
    const { rerender } = render(<Locker active={true} />);
    expect(document.body.style.overflow).toBe('hidden');

    rerender(<Locker active={false} />);
    expect(document.body.style.overflow).toBe('');
  });

  it('two simultaneous lockers: releasing ONE leaves the body locked; releasing BOTH restores it', () => {
    // Two independent trees, each with its own <Locker> — the module-level
    // counter is what has to make these compose, not React tree structure
    // (the drawer and the command palette are siblings under AppShell, not
    // nested, so this mirrors the real shape).
    const first = render(<Locker active={true} />);
    const second = render(<Locker active={true} />);
    expect(document.body.style.overflow).toBe('hidden');

    // Release the second locker only — the first is still active, so the
    // page must stay locked. This is exactly the composition bug the
    // shared, ref-counted hook fixes: two independent `document.body.style
    // .overflow = 'hidden'`/restore effects would instead unlock here.
    second.rerender(<Locker active={false} />);
    expect(document.body.style.overflow).toBe('hidden');

    // Release the last remaining locker — now it restores.
    first.rerender(<Locker active={false} />);
    expect(document.body.style.overflow).toBe('');
  });

  it('releases on unmount even if the caller never flips `active` back to false', () => {
    const { unmount } = render(<Locker active={true} />);
    expect(document.body.style.overflow).toBe('hidden');

    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('two simultaneous lockers: unmounting ONE leaves the body locked; unmounting BOTH restores it', () => {
    const first = render(<Locker active={true} />);
    const second = render(<Locker active={true} />);
    expect(document.body.style.overflow).toBe('hidden');

    first.unmount();
    expect(document.body.style.overflow).toBe('hidden');

    second.unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('preserves a pre-existing body overflow value instead of hard-coding an empty restore', () => {
    document.body.style.overflow = 'scroll';
    const { unmount } = render(<Locker active={true} />);
    expect(document.body.style.overflow).toBe('hidden');

    unmount();
    expect(document.body.style.overflow).toBe('scroll');
  });
});
