import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../utils/csrf', () => ({ getCsrfToken: vi.fn(async () => 'csrf-token') }));

import {
  disableBrowserPush,
  enableBrowserPush,
  getBrowserPushState,
  urlBase64ToUint8Array,
} from './pushService';

// Todo 413: browser push. jsdom has no Push API, so the browser surface is faked.

// The VAPID PUBLIC key (not a secret); detect-secrets flags its entropy.
const KEY =
  'BLrbiiidfpiAWj4ZHexQggpVCJue5b5tIjZ9KsgobEuNVz4wwNxPKsLmqHB1ANm31--xeXyulD-js65NgCr17G4'; // pragma: allowlist secret

function fakeBrowser({ permission = 'default', existing = null as unknown } = {}) {
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
    subscribe: vi.fn(async () => subscription),
  };
  const registration = { pushManager };
  Object.defineProperty(window, 'PushManager', {
    value: function PushManager() {},
    configurable: true,
  });
  Object.defineProperty(window, 'Notification', {
    value: { permission, requestPermission: vi.fn(async () => 'granted') },
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

function mockFetch(publicKey: { enabled: boolean; public_key: string }, subscribeStatus = 201) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
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
    // @ts-expect-error test cleanup of a faked global
    delete window.PushManager;
  });

  it('decodes the base64url VAPID key to the 65-byte P-256 point', () => {
    const bytes = urlBase64ToUint8Array(KEY);
    expect(bytes).toHaveLength(65);
    expect(bytes[0]).toBe(0x04); // uncompressed point marker
  });

  it('reports unsupported without the Push API', async () => {
    // @ts-expect-error simulate a browser without push
    delete window.PushManager;
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
});
