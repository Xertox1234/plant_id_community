/**
 * web/public/robots.txt (forum audit F213). Vite copies web/public into
 * web/dist, and Cloudflare serves it at /robots.txt. Without the file the SPA
 * fallback answers /robots.txt with index.html, so crawlers never learn where
 * the forum sitemap is. The sitemap lives on the API origin
 * (`.railway/railway.ts` domain + the `forum/sitemap.xml` route in
 * backend/plant_community_backend/urls.py).
 */
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';

const ROBOTS_FILE = path.resolve(__dirname, '../../public/robots.txt');

describe('robots.txt', () => {
  it('exists in web/public so the build ships it', () => {
    expect(existsSync(ROBOTS_FILE)).toBe(true);
  });

  it('names the forum sitemap on the API origin and blocks nothing', () => {
    const lines = readFileSync(ROBOTS_FILE, 'utf8')
      .split('\n')
      .map((l) => l.trim());
    expect(lines).toContain('Sitemap: https://api.houseplant-md.com/forum/sitemap.xml');
    expect(lines).toContain('User-agent: *');
    expect(lines.filter((l) => /^disallow:\s*\S/i.test(l))).toEqual([]);
  });
});
