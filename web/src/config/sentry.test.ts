import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Audit 2026-11-10 (M7): the scrubber only helps if every Sentry hook that can
// carry a URL goes through it. This pins the wiring; sentryScrub.test.ts pins
// what the scrubber does.

const { init, addEventProcessor, replayIntegration } = vi.hoisted(() => ({
  init: vi.fn(),
  addEventProcessor: vi.fn(),
  replayIntegration: vi.fn(
    (options: {
      beforeAddRecordingEvent: (event: { type: number; data?: unknown }) => unknown;
    }) => ({
      name: 'Replay',
      options,
    })
  ),
}));

vi.mock('@sentry/react', () => ({
  init,
  addEventProcessor,
  replayIntegration,
  browserTracingIntegration: () => ({ name: 'BrowserTracing' }),
}));

import { initSentry } from './sentry';

const URL = 'https://houseplant-md.com/verify-email?key=SECRET';

describe('initSentry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv('PROD', true);
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@o0.ingest.sentry.io/0');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('scrubs URLs in errors, transactions, breadcrumbs and replays', () => {
    initSentry();

    const options = init.mock.calls[0][0];
    const sent = [
      options.beforeSend({ request: { url: URL } }, { originalException: new Error('x') }),
      options.beforeSendTransaction({ transaction: URL }),
      options.beforeBreadcrumb({ category: 'navigation', data: { to: URL } }),
      replayIntegration.mock.calls[0][0].beforeAddRecordingEvent({ type: 4, data: { href: URL } }),
      addEventProcessor.mock.calls[0][0]({ type: 'replay_event', urls: [URL] }),
    ];

    expect(JSON.stringify(sent)).not.toContain('SECRET');
    expect(JSON.stringify(sent)).toContain('/verify-email');
  });

  // The replay library reads the address itself for each snapshot and only
  // passes custom events to beforeAddRecordingEvent, so nothing here can
  // scrub it. A page opened with a query string or fragment is not recorded.
  it('does not record a replay of a page opened with a query string', () => {
    window.history.replaceState({}, '', '/verify-email?key=SECRET');
    try {
      initSentry();
    } finally {
      window.history.replaceState({}, '', '/');
    }

    expect(replayIntegration).not.toHaveBeenCalled();
    const names = init.mock.calls[0][0].integrations.map((i: { name: string }) => i.name);
    expect(names).toEqual(['BrowserTracing']);
  });

  it('does not record a replay of a page opened with a fragment', () => {
    window.history.replaceState({}, '', '/auth/callback#access=SECRET');
    try {
      initSentry();
    } finally {
      window.history.replaceState({}, '', '/');
    }

    expect(replayIntegration).not.toHaveBeenCalled();
  });

  it('records replays of a page opened without one', () => {
    initSentry();
    const names = init.mock.calls[0][0].integrations.map((i: { name: string }) => i.name);
    expect(names).toEqual(['BrowserTracing', 'Replay']);
  });

  it('records no session unless it hits an error', () => {
    initSentry();
    const options = init.mock.calls[0][0];
    expect(options.replaysSessionSampleRate).toBe(0);
    expect(options.replaysOnErrorSampleRate).toBe(1.0);
  });

  it('still drops events that carry no exception', () => {
    initSentry();
    expect(init.mock.calls[0][0].beforeSend({ message: 'note' }, {})).toBeNull();
  });
});
