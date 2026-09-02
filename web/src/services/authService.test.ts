/**
 * Authentication Service Tests
 *
 * Comprehensive tests for auth service covering:
 * - Login flow with CSRF protection
 * - Registration with validation
 * - Logout and session cleanup
 * - Current user fetching
 * - Error handling and network failures
 *
 * Priority: P1 - CRITICAL (Authentication is core to application security)
 * Coverage Target: 100% branch coverage
 * Estimated Test Count: 18 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  login,
  signup,
  logout,
  getCurrentUser,
  getStoredUser,
  getGoogleOAuthUrl,
} from './authService';
import { clearCsrfToken } from '../utils/csrf';
import type { User, LoginCredentials, SignupData, AuthResponse } from '../types/auth';

// Mock logger to prevent console noise in tests
vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('authService', () => {
  // Test fixtures
  const mockUser: User = {
    id: 1,
    email: 'test@example.com',
    username: 'testuser',
    name: 'Test User',
    display_name: 'TestUser',
    trust_level: 'basic',
    date_joined: '2025-01-01T00:00:00Z',
    is_active: true,
    is_staff: false,
    is_moderator: false,
  };

  const mockLoginCredentials: LoginCredentials = {
    email: 'test@example.com',
    password: 'testpassword123',
  };

  const mockSignupData: SignupData = {
    username: 'testuser',
    first_name: 'Test',
    last_name: 'User',
    email: 'test@example.com',
    password: 'testpassword123',
  };

  const mockAuthResponse: AuthResponse = {
    user: mockUser,
  };

  // Mock implementations
  let fetchMock: ReturnType<typeof vi.fn>;
  let sessionStorageMock: {
    getItem: ReturnType<typeof vi.fn>;
    setItem: ReturnType<typeof vi.fn>;
    removeItem: ReturnType<typeof vi.fn>;
    clear: ReturnType<typeof vi.fn>;
  };
  let documentCookieMock: string;

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    // Mock sessionStorage
    sessionStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'sessionStorage', {
      value: sessionStorageMock,
      writable: true,
    });

    // Mock document.cookie
    documentCookieMock = 'csrftoken=test-csrf-token';
    Object.defineProperty(document, 'cookie', {
      get: () => documentCookieMock,
      set: (value: string) => {
        documentCookieMock = value;
      },
      configurable: true,
    });

    clearCsrfToken();
    document.head.querySelector('meta[name="csrf-token"]')?.remove();
    const csrfMeta = document.createElement('meta');
    csrfMeta.setAttribute('name', 'csrf-token');
    csrfMeta.setAttribute('content', 'test-csrf-token');
    document.head.appendChild(csrfMeta);

    // Clear all mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearCsrfToken();
    document.head.querySelector('meta[name="csrf-token"]')?.remove();
    vi.restoreAllMocks();
  });

  // ============================================================================
  // LOGIN TESTS
  // ============================================================================

  describe('login', () => {
    it('should authenticate with valid credentials', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      const result = await login(mockLoginCredentials);

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/login/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-CSRFToken': 'test-csrf-token',
            'X-Request-ID': expect.any(String),
          }),
          credentials: 'include',
          body: JSON.stringify(mockLoginCredentials),
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
    });

    it('should fetch CSRF token if not present in cookie', async () => {
      // Arrange
      documentCookieMock = ''; // No CSRF token
      document.head.querySelector('meta[name="csrf-token"]')?.remove();
      clearCsrfToken();

      // Mock CSRF fetch
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrfToken: 'fetched-csrf-token' }),
      });

      // Mock login
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await login(mockLoginCredentials);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/csrf/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
        })
      );
    });

    it('should handle invalid credentials (401)', async () => {
      // Arrange — matches apps.users.views.create_error_response's real shape:
      // every login failure branch, including this one, sets `errors.detail`.
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({
          message: 'Invalid credentials',
          errors: { detail: 'Username or password is incorrect' },
        }),
      });

      // Act & Assert — the nested detail (the field-level, actionable copy)
      // is preferred over the terse top-level message.
      await expect(login(mockLoginCredentials)).rejects.toThrow(
        'Username or password is incorrect'
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.any(String));
    });

    it('should fall back to the top-level message when errors.detail is absent', async () => {
      // Arrange — a non-standard/older error shape without the nested detail.
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ message: 'Invalid email or password' }),
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Invalid email or password');
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.any(String));
    });

    it('should handle network errors with retry logic', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Network error');
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.any(String));
    });

    it('should include CSRF token in request headers', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await login(mockLoginCredentials);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle missing error message gracefully', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}), // No message
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Login failed');
    });

    // todo 298: a blocked CSRF cookie (Safari/incognito third-party-cookie
    // blocking) gets Django's HTML 403 page, not JSON. response.json() then
    // throws a parse exception whose message ("Unexpected token '<'" in
    // Chrome, "The string did not match the expected pattern" in Safari) must
    // never reach the UI — this is the live prod repro (2026-08-13).
    it('should show a friendly cookie message for a non-JSON 403 (blocked CSRF cookie)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => {
          throw new Error('Unexpected token \'<\', "<!DOCTYPE "... is not valid JSON');
        },
      });

      // Act & Assert
      const err = await login(mockLoginCredentials).catch((e) => e);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).not.toMatch(/unexpected token|did not match the expected pattern/i);
      expect(err.message).toContain('private window or Safari');
    });

    it('should fall back to a status-coded message for a non-403 non-JSON error', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Login failed with status 502');
    });

    // todo 310: the mirror image of the 298 fix above — a 200 whose body is
    // not JSON (an HTML interstitial from a proxy/CDN, a truncated response).
    // The raw SyntaxError must not reach the UI through the outer catch.
    it('should show a friendly message for a malformed 200 body, not the parse error', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => {
          // A REAL SyntaxError — what response.json() actually throws. A
          // hand-rolled `new Error(...)` passes against a narrowed catch and a
          // bare one alike, so it cannot tell the two apart.
          throw new SyntaxError('Unexpected token \'<\', "<!DOCTYPE "... is not valid JSON');
        },
      });

      // Act & Assert
      const err = await login(mockLoginCredentials).catch((e) => e);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).not.toMatch(/unexpected token|did not match the expected pattern/i);
      expect(err.message).toBe(
        "Login succeeded but the response couldn't be read. Please try again."
      );
      // Nothing was cached from a body we could not read. Scoped to the
      // 'user' key: getOrCreateRequestId() also writes to sessionStorage on
      // every request, so a bare not.toHaveBeenCalled() asserts the wrong thing.
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    // Review finding 3. A 200 that PARSES but isn't an AuthResponse — a proxy
    // returning literal `null`, an envelope rename, API version skew. The
    // `data.user` deref used to sit OUTSIDE the guard, so this escaped it.
    it('should reject a 200 that parses to null rather than throw a raw TypeError', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => null });

      // Act & Assert — unguarded this is "Cannot read properties of null
      // (reading 'user')" rendered on the form, the exact class todo 310 closes.
      const err = await login(mockLoginCredentials).catch((e) => e);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).not.toMatch(/cannot read propert/i);
      expect(err.message).toBe(
        "Login succeeded but the response couldn't be read. Please try again."
      );
    });

    // The silent-loop case: `{}` throws nothing, so unguarded this RESOLVES
    // with `user: undefined`, caches the string "undefined", and reports
    // success for a login that leaves isAuthenticated false — ProtectedLayout
    // then bounces straight back to /login with no error shown.
    it('should reject a 200 whose body has no user key instead of resolving', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow(
        "Login succeeded but the response couldn't be read. Please try again."
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    it('should prefer the nested errors.detail (retry-hint copy) over the terse top-level message', async () => {
      // Arrange — matches apps.users.views.create_error_response's real shape
      // for account lockout: {message: "Account locked", errors: {detail: "..."}}
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({
          message: 'Account locked',
          errors: {
            detail:
              'Too many failed login attempts. Your account has been temporarily locked for security. Check your email for details.',
          },
        }),
      });

      // Act & Assert
      await expect(login(mockLoginCredentials)).rejects.toThrow('Too many failed login attempts');
    });
  });

  // ============================================================================
  // SIGNUP TESTS
  // ============================================================================

  describe('signup', () => {
    it('should create new user account', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      const result = await signup(mockSignupData);

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/register/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'X-CSRFToken': 'test-csrf-token',
            'X-Request-ID': expect.any(String),
          }),
          credentials: 'include',
          body: JSON.stringify(mockSignupData),
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
    });

    it('should validate CSRF token is present', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await signup(mockSignupData);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle duplicate email error (409)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ message: 'Email already exists' }),
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow('Email already exists');
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.any(String));
    });

    it('should handle validation errors (400)', async () => {
      // Arrange
      const validationError = {
        error: true,
        message: 'Password must be at least 8 characters',
      };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => validationError,
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow(
        'Password must be at least 8 characters'
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.any(String));
    });

    it('should handle non-JSON error responses', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow('Signup failed with status 500');
    });

    // todo 310 — same shape as login()'s malformed-200 case.
    it('should show a friendly message for a malformed 200 body, not the parse error', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => {
          // A REAL SyntaxError — what response.json() actually throws. A
          // hand-rolled `new Error(...)` passes against a narrowed catch and a
          // bare one alike, so it cannot tell the two apart.
          throw new SyntaxError('Unexpected token \'<\', "<!DOCTYPE "... is not valid JSON');
        },
      });

      // Act & Assert
      const err = await signup(mockSignupData).catch((e) => e);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).not.toMatch(/unexpected token|did not match the expected pattern/i);
      expect(err.message).toBe(
        "Signup succeeded but the response couldn't be read. Please try again."
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    // Review finding 3. A 200 that PARSES but isn't an AuthResponse — a proxy
    // returning literal `null`, an envelope rename, API version skew. The
    // `data.user` deref used to sit OUTSIDE the guard, so this escaped it.
    it('should reject a 200 that parses to null rather than throw a raw TypeError', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => null });

      // Act & Assert — unguarded this is "Cannot read properties of null
      // (reading 'user')" rendered on the form, the exact class todo 310 closes.
      const err = await signup(mockSignupData).catch((e) => e);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).not.toMatch(/cannot read propert/i);
      expect(err.message).toBe(
        "Signup succeeded but the response couldn't be read. Please try again."
      );
    });

    // The silent-loop case: `{}` throws nothing, so unguarded this RESOLVES
    // with `user: undefined`, caches the string "undefined", and reports
    // success for a login that leaves isAuthenticated false — ProtectedLayout
    // then bounces straight back to /login with no error shown.
    it('should reject a 200 whose body has no user key instead of resolving', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });

      // Act & Assert
      await expect(signup(mockSignupData)).rejects.toThrow(
        "Signup succeeded but the response couldn't be read. Please try again."
      );
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    it('should fetch CSRF token if not present', async () => {
      // Arrange
      documentCookieMock = ''; // No CSRF token
      document.head.querySelector('meta[name="csrf-token"]')?.remove();
      clearCsrfToken();

      // Mock CSRF fetch
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrfToken: 'fetched-csrf-token' }),
      });

      // Mock signup
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAuthResponse,
      });

      // Act
      await signup(mockSignupData);

      // Assert
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/csrf/'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // LOGOUT TESTS
  // ============================================================================

  describe('logout', () => {
    it('should clear sessionStorage and call logout endpoint', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      // Act
      await logout();

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/logout/'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-CSRFToken': 'test-csrf-token',
            'X-Request-ID': expect.any(String),
          }),
          credentials: 'include',
        })
      );
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should clear sessionStorage even if API fails', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      // Act
      await logout();

      // Assert
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should clear sessionStorage even on network error', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      // Act & Assert
      await expect(logout()).rejects.toThrow('Network error');
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });
  });

  // ============================================================================
  // GET CURRENT USER TESTS
  // ============================================================================

  describe('getCurrentUser', () => {
    it('should fetch user profile with valid authentication', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/user/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include',
        })
      );
      expect(sessionStorageMock.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
    });

    it('should return null and clear sessionStorage if not authenticated (401)', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toBeNull();
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should fallback to sessionStorage on network error', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));
      sessionStorageMock.getItem.mockImplementation((key: string) =>
        key === 'user' ? JSON.stringify(mockUser) : null
      );

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.getItem).toHaveBeenCalledWith('user');
    });

    it('should return null if sessionStorage fallback is empty', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));
      sessionStorageMock.getItem.mockReturnValueOnce(null);

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toBeNull();
    });

    // todo 310, corrected after code review. An unreadable 200 means we learned
    // NOTHING about the identity — not that the viewer is logged out. Returning
    // null would assert the latter, and NewThreadPage/ThreadDetailPage compute
    // `drifted = (current?.id ?? null) !== actingUserId` AFTER a write already
    // succeeded (todo 297), so it would show "Your session changed while
    // replying — you were signed out." for a session that never changed, and
    // then really sign them out. The last known user is the honest answer.
    it('should return the last known user on an unreadable 200, so drift detection stays quiet', async () => {
      // Arrange
      sessionStorageMock.getItem.mockImplementation((key: string) =>
        key === 'user' ? JSON.stringify(mockUser) : null
      );
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => {
          // A REAL SyntaxError, which is what response.json() actually throws
          // — a hand-rolled `new Error(...)` would pass against a narrowed
          // catch and a bare one alike, so it cannot tell them apart.
          throw new SyntaxError('Unexpected token \'<\', "<!DOCTYPE "... is not valid JSON');
        },
      });

      // Act
      const result = await getCurrentUser();

      // Assert — same id the caller was acting as, so `drifted` is false.
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.removeItem).not.toHaveBeenCalledWith('user');
      // Nothing unreadable was written back over the cache.
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    // A body that parses but isn't a user object is the same "cannot read"
    // case — caching it would put a non-user under the 'user' key.
    it('should treat a 200 that parses to null as unreadable, not as a logout', async () => {
      // Arrange
      sessionStorageMock.getItem.mockImplementation((key: string) =>
        key === 'user' ? JSON.stringify(mockUser) : null
      );
      fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => null });

      // Act
      const result = await getCurrentUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('user', expect.anything());
    });

    // The genuine "server says you are not authenticated" signal must still
    // clear and return null — otherwise the above would have neutered it.
    it('should still clear the cache and return null on a real 401', async () => {
      // Arrange
      sessionStorageMock.getItem.mockImplementation((key: string) =>
        key === 'user' ? JSON.stringify(mockUser) : null
      );
      fetchMock.mockResolvedValueOnce({ ok: false, status: 401 });

      // Act & Assert
      await expect(getCurrentUser()).resolves.toBeNull();
      expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('user');
    });

    it('should return null rather than throw when the sessionStorage fallback holds corrupt JSON', async () => {
      // Arrange
      fetchMock.mockRejectedValueOnce(new Error('Network error'));
      sessionStorageMock.getItem.mockImplementation((key: string) =>
        key === 'user' ? '{not valid json' : null
      );

      // Act & Assert — resolves, never rejects
      await expect(getCurrentUser()).resolves.toBeNull();
    });
  });

  // ============================================================================
  // GET STORED USER TESTS (Synchronous)
  // ============================================================================

  describe('getStoredUser', () => {
    it('should return user from sessionStorage', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce(JSON.stringify(mockUser));

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toEqual(mockUser);
      expect(sessionStorageMock.getItem).toHaveBeenCalledWith('user');
    });

    it('should return null if sessionStorage is empty', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce(null);

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toBeNull();
    });

    it('should handle invalid JSON gracefully', () => {
      // Arrange
      sessionStorageMock.getItem.mockReturnValueOnce('invalid-json');

      // Act
      const result = getStoredUser();

      // Assert
      expect(result).toBeNull();
    });
  });

  // ============================================================================
  // GOOGLE OAUTH TESTS
  // ============================================================================

  describe('getGoogleOAuthUrl', () => {
    it('returns the backend-provided oauth_url and sends cookies', async () => {
      // Arrange
      const oauthUrl = 'https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&state=xyz';
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ oauth_url: oauthUrl, provider: 'google' }),
      });

      // Act
      const result = await getGoogleOAuthUrl();

      // Assert
      expect(result).toBe(oauthUrl);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/oauth/google/login/'),
        expect.objectContaining({
          method: 'GET',
          credentials: 'include', // session cookie carries the OAuth state
        })
      );
    });

    it('throws the backend error message on a non-OK response', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ error: 'Google OAuth not configured' }),
      });

      // Act & Assert
      await expect(getGoogleOAuthUrl()).rejects.toThrow('Google OAuth not configured');
    });

    it('throws when the response omits oauth_url', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ provider: 'google' }),
      });

      // Act & Assert
      await expect(getGoogleOAuthUrl()).rejects.toThrow(/unavailable/i);
    });

    it('falls back to the default message when a non-OK body is not JSON', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => {
          throw new Error('not json');
        },
      });

      // Act & Assert
      await expect(getGoogleOAuthUrl()).rejects.toThrow(/unavailable/i);
    });
  });
});
