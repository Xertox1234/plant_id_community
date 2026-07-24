/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useState, ReactNode } from 'react';

/**
 * Screen-reader politeness. `polite` waits for the reader to finish (status
 * updates, success); `assertive` interrupts (errors).
 */
export type Announce = (message: string, politeness?: 'polite' | 'assertive') => void;

export interface AnnouncerContextValue {
  announce: Announce;
}

/**
 * AnnouncerContext
 *
 * A single pair of persistent `aria-live` regions mounted once at the app root.
 * Components call `announce(text)` to swap the region's *text content* — MDN is
 * explicit that a live region must already exist in the DOM before its content
 * changes; the common conditional-mount-with-content pattern (`{error && <p
 * role="alert">…</p>}`) is generally NOT announced (audit 2026-07-11 M26).
 */
export const AnnouncerContext = createContext<AnnouncerContextValue | null>(null);

/**
 * useAnnounce
 *
 * Returns the `announce(message, politeness?)` function. Announcing swaps the
 * persistent region's text so assistive tech reads it out.
 *
 * @throws if used outside an AnnouncerProvider
 */
export function useAnnounce(): Announce {
  const context = useContext(AnnouncerContext);
  if (context === null) {
    throw new Error('useAnnounce must be used within an AnnouncerProvider');
  }
  return context.announce;
}

export interface AnnouncerProviderProps {
  children: ReactNode;
}

/**
 * AnnouncerProvider
 *
 * Renders two visually-hidden, always-present live regions and swaps their text
 * on `announce()`. Content-swap (not conditional mount) is what makes the
 * announcement fire. Duplicate consecutive messages rely on the reader's own
 * re-read; the forum flows never announce the same string twice in a row.
 */
export function AnnouncerProvider({ children }: AnnouncerProviderProps) {
  const [politeMessage, setPoliteMessage] = useState('');
  const [assertiveMessage, setAssertiveMessage] = useState('');

  const announce = useCallback<Announce>((message, politeness = 'polite') => {
    if (!message) return;
    if (politeness === 'assertive') {
      setAssertiveMessage(message);
    } else {
      setPoliteMessage(message);
    }
  }, []);

  const value = useMemo<AnnouncerContextValue>(() => ({ announce }), [announce]);

  return (
    <AnnouncerContext value={value}>
      {children}
      {/* Persistent live regions — always in the DOM; only the text swaps.
          Bare `aria-live` (not role="status"/"alert") is the live-region
          mechanism and avoids colliding with the many role="status" spinners
          across the app in role-based test queries. */}
      <div className="sr-only" aria-live="polite" aria-atomic="true" data-announcer="polite">
        {politeMessage}
      </div>
      <div className="sr-only" aria-live="assertive" aria-atomic="true" data-announcer="assertive">
        {assertiveMessage}
      </div>
    </AnnouncerContext>
  );
}
