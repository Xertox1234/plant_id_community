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
// The worker's own re-subscribe (pushsubscriptionchange, todo 456) needs the
// API origin, and public/sw.js is served as-is, outside Vite: it reads it
// from its registration URL.
const SERVICE_WORKER_REGISTRATION_URL = `${SERVICE_WORKER_URL}?api=${encodeURIComponent(API_ORIGIN)}`;

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

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Whether the server holds this browser's subscription as active (todo 456).
 * After a 404/410 from the push service, or another account subscribing
 * this browser, the server has deactivated the row while the browser still
 * has the subscription. Null when it can't tell (a failed or odd response):
 * the caller then keeps the browser's own answer, never a guess.
 */
async function serverHasSubscription(subscription: PushSubscription): Promise<boolean | null> {
  try {
    const response = await fetch(`${BASE}/`, { credentials: 'include' });
    if (!response.ok) return null;
    const data = (await response.json()) as {
      subscriptions?: { endpoint_sha256?: unknown }[];
    };
    if (!Array.isArray(data.subscriptions)) return null;
    const mine = await sha256Hex(subscription.endpoint);
    return data.subscriptions.some((row) => row.endpoint_sha256 === mine);
  } catch {
    return null;
  }
}

export async function getBrowserPushState(): Promise<BrowserPushState> {
  if (!browserSupportsPush()) return 'unsupported';
  if (!(await fetchPublicKey())) return 'unavailable';
  if (Notification.permission === 'denied') return 'denied';
  const subscription = await currentSubscription();
  if (!subscription) return 'off';
  // A worker registered before todo 456 has no `?api=` on its URL, so its
  // re-subscribe cannot run: re-register it (a no-op once the URL matches).
  await navigator.serviceWorker.register(SERVICE_WORKER_REGISTRATION_URL).catch(() => undefined);
  // "On" only if the server still sends to it (todo 456 item 2).
  return (await serverHasSubscription(subscription)) === false ? 'off' : 'on';
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

  const registration = await navigator.serviceWorker.register(SERVICE_WORKER_REGISTRATION_URL);
  await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription.options?.applicationServerKey, applicationServerKey)) {
    // Made with a key the server no longer signs with (a rotation): every
    // send to it would fail, so replace it, and tell the server to drop the
    // old row now rather than on its next 404/410 (PR #852 round-2 note).
    const { endpoint } = subscription;
    await subscription.unsubscribe();
    await post('unsubscribe/', { endpoint }).catch(() => undefined);
    subscription = null;
  } else if (subscription && (await serverHasSubscription(subscription)) === false) {
    // The server deactivated it (the push service said it is gone, or another
    // account took this browser over): start a fresh one rather than
    // re-register an endpoint that may be dead (todo 456 item 2).
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
