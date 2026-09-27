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

async function fetchPublicKey(): Promise<string | null> {
  const response = await fetch(`${BASE}/public-key/`, { credentials: 'include' });
  if (!response.ok) throw new Error(`Push key request failed (${response.status})`);
  const data = (await response.json()) as { enabled?: boolean; public_key?: string };
  return data.enabled && data.public_key ? data.public_key : null;
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
  const registration = await navigator.serviceWorker.getRegistration(SERVICE_WORKER_URL);
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
  const publicKey = await fetchPublicKey();
  if (!publicKey) return 'unavailable';
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off';

  const registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL);
  await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }));
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
