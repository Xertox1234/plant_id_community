import { useEffect, useState } from 'react';
import Eyebrow from '../ui/Eyebrow';
import { logger } from '../../utils/logger';
import {
  disableBrowserPush,
  enableBrowserPush,
  getBrowserPushState,
  type BrowserPushState,
} from '../../services/pushService';

const EXPLANATION: Record<BrowserPushState, string> = {
  unsupported: "This browser can't show notifications from Houseplant MD.",
  unavailable: 'Browser notifications are not available yet.',
  denied:
    "Notifications are blocked for this site in your browser's settings. Allow them there to turn this on.",
  off: 'Get forum replies, mentions and answers on this device, even when the tab is closed.',
  on: 'This browser shows your forum notifications. The Push column above picks which ones.',
};

/**
 * Browser (Web Push) notifications for this device (todo 413). Which events
 * push is the existing Notifications table's "Push" column; this section
 * only turns the channel on or off for THIS browser.
 */
export default function BrowserNotificationsSection() {
  const [state, setState] = useState<BrowserPushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBrowserPushState()
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch((err: unknown) => {
        logger.warn('[PUSH] Could not read browser push state', { err });
        if (!cancelled) setState('unavailable');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = async () => {
    if (state !== 'on' && state !== 'off') return;
    setBusy(true);
    setError(null);
    try {
      setState(state === 'on' ? await disableBrowserPush() : await enableBrowserPush());
    } catch (err: unknown) {
      logger.warn('[PUSH] Browser push toggle failed', { err });
      setError("That didn't work. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="p-screen" aria-label="Browser notifications">
      <Eyebrow>Browser notifications</Eyebrow>
      {state === null ? (
        <p className="mt-2 text-sm text-ink-3">Loading…</p>
      ) : (
        <>
          <p className="mt-1 text-sm text-ink-3">{EXPLANATION[state]}</p>
          {(state === 'on' || state === 'off') && (
            <button
              type="button"
              onClick={toggle}
              disabled={busy}
              aria-pressed={state === 'on'}
              className="mt-2 min-h-11 rounded-pill px-4 py-1 text-sm text-primary hover:bg-primary/10 disabled:opacity-60"
            >
              {state === 'on' ? 'Turn off on this browser' : 'Turn on for this browser'}
            </button>
          )}
        </>
      )}
      {/* Always mounted, only the text swaps: a live region created along
          with its content announces nothing (docs/rules/react.md). */}
      <p aria-live="polite" className={error ? 'mt-1 text-sm text-error' : 'sr-only'}>
        {error}
      </p>
    </section>
  );
}
