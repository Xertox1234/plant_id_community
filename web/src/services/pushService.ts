/**
 * Browser (Web Push) notifications for forum events (todo 413).
 *
 * The server holds the VAPID key pair and sends to the subscriptions stored
 * here; `public/sw.js` shows them. Cookie + CSRF auth, like every service.
 */
import { API_ORIGIN } from '@/config/api';
import { getCsrfToken } from '../utils/csrf';

const BASE = `${API_ORIGIN}/api/v1/auth/me/push-notifications`;
export const SERVICE_WORKER_URL = '/sw.js';

export type BrowserPushState =
  | 'unsupported' // this browser has no Push API
  | 'unavailable' // the server has no key pair configured
  | 'denied' // the user blocked notifications for this site
  | 'off'
  | 'on';

export function browserSupportsPush(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/** The applicationServerKey the Push API wants, from the base64url key. */
export function urlBase64ToUint8Array(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url + '='.repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

// The key from the last fetch. enableBrowserPush reads it instead of fetching
// again, because it must ask permission before any network await (below).
let cachedPublicKey: string | null = null;

async function fetchPublicKey(): Promise<string | null> {
  const response = await fetch(`${BASE}/public-key/`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Push key request failed (${response.status})`);
  const data = (await response.json()) as { enabled?: boolean; public_key?: string };
  cachedPublicKey = data.enabled && data.public_key ? data.public_key : null;
  return cachedPublicKey;
}

function sameKey(a: ArrayBuffer | null | undefined, b: Uint8Array): boolean {
  if (!a || a.byteLength !== b.byteLength) return false;
  const bytes = new Uint8Array(a);
  return bytes.every((byte, i) => byte === b[i]);
}

async function post(path: string, body: unknown): Promise<Response> {
  const csrf = await getCsrfToken();
  return fetch(`${BASE}/${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRFToken': csrf } : {}),
    },
    body: JSON.stringify(body),
  });
}

async function currentSubscription(): Promise<PushSubscription | null> {
  // No argument: the registration controlling this page (its scope), not a
  // lookup keyed on the script path.
  const registration = await navigator.serviceWorker.getRegistration();
  return registration ? registration.pushManager.getSubscription() : null;
}

export async function getBrowserPushState(): Promise<BrowserPushState> {
  if (!browserSupportsPush()) return 'unsupported';
  if (!(await fetchPublicKey())) return 'unavailable';
  if (Notification.permission === 'denied') return 'denied';
  return (await currentSubscription()) ? 'on' : 'off';
}

/** Ask permission, subscribe this browser, and register it with the server. */
export async function enableBrowserPush(): Promise<BrowserPushState> {
  if (!browserSupportsPush()) return 'unsupported';
  // Permission FIRST: Safari shows the prompt only inside the click's user
  // activation, and an awaited fetch before it can use that up (PR #852 review).
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off';
  const publicKey = cachedPublicKey ?? (await fetchPublicKey());
  if (!publicKey) return 'unavailable';
  const applicationServerKey = urlBase64ToUint8Array(publicKey);

  const registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL);
  await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription.options?.applicationServerKey, applicationServerKey)) {
    // Made with a key the server no longer signs with (a rotation): every
    // send to it would fail, so replace it.
    await subscription.unsubscribe();
    subscription = null;
  }
  subscription ??= await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey,
  });
  const response = await post('subscribe/', { subscription: subscription.toJSON() });
  if (!response.ok) {
    // The server refused it: do not leave a browser subscription it can't use.
    await subscription.unsubscribe();
    throw new Error(`Subscribe failed (${response.status})`);
  }
  return 'on';
}

/** Unsubscribe this browser and tell the server. */
export async function disableBrowserPush(): Promise<BrowserPushState> {
  const subscription = await currentSubscription();
  if (subscription) {
    const { endpoint } = subscription;
    await subscription.unsubscribe();
    // A failure here leaves a dead row the server deactivates on its next 410.
    await post('unsubscribe/', { endpoint }).catch(() => undefined);
  }
  return 'off';
}

// Logout must never wait long on this.
const RELEASE_ON_LOGOUT_TIMEOUT_MS = 3000;

/**
 * On logout, stop this browser receiving the leaving account's notifications:
 * unsubscribe it, and tell the server while the session still exists. Best
 * effort and time-bounded; it never throws, so it can never block a logout.
 */
export async function releaseBrowserPushOnLogout(): Promise<void> {
  if (!browserSupportsPush()) return;
  const release = disableBrowserPush().then(() => undefined);
  const timeout = new Promise<void>((resolve) => setTimeout(resolve, RELEASE_ON_LOGOUT_TIMEOUT_MS));
  await Promise.race([release, timeout]).catch(() => undefined);
}
