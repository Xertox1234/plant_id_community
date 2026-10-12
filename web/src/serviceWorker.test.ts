/**
 * public/sw.js is plain JS outside the Vite module graph, so it is run here in
 * a node vm context with a fake `self` (todo 413, PR #852 review).
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { runInNewContext } from 'node:vm';
import { describe, expect, it, vi } from 'vitest';

const ORIGIN = 'https://houseplant-md.com';
const SOURCE = readFileSync(join(__dirname, '..', 'public', 'sw.js'), 'utf8');

type Listener = (event: Record<string, unknown>) => void;

interface FakeClient {
  url: string;
  focus: ReturnType<typeof vi.fn>;
  navigate: ReturnType<typeof vi.fn>;
}

const API = 'https://api.houseplant-md.com';

function loadWorker(windows: FakeClient[] = [], href = `${ORIGIN}/sw.js?api=${API}`) {
  const listeners: Record<string, Listener> = {};
  const fetch = vi.fn(async () => new Response('{}', { status: 200 }));
  const self = {
    location: { origin: ORIGIN, href },
    addEventListener: (type: string, fn: Listener) => {
      listeners[type] = fn;
    },
    skipWaiting: vi.fn(),
    registration: {
      showNotification: vi.fn(async () => undefined),
      pushManager: { subscribe: vi.fn(async () => fakeSubscription('fresh')) },
    },
    clients: {
      claim: vi.fn(async () => undefined),
      matchAll: vi.fn(async () => windows),
      openWindow: vi.fn(async () => null),
    },
  };
  const context: Record<string, unknown> = { self, URL, fetch };
  runInNewContext(SOURCE, context);
  return { self, listeners, context, fetch };
}

function fakeSubscription(id: string, applicationServerKey: ArrayBuffer | null = null) {
  const endpoint = `https://fcm.googleapis.com/fcm/send/${id}`;
  return {
    endpoint,
    options: { applicationServerKey },
    toJSON: () => ({ endpoint, keys: { p256dh: `p-${id}`, auth: `a-${id}` } }),
  };
}

async function subscriptionChange(
  listeners: Record<string, Listener>,
  oldSubscription: unknown,
  newSubscription: unknown
) {
  let pending: Promise<unknown> = Promise.resolve();
  listeners.pushsubscriptionchange({
    oldSubscription,
    newSubscription,
    waitUntil: (p: Promise<unknown>) => {
      pending = p;
    },
  });
  await pending;
}

async function click(listeners: Record<string, Listener>, url: unknown) {
  let pending: Promise<unknown> = Promise.resolve();
  listeners.notificationclick({
    notification: { close: vi.fn(), data: { url } },
    waitUntil: (p: Promise<unknown>) => {
      pending = p;
    },
  });
  await pending;
}

describe('service worker (public/sw.js)', () => {
  it.each([
    '/\\evil.com',
    '/\\/evil.com',
    '/\\\\evil.com',
    '//evil.com',
    'https://evil.com/forum',
    'javascript:alert(1)',
    42,
    '',
  ])('a click on %j never leaves this origin', async (raw) => {
    const { self, listeners } = loadWorker();

    await click(listeners, raw);

    expect(self.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/forum`);
  });

  it('a same-origin path opens at the post', async () => {
    const { self, listeners } = loadWorker();

    await click(listeners, '/forum/1-general/2-ferns#post-3');

    expect(self.clients.openWindow).toHaveBeenCalledWith(
      `${ORIGIN}/forum/1-general/2-ferns#post-3`
    );
  });

  it('an open tab is focused, then navigated', async () => {
    const tab: FakeClient = {
      url: `${ORIGIN}/settings`,
      focus: vi.fn(),
      navigate: vi.fn(async () => tab),
    };
    tab.focus.mockResolvedValue(tab);
    const { self, listeners } = loadWorker([tab]);

    await click(listeners, '/forum/1-general/2-ferns');

    expect(tab.navigate).toHaveBeenCalledWith(`${ORIGIN}/forum/1-general/2-ferns`);
    expect(self.clients.openWindow).not.toHaveBeenCalled();
  });

  it('a tab the worker cannot navigate falls back to a new window', async () => {
    const tab: FakeClient = {
      url: `${ORIGIN}/settings`,
      focus: vi.fn(),
      navigate: vi.fn(async () => {
        throw new TypeError('not controlled');
      }),
    };
    tab.focus.mockResolvedValue(tab);
    const { self, listeners } = loadWorker([tab]);

    await click(listeners, '/forum/1-general/2-ferns');

    expect(self.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/forum/1-general/2-ferns`);
  });

  it('takes control of open tabs on install and activate', async () => {
    const { self, listeners } = loadWorker();
    let activated: Promise<unknown> = Promise.resolve();

    listeners.install({});
    listeners.activate({
      waitUntil: (p: Promise<unknown>) => {
        activated = p;
      },
    });
    await activated;

    expect(self.skipWaiting).toHaveBeenCalled();
    expect(self.clients.claim).toHaveBeenCalled();
  });

  it('non-string icon, badge and tag fall back to the defaults', async () => {
    const { self, listeners } = loadWorker();

    listeners.push({
      data: { json: () => ({ title: 't', icon: { x: 1 }, badge: 7, tag: ['a'] }) },
      waitUntil: () => undefined,
    });

    const options = self.registration.showNotification.mock.calls[0] as unknown as [
      string,
      Record<string, unknown>,
    ];
    expect(options[1]).toMatchObject({
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      tag: 'houseplant-md',
    });
  });

  // --- Todo 456: pushsubscriptionchange --------------------------------------

  function postedBody(fetch: ReturnType<typeof vi.fn>) {
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    return { url, init, body: JSON.parse(String(init.body)) };
  }

  it('a replaced subscription is swapped on the server with the old secret', async () => {
    const { listeners, fetch } = loadWorker();

    await subscriptionChange(listeners, fakeSubscription('old'), fakeSubscription('new'));

    const { url, init, body } = postedBody(fetch);
    expect(url).toBe(`${API}/api/v1/auth/push-notifications/resubscribe/`);
    // No cookies: the old subscription is the credential, not a session.
    expect(init).toMatchObject({ method: 'POST', credentials: 'omit' });
    expect(body).toEqual({
      old_subscription: { endpoint: 'https://fcm.googleapis.com/fcm/send/old', auth: 'a-old' },
      subscription: {
        endpoint: 'https://fcm.googleapis.com/fcm/send/new',
        keys: { p256dh: 'p-new', auth: 'a-new' },
      },
    });
  });

  it.each([
    ['a 409 is retried once and then succeeds', [409, 200], 2],
    ['a second 409 gives up', [409, 409, 200], 2],
    ['a 200 is sent once', [200], 1],
    ['a 500 is not retried', [500, 200], 1],
  ])('resubscribe: %s (todo 641)', async (_name, statuses, sent) => {
    const { listeners, fetch } = loadWorker();
    fetch.mockImplementation(async () => new Response('{}', { status: statuses.shift() ?? 200 }));

    await subscriptionChange(listeners, fakeSubscription('old'), fakeSubscription('new'));

    expect(fetch).toHaveBeenCalledTimes(sent);
    const bodies = fetch.mock.calls.map((call) =>
      String((call as unknown as [string, RequestInit])[1].body)
    );
    expect(new Set(bodies).size).toBe(1);
  });

  it('with no new subscription it subscribes again with the old key', async () => {
    const key = new Uint8Array([4, 1, 2]).buffer;
    const { self, listeners, fetch } = loadWorker();

    await subscriptionChange(listeners, fakeSubscription('old', key), null);

    expect(self.registration.pushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: key,
    });
    expect(postedBody(fetch).body.subscription.endpoint).toBe(
      'https://fcm.googleapis.com/fcm/send/fresh'
    );
  });

  it.each([
    ['no old subscription', null, `${ORIGIN}/sw.js?api=${API}`],
    ['no API origin on the registration URL', fakeSubscription('old'), `${ORIGIN}/sw.js`],
    ['a non-http API origin', fakeSubscription('old'), `${ORIGIN}/sw.js?api=javascript:x`],
    // Todo 602 items 10 and 8: an XSS-registered `?api=` must not carry the
    // secret off-site, and plain http is refused outside local dev.
    ['an unpinned API origin', fakeSubscription('old'), `${ORIGIN}/sw.js?api=https://evil.example`],
    [
      'a look-alike of the pinned origin',
      fakeSubscription('old'),
      `${ORIGIN}/sw.js?api=https://api.houseplant-md.com.evil.example`,
    ],
    [
      'the pinned origin over http',
      fakeSubscription('old'),
      `${ORIGIN}/sw.js?api=http://api.houseplant-md.com`,
    ],
    [
      'a localhost API from a deployed worker',
      fakeSubscription('old'),
      `${ORIGIN}/sw.js?api=http://localhost:8000`,
    ],
    [
      'a non-local http API from a local worker',
      fakeSubscription('old'),
      'http://localhost:5174/sw.js?api=http://10.0.0.5:8000',
    ],
  ])('does nothing with %s (the page reconciles on load)', async (_name, old, href) => {
    const { listeners, fetch } = loadWorker([], href);

    await subscriptionChange(listeners, old, fakeSubscription('new'));

    expect(fetch).not.toHaveBeenCalled();
  });

  it('in local dev it sends to a localhost API over http', async () => {
    const { listeners, fetch } = loadWorker(
      [],
      'http://localhost:5174/sw.js?api=http://localhost:8000'
    );

    await subscriptionChange(listeners, fakeSubscription('old'), fakeSubscription('new'));

    expect(postedBody(fetch).url).toBe(
      'http://localhost:8000/api/v1/auth/push-notifications/resubscribe/'
    );
  });

  it('does nothing when the old key is unknown and there is no new subscription', async () => {
    const { self, listeners, fetch } = loadWorker();

    await subscriptionChange(listeners, fakeSubscription('old', null), null);

    expect(self.registration.pushManager.subscribe).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
});
