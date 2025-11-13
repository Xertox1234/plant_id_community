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
import type { User, LoginCredentials, SignupData, AuthResponse } from '../types/auth';
import type { ApiError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// HTTPS enforcement for production
if (import.meta.env.PROD && API_URL.startsWith('http://')) {
  logger.error('[authService] SECURITY ERROR: API_URL must use HTTPS in production');
  throw new Error('Cannot send credentials over HTTP in production. Set VITE_API_URL to https:// endpoint.');
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
      const error = await response.json();
      throw new Error(error.message || 'Login failed');
    }

    const data: AuthResponse = await response.json();

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user));

    return data.user;
  } catch (error) {
    logger.error('[authService] Login error:', error);
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
      let errorData: ApiError | { error?: { message?: string }; message?: string };
      try {
        errorData = await response.json();
      } catch (e) {
        throw new Error(`Signup failed with status ${response.status}`);
      }

      // Log detailed error for debugging
      logger.error('[authService] Signup failed:', {
        status: response.status,
        error: errorData
      });

      // Extract error message from backend
      const errorMessage = ('error' in errorData && errorData.error && typeof errorData.error === 'object' && 'message' in errorData.error)
        ? errorData.error.message
        : ('message' in errorData ? errorData.message : JSON.stringify(errorData));
      throw new Error(errorMessage);
    }

    const data: AuthResponse = await response.json();

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user));

    return data.user;
  } catch (error) {
    logger.error('[authService] Signup error:', error);
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
    const headers: Record<string, string> = {};

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
    logger.error('[authService] Logout error:', error);
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
      credentials: 'include', // Include cookies
    });

    if (!response.ok) {
      // Not authenticated - clear sessionStorage
      sessionStorage.removeItem('user');
      return null;
    }

    const data: User = await response.json();

    // Update sessionStorage with fresh user data
    sessionStorage.setItem('user', JSON.stringify(data));

    return data;
  } catch (error) {
    logger.error('[authService] Get current user error:', error);
    // On error, try to get user from sessionStorage as fallback
    const storedUser = sessionStorage.getItem('user');
    return storedUser ? JSON.parse(storedUser) : null;
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
    logger.error('[authService] Error parsing stored user:', error);
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
      logger.warn('[authService] Token refresh failed:', response.status);
      return false;
    }

    // Token successfully refreshed (new tokens set in httpOnly cookies)
    logger.info('[authService] Access token refreshed successfully');
    return true;
  } catch (error) {
    logger.error('[authService] Token refresh error:', error);
    return false;
  }
}

export const authService = {
  login,
  signup,
  logout,
  getCurrentUser,
  getStoredUser,
  refreshAccessToken,
};
