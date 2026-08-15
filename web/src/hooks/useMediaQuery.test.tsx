import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { useMediaQuery } from './useMediaQuery';

function Probe({ query }: { query: string }) {
  return <span data-testid="matches">{String(useMediaQuery(query))}</span>;
}

type ChangeListener = (event: { matches: boolean }) => void;

// Controllable matchMedia stub (the global setup.ts polyfill always reports
// false): flip `state.matches` and fire the captured listeners to simulate
// the viewport crossing the breakpoint.
function installMatchMedia(initialMatches: boolean) {
  const state = {
    matches: initialMatches,
    listeners: [] as ChangeListener[],
  };
  window.matchMedia = ((query: string) => ({
    get matches() {
      return state.matches;
    },
    media: query,
    onchange: null,
    addEventListener: (_type: string, listener: ChangeListener) => {
      state.listeners.push(listener);
    },
    removeEventListener: (_type: string, listener: ChangeListener) => {
      state.listeners = state.listeners.filter((l) => l !== listener);
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
  return state;
}

const originalMatchMedia = window.matchMedia;

describe('useMediaQuery', () => {
  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('reads the query synchronously on first render', () => {
    installMatchMedia(true);
    render(<Probe query="(min-width: 1280px)" />);
    expect(screen.getByTestId('matches')).toHaveTextContent('true');
  });

  it('updates when the media query fires a change event', () => {
    const state = installMatchMedia(false);
    render(<Probe query="(min-width: 1280px)" />);
    expect(screen.getByTestId('matches')).toHaveTextContent('false');

    act(() => {
      state.matches = true;
      state.listeners.forEach((listener) => listener({ matches: true }));
    });
    expect(screen.getByTestId('matches')).toHaveTextContent('true');
  });

  it('unsubscribes on unmount', () => {
    const state = installMatchMedia(false);
    const { unmount } = render(<Probe query="(min-width: 1280px)" />);
    expect(state.listeners).toHaveLength(1);
    unmount();
    expect(state.listeners).toHaveLength(0);
  });
});
