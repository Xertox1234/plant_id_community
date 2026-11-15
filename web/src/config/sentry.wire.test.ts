import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as Sentry from '@sentry/react';

import { initSentry } from './sentry';

// sentry.test.ts mocks @sentry/react and proves which hooks initSentry passes.
// It cannot prove the SDK still CALLS them: Sentry 11 stopped calling
// beforeSendTransaction by default (span streaming) while that test stayed
// green. This file runs the real SDK and reads what it puts on the wire.

const TOKEN_URL = 'https://houseplant-md.com/verify-email?key=SECRET';

function bodyText(body: unknown): string {
  if (typeof body === 'string') return body;
  if (body instanceof Uint8Array) return new TextDecoder().decode(body);
  if (body instanceof ArrayBuffer) return new TextDecoder().decode(new Uint8Array(body));
  return String(body);
}

describe('what the real Sentry SDK sends', () => {
  let sent: string[];

  beforeEach(() => {
    sent = [];
    vi.stubEnv('PROD', true);
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@o0.ingest.sentry.io/0');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: unknown, init?: { body?: unknown }) => {
        sent.push(bodyText(init?.body));
        return new Response('{}', { status: 200 });
      })
    );
    // tracesSampleRate is 0.1; make this trace one of the sampled ones.
    vi.spyOn(Math, 'random').mockReturnValue(0);
  });

  afterEach(async () => {
    await Sentry.getClient()?.close(0);
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('sends a traced page with its query string removed', async () => {
    initSentry();

    Sentry.startSpan({ name: `GET ${TOKEN_URL}`, op: 'navigation', forceTransaction: true }, () => {
      Sentry.startSpan(
        {
          name: `GET ${TOKEN_URL}`,
          op: 'http.client',
          attributes: { 'http.url': TOKEN_URL, 'url.full': TOKEN_URL, 'http.query': '?key=SECRET' },
        },
        () => undefined
      );
    });
    await Sentry.flush(2000);

    const wire = sent.join('\n');
    // Canary: the trace really was sent, so the next line is not vacuous.
    expect(wire).toContain('/verify-email');
    expect(wire).not.toContain('SECRET');
  });
});
