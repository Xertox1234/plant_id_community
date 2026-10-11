import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../utils/csrf', () => ({ getCsrfToken: vi.fn(async () => 'csrf-token') }));

import {
  disableBrowserPush,
  enableBrowserPush,
  getBrowserPushState,
  releaseBrowserPushOnLogout,
  urlBase64ToUint8Array,
} from './pushService';

// Todo 413: browser push. jsdom has no Push API, so the browser surface is faked.

// The VAPID PUBLIC key (not a secret); detect-secrets flags its entropy.
const KEY =
  'BLrbiiidfpiAWj4ZHexQggpVCJue5b5tIjZ9KsgobEuNVz4wwNxPKsLmqHB1ANm31--xeXyulD-js65NgCr17G4'; // pragma: allowlist secret

function fakeBrowser({
  permission = 'default',
  existing = null as unknown,
  grant = 'granted' as NotificationPermission,
  log = [] as string[],
} = {}) {
  const subscription = {
    endpoint: 'https://fcm.googleapis.com/fcm/send/abc',
    toJSON: () => ({
      endpoint: 'https://fcm.googleapis.com/fcm/send/abc',
      keys: { p256dh: 'p', auth: 'a' },
    }),
    unsubscribe: vi.fn(async () => true),
  };
  const pushManager = {
    getSubscription: vi.fn(async () => existing),
    subscribe: vi.fn(async (_options?: PushSubscriptionOptionsInit) => subscription),
  };
  const registration = { pushManager };
  Object.defineProperty(window, 'PushManager', {
    value: function PushManager() {},
    configurable: true,
  });
  Object.defineProperty(window, 'Notification', {
    value: {
      permission,
      requestPermission: vi.fn(async () => {
        log.push('permission');
        return grant;
      }),
    },
    configurable: true,
    writable: true,
  });
  Object.defineProperty(navigator, 'serviceWorker', {
    value: {
      register: vi.fn(async () => registration),
      ready: Promise.resolve(registration),
      getRegistration: vi.fn(async () => (existing ? registration : undefined)),
    },
    configurable: true,
  });
  return { subscription, pushManager };
}

function mockFetch(
  publicKey: { enabled: boolean; public_key: string },
  subscribeStatus = 201,
  log: string[] = []
) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      log.push(`fetch ${url.split('/push-notifications/')[1]}`);
      if (url.endsWith('/public-key/'))
        return new Response(JSON.stringify(publicKey), { status: 200 });
      return new Response('{}', { status: url.endsWith('/subscribe/') ? subscribeStatus : 200 });
    })
  );
  return calls;
}

describe('pushService', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window, 'PushManager'); // cleanup of a faked global
  });

  it('decodes the base64url VAPID key to the 65-byte P-256 point', () => {
    const bytes = urlBase64ToUint8Array(KEY);
    expect(bytes).toHaveLength(65);
    expect(bytes[0]).toBe(0x04); // uncompressed point marker
  });

  it('reports unsupported without the Push API', async () => {
    Reflect.deleteProperty(window, 'PushManager'); // a browser without push
    expect(await getBrowserPushState()).toBe('unsupported');
  });

  it('reports unavailable when the server has no key pair', async () => {
    fakeBrowser();
    mockFetch({ enabled: false, public_key: '' });
    expect(await getBrowserPushState()).toBe('unavailable');
  });

  it('turning on subscribes with the server key and registers the subscription', async () => {
    const { pushManager } = fakeBrowser();
    const calls = mockFetch({ enabled: true, public_key: KEY });

    expect(await enableBrowserPush()).toBe('on');

    const options = pushManager.subscribe.mock.calls[0][0] as PushSubscriptionOptionsInit;
    expect(options.userVisibleOnly).toBe(true);
    expect(options.applicationServerKey).toEqual(urlBase64ToUint8Array(KEY));
    const subscribe = calls.find((c) => c.url.endsWith('/subscribe/'));
    expect(JSON.parse(String(subscribe?.init?.body))).toEqual({
      subscription: {
        endpoint: 'https://fcm.googleapis.com/fcm/send/abc',
        keys: { p256dh: 'p', auth: 'a' },
      },
    });
    expect((subscribe?.init?.headers as Record<string, string>)['X-CSRFToken']).toBe('csrf-token');
  });

  it('a subscription the server refuses is removed from the browser', async () => {
    const { subscription } = fakeBrowser();
    mockFetch({ enabled: true, public_key: KEY }, 400);

    await expect(enableBrowserPush()).rejects.toThrow('Subscribe failed (400)');
    expect(subscription.unsubscribe).toHaveBeenCalled();
  });

  it('turning off unsubscribes and tells the server which endpoint', async () => {
    const existing = {
      endpoint: 'https://fcm.googleapis.com/fcm/send/old',
      unsubscribe: vi.fn(async () => true),
    };
    fakeBrowser({ existing });
    const calls = mockFetch({ enabled: true, public_key: KEY });

    expect(await disableBrowserPush()).toBe('off');
    expect(existing.unsubscribe).toHaveBeenCalled();
    const unsubscribe = calls.find((c) => c.url.endsWith('/unsubscribe/'));
    expect(JSON.parse(String(unsubscribe?.init?.body))).toEqual({ endpoint: existing.endpoint });
  });

  // --- PR #852 round-1 repairs ----------------------------------------------

  function existingSubscription(key: Uint8Array) {
    return {
      endpoint: 'https://fcm.googleapis.com/fcm/send/old',
      options: { applicationServerKey: key.buffer.slice(0) },
      toJSON: () => ({
        endpoint: 'https://fcm.googleapis.com/fcm/send/old',
        keys: { p256dh: 'op', auth: 'oa' },
      }),
      unsubscribe: vi.fn(async () => true),
    };
  }

  it('re-registers an existing subscription made with the current key', async () => {
    const existing = existingSubscription(urlBase64ToUint8Array(KEY));
    const { pushManager } = fakeBrowser({ existing });
    const calls = mockFetch({ enabled: true, public_key: KEY });

    expect(await enableBrowserPush()).toBe('on');

    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(existing.unsubscribe).not.toHaveBeenCalled();
    const subscribe = calls.find((c) => c.url.endsWith('/subscribe/'));
    expect(JSON.parse(String(subscribe?.init?.body)).subscription.endpoint).toBe(existing.endpoint);
  });

  it('replaces an existing subscription made with a rotated-out key', async () => {
    const oldKey = urlBase64ToUint8Array(KEY);
    oldKey[10] ^= 0xff;
    const existing = existingSubscription(oldKey);
    const { pushManager } = fakeBrowser({ existing });
    const calls = mockFetch({ enabled: true, public_key: KEY });

    expect(await enableBrowserPush()).toBe('on');

    expect(existing.unsubscribe).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledOnce();
    const subscribe = calls.find((c) => c.url.endsWith('/subscribe/'));
    expect(JSON.parse(String(subscribe?.init?.body)).subscription.endpoint).toBe(
      'https://fcm.googleapis.com/fcm/send/abc'
    );
  });

  it.each([
    ['denied', 'denied'],
    ['default', 'off'],
  ] as const)('a %s permission answer subscribes nothing', async (grant, state) => {
    const { pushManager } = fakeBrowser({ grant });
    const calls = mockFetch({ enabled: true, public_key: KEY });

    expect(await enableBrowserPush()).toBe(state);

    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(calls.some((c) => c.url.endsWith('/subscribe/'))).toBe(false);
  });

  it('asks permission before any network await (Safari user activation)', async () => {
    const log: string[] = [];
    fakeBrowser({ log });
    mockFetch({ enabled: true, public_key: KEY }, 201, log);

    await getBrowserPushState(); // the mount-time read caches the key
    log.length = 0;
    expect(await enableBrowserPush()).toBe('on');

    expect(log[0]).toBe('permission');
    expect(log).not.toContain('fetch public-key/');
  });

  it('logout unsubscribes this browser and tells the server', async () => {
    const existing = existingSubscription(urlBase64ToUint8Array(KEY));
    fakeBrowser({ existing });
    const calls = mockFetch({ enabled: true, public_key: KEY });

    await releaseBrowserPushOnLogout();

    expect(existing.unsubscribe).toHaveBeenCalled();
    const unsubscribe = calls.find((c) => c.url.endsWith('/unsubscribe/'));
    expect(JSON.parse(String(unsubscribe?.init?.body))).toEqual({ endpoint: existing.endpoint });
  });

  it('logout is never blocked by a hung or failing release', async () => {
    const existing = existingSubscription(urlBase64ToUint8Array(KEY));
    existing.unsubscribe = vi.fn(() => new Promise<boolean>(() => undefined));
    fakeBrowser({ existing });
    mockFetch({ enabled: true, public_key: KEY });
    vi.useFakeTimers();
    try {
      const done = releaseBrowserPushOnLogout();
      await vi.advanceTimersByTimeAsync(3000);
      await expect(done).resolves.toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });
});

// --- Todo 456: reconcile the "on" state with the server ------------------------

describe('pushService reconcile (todo 456)', () => {
  const ENDPOINT = 'https://fcm.googleapis.com/fcm/send/old';

  async function sha256(text: string) {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
  }

  function existing() {
    return {
      endpoint: ENDPOINT,
      options: { applicationServerKey: urlBase64ToUint8Array(KEY).buffer.slice(0) },
      toJSON: () => ({ endpoint: ENDPOINT, keys: { p256dh: 'op', auth: 'oa' } }),
      unsubscribe: vi.fn(async () => true),
    };
  }

  /** The server's list: `rows` hashes, or a status/body to fail with. */
  function serverList(rows: string[] | null, status = 200) {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith('/public-key/'))
          return new Response(JSON.stringify({ enabled: true, public_key: KEY }), { status: 200 });
        if (url.endsWith('/push-notifications/')) {
          const body =
            rows === null ? {} : { subscriptions: rows.map((h) => ({ endpoint_sha256: h })) };
          return new Response(JSON.stringify(body), { status });
        }
        return new Response('{}', { status: 201 });
      })
    );
    return calls;
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window, 'PushManager');
  });

  it('is on when the server holds this browser subscription', async () => {
    fakeBrowser({ existing: existing() });
    serverList([await sha256('https://fcm.googleapis.com/fcm/send/other'), await sha256(ENDPOINT)]);

    expect(await getBrowserPushState()).toBe('on');
  });

  it('moves an already-subscribed browser onto the worker URL with the API origin', async () => {
    fakeBrowser({ existing: existing() });
    serverList([await sha256(ENDPOINT)]);

    await getBrowserPushState();

    const register = navigator.serviceWorker.register as unknown as ReturnType<typeof vi.fn>;
    expect(String(register.mock.calls[0][0])).toMatch(/^\/sw\.js\?api=/);
  });

  it('is off when the server deactivated it, though the browser still has it', async () => {
    fakeBrowser({ existing: existing() });
    serverList([await sha256('https://fcm.googleapis.com/fcm/send/other')]);

    expect(await getBrowserPushState()).toBe('off');
  });

  it.each([
    ['an error status', [] as string[], 500],
    ['an unexpected body', null, 200],
  ])('keeps the browser answer when the server gives %s', async (_name, rows, status) => {
    fakeBrowser({ existing: existing() });
    serverList(rows, status);

    expect(await getBrowserPushState()).toBe('on');
  });

  it('turning on again replaces a subscription the server dropped', async () => {
    const old = existing();
    const { pushManager } = fakeBrowser({ existing: old });
    const calls = serverList([]);

    expect(await enableBrowserPush()).toBe('on');

    expect(old.unsubscribe).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledOnce();
    const subscribe = calls.find((c) => c.url.endsWith('/subscribe/'));
    expect(JSON.parse(String(subscribe?.init?.body)).subscription.endpoint).toBe(
      'https://fcm.googleapis.com/fcm/send/abc'
    );
  });

  it('registers the worker with the API origin it re-subscribes to', async () => {
    fakeBrowser();
    serverList([]);

    await enableBrowserPush();

    const register = navigator.serviceWorker.register as unknown as ReturnType<typeof vi.fn>;
    const url = new URL(String(register.mock.calls[0][0]), 'https://houseplant-md.com');
    expect(url.pathname).toBe('/sw.js');
    expect(url.searchParams.get('api')).toMatch(/^https?:\/\//);
  });

  it('a key rotation tells the server to drop the old row', async () => {
    const old = existing();
    const rotated = urlBase64ToUint8Array(KEY);
    rotated[10] ^= 0xff;
    old.options.applicationServerKey = rotated.buffer.slice(0);
    fakeBrowser({ existing: old });
    const calls = serverList([]);

    expect(await enableBrowserPush()).toBe('on');

    const unsubscribe = calls.find((c) => c.url.endsWith('/unsubscribe/'));
    expect(JSON.parse(String(unsubscribe?.init?.body))).toEqual({ endpoint: ENDPOINT });
  });
});
