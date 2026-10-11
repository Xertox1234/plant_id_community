import { test, expect, type BrowserContext, type CDPSession, type Page } from '@playwright/test';

/**
 * public/sw.js in a real browser (todo 456 item 4). The unit test
 * (src/serviceWorker.test.ts) runs the worker in a node vm with a fake `self`;
 * this registers the real file and drives it through the browser.
 *
 * What a browser automation can and cannot do here:
 * - A PUSH is delivered for real in Chromium, through the DevTools protocol
 *   (ServiceWorker.deliverPushMessage): a trusted push event, no push service.
 * - A notification CLICK cannot be: no automation API clicks an OS
 *   notification, and a script-made NotificationEvent is untrusted, so
 *   `waitUntil` throws and the browser grants no user activation (focus and
 *   openWindow then reject). The click test therefore dispatches the event in
 *   the real worker, records where openWindow was asked to go, and checks the
 *   real notification was closed.
 * - WebKit has no DevTools protocol and Playwright's WebKit has no Web Push,
 *   so there it checks only that the real worker parses, installs and takes
 *   control of the page.
 *
 * Needs only the Vite dev server (it serves public/ as-is); no login.
 */

const PAYLOAD = {
  title: 'Ada replied to Ferns',
  body: 'Looks like root rot.',
  tag: 'forum-reply_added-7',
  data: { url: '/forum/1-general/2-ferns#post-7', event: 'reply_added' },
};

async function registerWorker(page: Page) {
  await page.goto('/');
  await page.evaluate(async () => {
    await navigator.serviceWorker.register('/sw.js?api=http://localhost:8000');
    await navigator.serviceWorker.ready;
  });
  // clients.claim() in the activate handler hands this page to the worker.
  await expect
    .poll(() => page.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null))
    .toContain('/sw.js');
}

async function registrationId(cdp: CDPSession, origin: string): Promise<string> {
  return new Promise((resolve) => {
    cdp.on('ServiceWorker.workerRegistrationUpdated', ({ registrations }) => {
      const mine = registrations.find(
        (r: { scopeURL: string; isDeleted: boolean }) =>
          r.scopeURL.startsWith(origin) && !r.isDeleted
      );
      if (mine) resolve(mine.registrationId);
    });
    void cdp.send('ServiceWorker.enable');
  });
}

async function notifications(page: Page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    return (await registration.getNotifications()).map((n) => ({
      title: n.title,
      body: n.body,
      tag: n.tag,
      data: n.data,
    }));
  });
}

test.describe('service worker in a real browser (todo 456)', () => {
  test('installs and takes control of the page', async ({ page }) => {
    await registerWorker(page);
  });
});

test.describe('push and click in Chromium (todo 456)', () => {
  test.skip(
    ({ browserName }) => browserName !== 'chromium',
    'push is delivered through the Chromium DevTools protocol'
  );
  test('a delivered push shows the notification, and a click opens the post', async ({
    playwright,
    baseURL,
  }) => {
    const origin = new URL(baseURL ?? 'http://localhost:5174').origin;
    // The full Chromium build, not the project's default headless shell: the
    // shell reports notification permission "denied" whatever is granted, so
    // showNotification always throws there. (`test.use({ channel })` cannot
    // be scoped to one group, hence a browser of its own.)
    test.info().setTimeout(60_000);
    const browser = await playwright.chromium.launch({ channel: 'chromium' });
    const context = await browser.newContext({ baseURL: origin });
    try {
      await context.grantPermissions(['notifications'], { origin });
      const page = await context.newPage();
      await registerWorker(page);
      await deliverAndClick(page, context, origin);
    } finally {
      await browser.close();
    }
  });
});

async function deliverAndClick(page: Page, context: BrowserContext, origin: string) {
  const cdp = await context.newCDPSession(page);
  const id = await registrationId(cdp, origin);
  await cdp.send('ServiceWorker.deliverPushMessage', {
    origin,
    registrationId: id,
    data: JSON.stringify(PAYLOAD),
  });

  await expect
    .poll(() => notifications(page))
    .toEqual([{ title: PAYLOAD.title, body: PAYLOAD.body, tag: PAYLOAD.tag, data: PAYLOAD.data }]);

  // The click, inside the real worker (see the header for why untrusted).
  const [worker] = context.serviceWorkers();
  const opened = await worker.evaluate(async () => {
    // Worker globals: the web tsconfig has the DOM lib, not WebWorker.
    const sw = self as unknown as {
      registration: ServiceWorkerRegistration;
      clients: { openWindow: (url: string | URL) => Promise<unknown> };
      dispatchEvent: (event: Event) => boolean;
      NotificationEvent: new (type: string, init: { notification: Notification }) => Event;
    };
    const [notification] = await sw.registration.getNotifications();
    let target: string | null = null;
    // No user activation for a synthetic click: record the request instead.
    sw.clients.openWindow = async (url: string | URL) => {
      target = String(url);
      return null;
    };
    const event = new sw.NotificationEvent('notificationclick', { notification });
    let pending: Promise<unknown> = Promise.resolve();
    Object.defineProperty(event, 'waitUntil', {
      value: (p: Promise<unknown>) => {
        pending = p;
      },
    });
    sw.dispatchEvent(event);
    await pending.catch(() => undefined);
    return target;
  });

  expect(opened).toBe(`${origin}${PAYLOAD.data.url}`);
  await expect.poll(() => notifications(page)).toEqual([]);
}
