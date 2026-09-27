import { afterEach, describe, expect, it, vi } from 'vitest';

// Todo 449 item 4: one reader of VITE_API_URL for the whole app.
async function load(url: string | undefined) {
  vi.resetModules();
  vi.stubEnv('VITE_API_URL', url as string);
  return (await import('./api')).API_ORIGIN;
}

describe('API_ORIGIN', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('uses VITE_API_URL', async () => {
    expect(await load('https://api.example.test')).toBe('https://api.example.test');
  });

  it('strips trailing slashes so `${API_ORIGIN}/api/...` never doubles one', async () => {
    expect(await load('https://api.example.test//')).toBe('https://api.example.test');
  });

  it('refuses a plain-http origin in a production build', async () => {
    vi.stubEnv('PROD', true);
    await expect(load('http://api.example.test')).rejects.toThrow(/HTTP in production/);
  });

  it('allows an https origin in a production build', async () => {
    vi.stubEnv('PROD', true);
    expect(await load('https://api.example.test')).toBe('https://api.example.test');
  });

  it('falls back to the local backend when unset', async () => {
    expect(await load('')).toBe('http://localhost:8000');
  });
});
