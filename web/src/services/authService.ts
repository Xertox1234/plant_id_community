/**
 * Authentication Service
 *
 * Handles all authentication-related API calls to the Django backend.
 * Uses cookie-based JWT authentication (HttpOnly cookies).
 *
 * API Endpoints (Django backend):
 * - GET  /api/v1/auth/csrf/ (fetch CSRF token)
 * - POST /api/v1/auth/login/
 * - POST /api/v1/auth/register/
 * - POST /api/v1/auth/logout/
 * - GET  /api/v1/auth/user/ (current user)
 */

import { logger } from '../utils/logger';
import { getCsrfToken } from '../utils/csrf';
import { getOrCreateRequestId } from '../utils/requestId';
import type { User, LoginCredentials, SignupData, AuthResponse } from '../types/auth';
import type { ApiError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// HTTPS enforcement for production
if (import.meta.env.PROD && API_URL.startsWith('http://')) {
  logger.error('[authService] SECURITY ERROR: API_URL must use HTTPS in production');
  throw new Error(
    'Cannot send credentials over HTTP in production. Set VITE_API_URL to https:// endpoint.'
  );
}

/**
 * Login user with email and password
 */
export async function login(credentials: LoginCredentials): Promise<User> {
  try {
    // Get CSRF token from centralized utility (handles caching + meta tag/API fallback)
    const csrfToken = await getCsrfToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': getOrCreateRequestId(),
    };

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    const response = await fetch(`${API_URL}/api/v1/auth/login/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      let errorData: Record<string, unknown>;
      try {
        errorData = await response.json();
      } catch {
        // Non-JSON body — an HTML error page. The observed prod trigger
        // (todo 298) is third-party-cookie blocking (Safari/incognito)
        // refusing the CSRF cookie, which Django answers with an HTML 403;
        // never let that parse exception's message ("Unexpected token '<'"
        // in Chrome, "The string did not match the expected pattern" in
        // Safari) reach the UI.
        logger.error('[authService] Non-JSON login error response', {
          status: response.status,
        });
        if (response.status === 403) {
          throw new Error(
            "Login couldn't start — if you're in a private window or Safari, allow cookies for this site and retry."
          );
        }
        throw new Error(`Login failed with status ${response.status}`);
      }

      logger.error('[authService] Login failed:', { status: response.status, error: errorData });

      // Canonical: {message: "..."} — the nested {errors: {detail: "..."}}
      // (e.g. account-lockout retry copy, or the field-level "Username or
      // password is incorrect") is more actionable than the terse top-level
      // message, so it's preferred when present.
      const nestedErrors = errorData.errors as Record<string, unknown> | undefined;
      const message =
        (typeof nestedErrors?.detail === 'string' && nestedErrors.detail) ||
        (typeof errorData.message === 'string' && errorData.message) ||
        'Login failed. Please try again.';

      throw new Error(message);
    }

    // Success-path parse is guarded the same way the error path above is
    // (todo 310). A 200 whose body isn't JSON — an HTML interstitial from a
    // proxy or CDN, a truncated response — would otherwise let the raw
    // `SyntaxError` ("Unexpected token '<'...") escape through the outer
    // catch and reach the UI as `error.message`: the exact failure class
    // todo 298 fixed on the error branch, on the opposite branch.
    let data: AuthResponse;
    try {
      data = await response.json();
      // The shape check belongs INSIDE the guard, not after it. A body that
      // parses but isn't an AuthResponse (a proxy returning literal `null`,
      // an envelope rename) would otherwise reach `data.user` below: `null`
      // throws a raw TypeError that escapes to the UI — the exact class this
      // guard exists to close — and `{}` resolves with `user: undefined`,
      // caching the string "undefined" and returning success for a login that
      // leaves `isAuthenticated` false, so ProtectedLayout bounces straight
      // back to /login with nothing shown.
      if (!data?.user) throw new SyntaxError('login body is not an AuthResponse');
    } catch (parseError) {
      logger.error('[authService] Unreadable login success response', {
        status: response.status,
        error: parseError,
      });
      throw new Error("Login succeeded but the response couldn't be read. Please try again.", {
        cause: parseError,
      });
    }

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user));

    return data.user;
  } catch (error) {
    logger.error('[authService] Login error', { error });
    throw error;
  }
}

/**
 * Sign up new user
 */
export async function signup(userData: SignupData): Promise<User> {
  try {
    // Get CSRF token from centralized utility (handles caching + meta tag/API fallback)
    const csrfToken = await getCsrfToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': getOrCreateRequestId(),
    };

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    const response = await fetch(`${API_URL}/api/v1/auth/register/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      let errorData: Record<string, unknown>;
      try {
        errorData = await response.json();
      } catch {
        throw new Error(`Signup failed with status ${response.status}`);
      }

      logger.error('[authService] Signup failed:', { status: response.status, error: errorData });

      // Canonical: {message: "..."} | DRF detail: {detail: "..."} | DRF field validation: {field: ["msg"]}
      const message =
        (typeof errorData.message === 'string' && errorData.message) ||
        (typeof errorData.detail === 'string' && errorData.detail) ||
        Object.values(errorData)
          .flatMap((v) => (Array.isArray(v) ? v : [v]))
          .find((v): v is string => typeof v === 'string') ||
        `Signup failed with status ${response.status}`;

      throw new Error(message);
    }

    // Same success-path guard as login() (todo 310).
    let data: AuthResponse;
    try {
      data = await response.json();
      // The shape check belongs INSIDE the guard, not after it. A body that
      // parses but isn't an AuthResponse (a proxy returning literal `null`,
      // an envelope rename) would otherwise reach `data.user` below: `null`
      // throws a raw TypeError that escapes to the UI — the exact class this
      // guard exists to close — and `{}` resolves with `user: undefined`,
      // caching the string "undefined" and returning success for a login that
      // leaves `isAuthenticated` false, so ProtectedLayout bounces straight
      // back to /login with nothing shown.
      if (!data?.user) throw new SyntaxError('signup body is not an AuthResponse');
    } catch (parseError) {
      logger.error('[authService] Unreadable signup success response', {
        status: response.status,
        error: parseError,
      });
      throw new Error("Signup succeeded but the response couldn't be read. Please try again.", {
        cause: parseError,
      });
    }

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user));

    return data.user;
  } catch (error) {
    logger.error('[authService] Signup error', { error });
    throw error;
  }
}

/**
 * Logout current user
 * Clears cookie and sessionStorage
 */
export async function logout(): Promise<void> {
  try {
    // Get CSRF token from centralized utility (handles caching + meta tag/API fallback)
    const csrfToken = await getCsrfToken();
    const headers: Record<string, string> = {
      'X-Request-ID': getOrCreateRequestId(),
    };

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    const response = await fetch(`${API_URL}/api/v1/auth/logout/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
    });

    if (!response.ok) {
      logger.warn('[authService] Logout API failed, clearing local state anyway');
    }

    // Always clear sessionStorage regardless of API response
    sessionStorage.removeItem('user');
  } catch (error) {
    logger.error('[authService] Logout error', { error });
    // Still clear sessionStorage even if API fails
    sessionStorage.removeItem('user');
    throw error;
  }
}

/**
 * Get current user from backend
 * Used to verify authentication status on app load
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/user/`, {
      method: 'GET',
      headers: {
        'X-Request-ID': getOrCreateRequestId(),
      },
      credentials: 'include', // Include cookies
    });

    if (!response.ok) {
      // Not authenticated - clear sessionStorage
      sessionStorage.removeItem('user');
      return null;
    }

    // A 200 we cannot read means we learned NOTHING about who the viewer is —
    // which is not the same as learning they are logged out (todo 310).
    //
    // Returning `null` here would assert the latter, and three callers act on
    // that assertion: `AuthContext.revalidateIdentity()` reconciles it with
    // `setUser(null)`, and `NewThreadPage`/`ThreadDetailPage` compute
    // `drifted = (current?.id ?? null) !== actingUserId` AFTER a write has
    // already succeeded (todo 297's defense-in-depth). So one unparseable
    // body following a successful reply would tell the user "Your session
    // changed while replying — you were signed out." for a session that never
    // changed, and then actually sign them out via ProtectedLayout.
    //
    // Returning the last known user is not "promoting a stale identity" — the
    // UI is already showing that user, so this changes nothing; it only
    // declines to update. That is the honest representation of an unknown
    // outcome, and it is what the pre-existing outer catch already did. The
    // guard exists to make the case explicit, logged, and incapable of
    // throwing — not to change the answer.
    //
    // A body that parses but is not a user object (a proxy returning literal
    // `null`, an envelope rename) is the same "cannot read" case: caching it
    // would store a non-user under the 'user' key.
    let data: User;
    try {
      data = await response.json();
      if (!data?.id) throw new SyntaxError('current-user body is not a user object');
    } catch (parseError) {
      logger.error('[authService] Unreadable current-user response', {
        status: response.status,
        error: parseError,
      });
      return getStoredUser();
    }

    // Update sessionStorage with fresh user data
    sessionStorage.setItem('user', JSON.stringify(data));

    return data;
  } catch (error) {
    logger.error('[authService] Get current user error', { error });
    // On error, try to get user from sessionStorage as fallback.
    // Via getStoredUser() rather than an inline `JSON.parse(...)`, which is
    // itself unguarded and throws OUT of this catch block on a corrupt
    // sessionStorage value (todo 310). That matters because
    // `AuthContext.revalidateIdentity()` awaits this on every tab focus with
    // no try/catch of its own — an inline parse turns corrupt storage into an
    // unhandled rejection there. getStoredUser() already has the try/catch.
    return getStoredUser();
  }
}

/**
 * Get user from sessionStorage (synchronous)
 * Used for initial state on app load
 */
export function getStoredUser(): User | null {
  try {
    const storedUser = sessionStorage.getItem('user');
    return storedUser ? JSON.parse(storedUser) : null;
  } catch (error) {
    logger.error('[authService] Error parsing stored user', { error });
    return null;
  }
}

/**
 * Refresh JWT access token using refresh token from cookie
 * SECURITY: Implements OWASP-compliant short access token lifetime (15 minutes)
 * Must be called every 10 minutes to prevent token expiration
 *
 * @returns true if refresh succeeded, false if failed (user should be logged out)
 */
export async function refreshAccessToken(): Promise<boolean> {
  try {
    // Get CSRF token from centralized utility (handles caching + meta tag/API fallback)
    const csrfToken = await getCsrfToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': getOrCreateRequestId(),
    };

    // Add CSRF token (required by backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    const response = await fetch(`${API_URL}/api/v1/auth/token/refresh/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies (refresh token)
    });

    if (!response.ok) {
      logger.warn('[authService] Token refresh failed', { status: response.status });
      return false;
    }

    // Token successfully refreshed (new tokens set in httpOnly cookies)
    logger.info('[authService] Access token refreshed successfully');
    return true;
  } catch (error) {
    logger.error('[authService] Token refresh error', { error });
    return false;
  }
}

/**
 * Begin Google OAuth sign-in.
 *
 * Asks the backend for the Google authorization URL; the caller redirects the
 * browser to it. `credentials: 'include'` is REQUIRED: the backend stores the
 * OAuth `state` (CSRF guard) in the Django session, so the `sessionid` cookie
 * must round-trip to the callback for state validation to pass. In prod this
 * is a cross-site cookie, which the browser only stores when the backend sets
 * `SESSION_COOKIE_SAMESITE=None; Secure` (see todo 240).
 *
 * Endpoint is unversioned (`/api/auth/oauth/...`), not `/api/v1/...`.
 */
export async function getGoogleOAuthUrl(): Promise<string> {
  const response = await fetch(`${API_URL}/api/auth/oauth/google/login/`, {
    method: 'GET',
    headers: {
      'X-Request-ID': getOrCreateRequestId(),
    },
    credentials: 'include', // session cookie carries the OAuth state
  });

  if (!response.ok) {
    let message = 'Google sign-in is currently unavailable. Please try again later.';
    try {
      const data = await response.json();
      if (typeof data?.error === 'string' && data.error) {
        message = data.error;
      }
    } catch {
      // Non-JSON error body — keep the default message.
    }
    logger.error('[authService] Google OAuth init failed', { status: response.status });
    throw new Error(message);
  }

  const data: { oauth_url?: unknown } = await response.json();
  if (typeof data.oauth_url !== 'string' || !data.oauth_url) {
    throw new Error('Google sign-in is currently unavailable. Please try again later.');
  }

  return data.oauth_url;
}

export const authService = {
  login,
  signup,
  logout,
  getCurrentUser,
  getStoredUser,
  refreshAccessToken,
  getGoogleOAuthUrl,
};
