import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import LiveToast, { LIVE_TOAST_MS } from './LiveToast';
import type { LiveToastSpec } from '../../types/forumLive';

const spec = (overrides: Partial<LiveToastSpec> = {}): LiveToastSpec => ({
  id: 't1',
  message: 'Replies now appear live.',
  actions: [{ label: 'Turn off', onClick: vi.fn() }],
  ...overrides,
});

describe('LiveToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('the status region is mounted while empty', () => {
    render(<LiveToast toast={null} onDismiss={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('shows the message and its action buttons', () => {
    render(<LiveToast toast={spec()} onDismiss={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Replies now appear live.');
    expect(screen.getByRole('button', { name: 'Turn off' })).toBeInTheDocument();
  });

  it('an action calls onClick then onDismiss', () => {
    const onClick = vi.fn();
    const onDismiss = vi.fn();
    render(
      <LiveToast toast={spec({ actions: [{ label: 'Undo', onClick }] })} onDismiss={onDismiss} />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('has a Dismiss button', () => {
    const onDismiss = vi.fn();
    render(<LiveToast toast={spec()} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('auto-dismisses after LIVE_TOAST_MS', () => {
    const onDismiss = vi.fn();
    render(<LiveToast toast={spec()} onDismiss={onDismiss} />);
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS - 1));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('the timer pauses while the toast has focus or hover, and restarts on blur', () => {
    const onDismiss = vi.fn();
    render(<LiveToast toast={spec()} onDismiss={onDismiss} />);
    const button = screen.getByRole('button', { name: 'Turn off' });
    fireEvent.focus(button);
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS * 3));
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.blur(button);
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('pauses on hover', () => {
    const onDismiss = vi.fn();
    render(<LiveToast toast={spec()} onDismiss={onDismiss} />);
    fireEvent.mouseEnter(screen.getByText('Replies now appear live.'));
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS * 2));
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.mouseLeave(screen.getByText('Replies now appear live.'));
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('a new toast id restarts the timer', () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<LiveToast toast={spec()} onDismiss={onDismiss} />);
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS - 1000));
    rerender(
      <LiveToast toast={spec({ id: 't2', message: 'Live updates off' })} onDismiss={onDismiss} />
    );
    act(() => vi.advanceTimersByTime(LIVE_TOAST_MS - 1));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
