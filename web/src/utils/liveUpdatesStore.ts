import { useCallback, useSyncExternalStore } from 'react';

/**
 * The per-browser "Live updates" setting and the two live-updates toast
 * flags (forum live replies, slice 3). Stored on this device only, never on
 * the account: the phone and the browser are set separately (owner decision
 * O8). Read through useSyncExternalStore, so no provider is needed and a
 * change in another tab (the `storage` event) reaches this one.
 */

export const LIVE_UPDATES_KEY = 'gt-live-updates';
export const LIVE_INTRO_KEY = 'gt-live-intro-shown';
export const MISSING_OUT_KEY = 'gt-live-missing-out-at';
export const MISSING_OUT_SESSION_KEY = 'gt-live-missing-out-session';
/** After the signed-out "missing out" toast shows, not again on this device for 24 h. */
export const MISSING_OUT_QUIET_MS = 24 * 60 * 60 * 1000;

function readItem(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function writeItem(storage: () => Storage, key: string, value: string): void {
  try {
    storage().setItem(key, value);
  } catch {
    /* ignore quota/denied */
  }
}

const local = () => localStorage;
const session = () => sessionStorage;

/** On unless this browser stored 'off'; unreadable storage reads as on. */
export function readLiveUpdatesEnabled(): boolean {
  return readItem(local, LIVE_UPDATES_KEY) !== 'off';
}

const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  const onStorage = (event: StorageEvent) => {
    if (event.key === LIVE_UPDATES_KEY || event.key === null) onChange();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener('storage', onStorage);
  };
}

export function useLiveUpdatesEnabled(): [boolean, (on: boolean) => void] {
  const enabled = useSyncExternalStore(subscribe, readLiveUpdatesEnabled, () => true);
  const setEnabled = useCallback((on: boolean) => {
    writeItem(local, LIVE_UPDATES_KEY, on ? 'on' : 'off');
    listeners.forEach((listener) => listener());
  }, []);
  return [enabled, setEnabled];
}

/** True exactly once per browser (the first-time "Replies now appear live." toast). */
export function takeLiveIntro(): boolean {
  if (readItem(local, LIVE_INTRO_KEY) === '1') return false;
  writeItem(local, LIVE_INTRO_KEY, '1');
  return true;
}

/** At most once per tab session, and not within 24 h of the last showing. */
export function mayShowMissingOut(now: number): boolean {
  if (readItem(session, MISSING_OUT_SESSION_KEY) === '1') return false;
  const last = Number(readItem(local, MISSING_OUT_KEY));
  return !(Number.isFinite(last) && last > 0 && now - last < MISSING_OUT_QUIET_MS);
}

export function markMissingOutShown(now: number): void {
  writeItem(session, MISSING_OUT_SESSION_KEY, '1');
  writeItem(local, MISSING_OUT_KEY, String(now));
}
