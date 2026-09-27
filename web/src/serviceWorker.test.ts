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

function loadWorker(windows: FakeClient[] = []) {
  const listeners: Record<string, Listener> = {};
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, fn: Listener) => {
      listeners[type] = fn;
    },
    skipWaiting: vi.fn(),
    registration: { showNotification: vi.fn(async () => undefined) },
    clients: {
      claim: vi.fn(async () => undefined),
      matchAll: vi.fn(async () => windows),
      openWindow: vi.fn(async () => null),
    },
  };
  const context: Record<string, unknown> = { self, URL };
  runInNewContext(SOURCE, context);
  return { self, listeners, context };
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
});
