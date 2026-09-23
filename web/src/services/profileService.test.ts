import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchProfile, updateProfile } from './profileService';
import { getCsrfToken } from '../utils/csrf';

vi.mock('../utils/csrf', () => ({ getCsrfToken: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

describe('profileService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('reads the profile from /api/v1/auth/user/ with cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1, username: 'ada' }));

    await expect(fetchProfile()).resolves.toMatchObject({ username: 'ada' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/user\/$/);
    expect(init.credentials).toBe('include');
  });

  it('PATCHes changes to /api/v1/auth/user/update/ with the CSRF token, returning the user', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ message: 'Profile updated successfully', user: { id: 1, bio: 'Ferns' } })
    );

    await expect(updateProfile({ bio: 'Ferns' })).resolves.toEqual({ id: 1, bio: 'Ferns' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/user\/update\/$/);
    expect(init.method).toBe('PATCH');
    expect(init.headers['X-CSRFToken']).toBe('csrf-123');
    expect(JSON.parse(init.body)).toEqual({ bio: 'Ferns' });
  });

  it('turns a DRF field-error map into one readable message', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ website: ['Enter a valid URL.'] }, 400));

    await expect(updateProfile({ website: 'nope' })).rejects.toThrow('website: Enter a valid URL.');
  });

  it('prefers a flattened {message} error body', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ message: 'Invalid first name' }, 400));

    await expect(updateProfile({ first_name: 'x' })).rejects.toThrow('Invalid first name');
  });
});
