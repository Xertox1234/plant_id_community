/* Browser (Web Push) notifications for forum events (todo 413).
 *
 * The server sends {title, body, icon, badge, tag, data: {url, event}}
 * (apps/users/services.py NotificationService.send_web_push_notification).
 * The payload is data, never markup: showNotification renders text only.
 */
self.addEventListener('push', (event) => {
  let payload;
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }
  const title =
    typeof payload.title === 'string' && payload.title ? payload.title : 'Houseplant MD';
  const data = payload.data && typeof payload.data === 'object' ? payload.data : {};
  event.waitUntil(
    self.registration.showNotification(title, {
      body: typeof payload.body === 'string' ? payload.body : '',
      icon: payload.icon || '/favicon.svg',
      badge: payload.badge || '/favicon.svg',
      tag: payload.tag || 'houseplant-md',
      data,
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  // Same-origin paths only: a crafted payload cannot send the click elsewhere.
  const raw = event.notification.data && event.notification.data.url;
  const url = new URL(
    typeof raw === 'string' && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/forum',
    self.location.origin
  );
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (new URL(client.url).origin === url.origin && 'focus' in client) {
          client.navigate(url.href);
          return client.focus();
        }
      }
      return self.clients.openWindow(url.href);
    })
  );
});
