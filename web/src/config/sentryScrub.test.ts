import { describe, it, expect } from 'vitest';
import {
  scrubUrlText,
  scrubEvent,
  scrubBreadcrumb,
  scrubRecordingEvent,
  type ScrubbableEvent,
} from './sentryScrub';

// Audit 2026-11-10 (M7): /delete-account/confirm?token=, /verify-email?key= and
// /unsubscribe?token= carry single-use credentials in the address. Sentry
// records page and request URLs, so those reached anyone with Sentry access.

const CONFIRM = 'https://houseplant-md.com/delete-account/confirm?token=SECRET.abc';

describe('scrubUrlText', () => {
  it('drops the query string and the fragment', () => {
    expect(scrubUrlText(CONFIRM)).toBe('https://houseplant-md.com/delete-account/confirm');
    expect(scrubUrlText('/verify-email?key=SECRET#top')).toBe('/verify-email');
    expect(scrubUrlText('https://x.test/a#access=SECRET')).toBe('https://x.test/a');
  });

  it('scrubs a URL inside a longer string', () => {
    expect(scrubUrlText(`GET ${CONFIRM}`)).toBe(
      'GET https://houseplant-md.com/delete-account/confirm'
    );
  });

  it('leaves text without a URL alone', () => {
    expect(scrubUrlText('What happened? Nothing #1')).toBe('What happened? Nothing #1');
    expect(scrubUrlText('/forum/topics/12')).toBe('/forum/topics/12');
  });
});

describe('scrubEvent', () => {
  it('scrubs the request, the transaction name, breadcrumbs and spans', () => {
    const event: ScrubbableEvent = {
      transaction: '/delete-account/confirm?token=SECRET.abc',
      request: { url: CONFIRM, query_string: 'token=SECRET.abc', headers: { Referer: CONFIRM } },
      breadcrumbs: [{ category: 'navigation', data: { from: '/', to: CONFIRM } }],
      spans: [{ description: `GET ${CONFIRM}`, data: { 'http.query': '?token=SECRET.abc' } }],
      contexts: { trace: { data: { 'url.full': CONFIRM } } },
    };

    const scrubbed = scrubEvent(event);

    expect(JSON.stringify(scrubbed)).not.toContain('SECRET');
    expect(scrubbed.request?.url).toBe('https://houseplant-md.com/delete-account/confirm');
  });

  it('scrubs the URL list of a replay event', () => {
    const scrubbed = scrubEvent({ type: 'replay_event', urls: [CONFIRM, '/'] });
    expect(scrubbed.urls).toEqual(['https://houseplant-md.com/delete-account/confirm', '/']);
  });

  it('scrubs a URL quoted in an error message, extra data or a tag', () => {
    const scrubbed = scrubEvent({
      exception: { values: [{ type: 'TypeError', value: `Failed to fetch ${CONFIRM}` }] },
      extra: { page: CONFIRM },
      tags: { url: CONFIRM },
    });
    expect(JSON.stringify(scrubbed)).not.toContain('SECRET');
    expect(JSON.stringify(scrubbed)).toContain('Failed to fetch https://houseplant-md.com/');
  });

  it('keeps the exception so the error is still readable', () => {
    const exception = { values: [{ type: 'TypeError', value: 'x is undefined? #2' }] };
    expect(scrubEvent({ exception }).exception).toEqual(exception);
  });
});

describe('scrubBreadcrumb', () => {
  it('scrubs fetch and navigation URLs', () => {
    const crumb = scrubBreadcrumb({
      category: 'fetch',
      data: { url: 'https://api.houseplant-md.com/api/v1/auth/unsubscribe/check/?token=SECRET' },
    });
    expect(JSON.stringify(crumb)).not.toContain('SECRET');
  });
});

describe('scrubRecordingEvent', () => {
  it('scrubs the page address in a replay meta event', () => {
    const meta = { type: 4, data: { href: CONFIRM, width: 800, height: 600 } };
    expect(scrubRecordingEvent(meta).data).toEqual({
      href: 'https://houseplant-md.com/delete-account/confirm',
      width: 800,
      height: 600,
    });
  });

  it('scrubs URLs in replay custom events (requests and navigations)', () => {
    const custom = {
      type: 5,
      data: {
        tag: 'performanceSpan',
        payload: { op: 'navigation.navigate', description: CONFIRM },
      },
    };
    expect(JSON.stringify(scrubRecordingEvent(custom))).not.toContain('SECRET');
  });

  it('returns page snapshots untouched, by identity', () => {
    const snapshot = { type: 2, data: { node: { id: 1 } } };
    expect(scrubRecordingEvent(snapshot)).toBe(snapshot);
  });
});
