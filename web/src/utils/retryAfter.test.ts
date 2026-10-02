import { describe, it, expect } from 'vitest';
import { describeWait, readRetryAfter } from './retryAfter';

describe('readRetryAfter', () => {
  it('reads the delta-seconds form', () => {
    const response = { headers: new Headers({ 'Retry-After': '900' }) } as Response;
    expect(readRetryAfter(response)).toBe(900);
  });

  it('tolerates surrounding whitespace', () => {
    const response = {
      headers: { get: (name: string) => (name === 'Retry-After' ? ' 60 ' : null) },
    } as unknown as Response;
    expect(readRetryAfter(response)).toBe(60);
  });

  it('returns null for an absent header, the HTTP-date form, or a response with no Headers object', () => {
    expect(readRetryAfter({ headers: new Headers() } as Response)).toBeNull();
    expect(
      readRetryAfter({
        headers: new Headers({ 'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT' }),
      } as Response)
    ).toBeNull();
    // A hand-rolled test response — the error path must not throw on it.
    expect(readRetryAfter({} as Response)).toBeNull();
  });
});

describe('describeWait', () => {
  it.each([
    [1, '1 second'],
    [45, '45 seconds'],
    [59, '59 seconds'],
  ])('%i s under a minute is whole seconds, pluralized', (seconds, text) => {
    expect(describeWait(seconds)).toBe(text);
  });

  it.each([
    [60, '1 minute'],
    [61, '2 minutes'],
    [90, '2 minutes'],
    [3600, '60 minutes'],
  ])('%i s is minutes rounded UP, pluralized', (seconds, text) => {
    expect(describeWait(seconds)).toBe(text);
  });
});
