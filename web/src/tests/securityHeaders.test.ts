/**
 * web/public/_headers (todo 706, audit 2026-11-10 M2). Cloudflare serves these
 * headers on every page; Vite copies the file into web/dist. A wrong
 * frame-ancestors breaks the Wagtail CMS preview, which frames /blog/preview
 * from the API origin, so the directive is asserted exactly.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';

// Resolved from this file, not the cwd, so any runner location reads the same file.
const HEADERS_FILE = path.resolve(__dirname, '../../public/_headers');

/** Header name (lower-case) -> value, for the `/*` rule block. */
function headersForAllPaths(text: string): Map<string, string> {
  const headers = new Map<string, string>();
  let inBlock = false;
  for (const line of text.split('\n')) {
    if (line.trim() === '' || line.trimStart().startsWith('#')) continue;
    if (!/^\s/.test(line)) {
      inBlock = line.trim() === '/*';
      continue;
    }
    if (!inBlock) continue;
    const colon = line.indexOf(':');
    headers.set(line.slice(0, colon).trim().toLowerCase(), line.slice(colon + 1).trim());
  }
  return headers;
}

function directives(csp: string): Map<string, string> {
  return new Map(
    csp
      .split(';')
      .map((d) => d.trim())
      .filter(Boolean)
      .map((d) => {
        const [name, ...values] = d.split(/\s+/);
        return [name.toLowerCase(), values.join(' ')] as [string, string];
      })
  );
}

describe('web/public/_headers', () => {
  const headers = headersForAllPaths(readFileSync(HEADERS_FILE, 'utf8'));

  it('sets Referrer-Policy and X-Content-Type-Options on every path', () => {
    expect(headers.get('referrer-policy')).toBe('strict-origin-when-cross-origin');
    expect(headers.get('x-content-type-options')).toBe('nosniff');
  });

  it('ships the CSP report-only, never enforcing yet', () => {
    expect(headers.has('content-security-policy-report-only')).toBe(true);
    expect(headers.has('content-security-policy')).toBe(false);
  });

  it('lets only this site and the CMS origin frame the app', () => {
    const csp = directives(headers.get('content-security-policy-report-only') ?? '');
    expect(csp.get('frame-ancestors')).toBe("'self' https://api.houseplant-md.com");
  });

  it('sets no X-Frame-Options, which would block the CMS preview', () => {
    expect(headers.has('x-frame-options')).toBe(false);
  });
});
