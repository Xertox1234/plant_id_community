/* Browser (Web Push) notifications for forum events (todo 413).
 *
 * The server sends {title, body, icon, badge, tag, data: {url, event}}
 * (apps/users/services.py NotificationService.send_web_push_notification).
 * The payload is data, never markup: showNotification renders text only.
 */

// Take over open tabs at once: a tab this worker does not control cannot be
// navigated by it (WindowClient.navigate rejects), so a click would only focus
// it (PR #852 review).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

function text(value, fallback) {
  return typeof value === 'string' && value ? value : fallback;
}

/** The click target, always on this origin. Checked AFTER parsing: a string
 * test is not enough, since URL() reads '/\evil.com' as '//evil.com'. */
function resolveClickUrl(raw, origin) {
  const fallback = new URL('/forum', origin);
  if (typeof raw !== 'string' || !raw) return fallback;
  let url;
  try {
    url = new URL(raw, origin);
  } catch {
    return fallback;
  }
  return url.origin === fallback.origin ? url : fallback;
}

self.addEventListener('push', (event) => {
  let payload;
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }
  const data = payload.data && typeof payload.data === 'object' ? payload.data : {};
  event.waitUntil(
    self.registration.showNotification(text(payload.title, 'Houseplant MD'), {
      body: text(payload.body, ''),
      icon: text(payload.icon, '/favicon.svg'),
      badge: text(payload.badge, '/favicon.svg'),
      tag: text(payload.tag, 'houseplant-md'),
      data,
    })
  );
});

async function openClick(url) {
  const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const tab = windows.find((client) => new URL(client.url).origin === url.origin);
  if (tab) {
    try {
      // Focus first, while the click's user activation lasts; then navigate
      // the tab itself (focus() may resolve to null in some browsers).
      await tab.focus();
      return await tab.navigate(url.href);
    } catch {
      // An uncontrolled tab cannot be navigated: open the target instead.
    }
  }
  return self.clients.openWindow(url.href);
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const raw = event.notification.data && event.notification.data.url;
  event.waitUntil(openClick(resolveClickUrl(raw, self.location.origin)));
});

/** The API origins the worker may send a subscription's auth secret to (todo
 * 602, owner decision 2026-10-11). That secret is the resubscribe credential,
 * and same-origin script (an XSS) can register `/sw.js?api=<anything>`, which
 * would outlive the XSS: so the origin is pinned here, not trusted from the
 * URL. A new deployed API origin must be added to this list. */
const ALLOWED_API_ORIGINS = ['https://api.houseplant-md.com'];
const LOCAL_HOSTS = ['localhost', '127.0.0.1', '[::1]'];

/** The API origin, from the registration URL (`/sw.js?api=<origin>`): this
 * file is served as-is, outside Vite, so it cannot read VITE_API_URL. Null
 * unless it is a pinned origin, or, in dev (the worker itself on localhost),
 * a localhost origin. Never plain http anywhere else: the secret would travel
 * in cleartext. */
function apiOrigin() {
  try {
    const raw = new URL(self.location.href).searchParams.get('api');
    if (!raw) return null;
    const url = new URL(raw);
    if (ALLOWED_API_ORIGINS.includes(url.origin)) return url.origin;
    const dev =
      LOCAL_HOSTS.includes(new URL(self.location.href).hostname) &&
      LOCAL_HOSTS.includes(url.hostname) &&
      (url.protocol === 'http:' || url.protocol === 'https:');
    return dev ? url.origin : null;
  } catch {
    return null;
  }
}

/**
 * The browser replaced this subscription (Firefox, or Chrome on expiry), todo
 * 456. Tell the server, or it keeps sending to the dead endpoint and
 * notifications stop without an error. The worker has no cookie or CSRF
 * token, so it proves it holds the old subscription with that subscription's
 * own endpoint and auth secret instead. With no oldSubscription there is
 * nothing to prove it with: the Settings page reconciles on its next load.
 */
async function resubscribe(oldSubscription, newSubscription) {
  const api = apiOrigin();
  if (!oldSubscription || !api) return;
  const old = oldSubscription.toJSON();
  if (!old || !old.endpoint || !old.keys || !old.keys.auth) return;
  let fresh = newSubscription;
  if (!fresh) {
    const applicationServerKey =
      oldSubscription.options && oldSubscription.options.applicationServerKey;
    if (!applicationServerKey) return;
    fresh = await self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
  }
  const send = () =>
    fetch(`${api}/api/v1/auth/push-notifications/resubscribe/`, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        old_subscription: { endpoint: old.endpoint, auth: old.keys.auth },
        subscription: fresh.toJSON(),
      }),
    });
  // 409: other accounts took the new endpoint concurrently twice running and
  // the server rolled everything back, so one retry is safe (todo 641, owner
  // decision 2026-10-12). After that the Settings page reconciles on load.
  const response = await send();
  if (response && response.status === 409) await send();
}

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(resubscribe(event.oldSubscription, event.newSubscription).catch(() => undefined));
});
