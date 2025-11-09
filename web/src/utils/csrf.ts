/**
 * CSRF Token Utilities (Issue #144 Fix - Secure Pattern)
 *
 * Fetches CSRF token from Django backend API endpoint instead of reading cookies.
 * This allows CSRF_COOKIE_HTTPONLY = True for better XSS protection.
 *
 * Security:
 * - CSRF cookie is now HttpOnly (JavaScript cannot read it)
 * - Token fetched from dedicated API endpoint
 * - Cached in memory to avoid repeated API calls
 * - Automatic refresh on 403 CSRF errors
 *
 * Usage:
 * ```typescript
 * import { getCsrfToken } from '@/utils/csrf'
 *
 * const token = await getCsrfToken()
 * if (token) {
 *   headers['X-CSRFToken'] = token
 * }
 * ```
 */

// In-memory cache for CSRF token (single source of truth)
let csrfToken: string | null = null

/**
 * Get CSRF token from Django backend API
 *
 * Fetches the CSRF token from /api/csrf/ endpoint and caches it in memory.
 * On subsequent calls, returns the cached value.
 *
 * This is more secure than reading from cookies because:
 * 1. Allows CSRF_COOKIE_HTTPONLY = True (prevents XSS theft)
 * 2. Single source of truth (no cookie parsing bugs)
 * 3. Works with Django's CSRF middleware
 *
 * @returns Promise<string | null> - CSRF token or null if fetch fails
 *
 * @example
 * const token = await getCsrfToken()
 * // First call: Fetches from API
 * // Subsequent calls: Returns cached value
 */
export async function getCsrfToken(): Promise<string | null> {
  // Return cached token if available
  if (csrfToken) {
    return csrfToken
  }

  try {
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const response = await fetch(`${API_URL}/api/csrf/`, {
      method: 'GET',
      credentials: 'include', // Required to receive CSRF cookie
    })

    if (!response.ok) {
      console.error('[CSRF] Failed to fetch token:', response.status)
      return null
    }

    const data = await response.json()
    csrfToken = data.csrfToken

    return csrfToken
  } catch (error) {
    console.error('[CSRF] Error fetching token:', error)
    return null
  }
}

/**
 * Clear cached CSRF token
 *
 * Call this when you receive a 403 CSRF error to force token refresh.
 *
 * @example
 * if (response.status === 403) {
 *   clearCsrfToken()
 *   const newToken = await getCsrfToken()
 * }
 */
export function clearCsrfToken(): void {
  csrfToken = null
}

export default {
  getCsrfToken,
  clearCsrfToken,
}
