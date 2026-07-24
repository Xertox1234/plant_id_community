import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AnnouncerProvider, useAnnounce } from './AnnouncerContext';

/** Test harness: exposes announce() to the test via a button click. */
function Harness() {
  const announce = useAnnounce();
  return (
    <>
      <button onClick={() => announce('Reply posted', 'polite')}>polite</button>
      <button onClick={() => announce('Failed to post reply', 'assertive')}>assertive</button>
    </>
  );
}

const politeRegion = () => document.querySelector('[data-announcer="polite"]');
const assertiveRegion = () => document.querySelector('[data-announcer="assertive"]');

describe('AnnouncerContext', () => {
  it('mounts both live regions persistently, empty, before any announcement', () => {
    render(
      <AnnouncerProvider>
        <span>child</span>
      </AnnouncerProvider>
    );

    // The regions exist in the DOM from first render — the whole point of the
    // pattern (MDN: a live region must pre-exist for a content change to fire).
    expect(politeRegion()).toBeInTheDocument();
    expect(assertiveRegion()).toBeInTheDocument();
    expect(politeRegion()).toHaveAttribute('aria-live', 'polite');
    expect(assertiveRegion()).toHaveAttribute('aria-live', 'assertive');
    // Empty to start — announcing swaps text in, it is not conditionally mounted.
    expect(politeRegion()).toHaveTextContent('');
    expect(assertiveRegion()).toHaveTextContent('');
  });

  it('announces a polite message by swapping the persistent region text content', () => {
    render(
      <AnnouncerProvider>
        <Harness />
      </AnnouncerProvider>
    );

    // Same element node before and after — content swap, not a remount.
    const nodeBefore = politeRegion();
    act(() => {
      screen.getByText('polite').click();
    });
    expect(politeRegion()).toBe(nodeBefore);
    expect(nodeBefore).toHaveTextContent('Reply posted');
    // The assertive region stays untouched.
    expect(assertiveRegion()).toHaveTextContent('');
  });

  it('routes assertive messages to the assertive region only', () => {
    render(
      <AnnouncerProvider>
        <Harness />
      </AnnouncerProvider>
    );

    act(() => {
      screen.getByText('assertive').click();
    });
    expect(assertiveRegion()).toHaveTextContent('Failed to post reply');
    expect(politeRegion()).toHaveTextContent('');
  });

  it('throws when useAnnounce is used outside a provider', () => {
    function Orphan() {
      useAnnounce();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow(/AnnouncerProvider/);
  });
});
