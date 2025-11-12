/**
 * CSRF Token Utilities (Issue #013 Fix - Django Standard Meta Tag Pattern)
 *
 * Reads CSRF token from Django-rendered meta tag instead of cookies.
 * This allows CSRF_COOKIE_HTTPONLY = True for better XSS protection.
 *
 * Security Benefits:
 * - CSRF cookie is HttpOnly (JavaScript cannot read it)
 * - Token read from meta tag (injected by Django template)
 * - XSS attacks cannot steal CSRF token from cookie
 * - Defense-in-depth: HttpOnly cookie + meta tag access
 *
 * Django Template Pattern:
 * ```django
 * <!-- templates/react_app.html -->
 * <meta name="csrf-token" content="{{ csrf_token }}">
 * ```
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
 * Get CSRF token using Django standard meta tag pattern
 *
 * Priority:
 * 1. Meta tag (preferred - Django standard)
 * 2. API endpoint (fallback for backward compatibility)
 *
 * This is more secure than reading from cookies because:
 * 1. Allows CSRF_COOKIE_HTTPONLY = True (prevents XSS theft)
 * 2. Official Django recommendation for SPAs
 * 3. Single source of truth (no cookie parsing bugs)
 * 4. Works with Django's CSRF middleware
 *
 * @returns Promise<string | null> - CSRF token or null if not found
 *
 * @example
 * const token = await getCsrfToken()
 * // First call: Reads from meta tag or fetches from API
 * // Subsequent calls: Returns cached value
 */
export async function getCsrfToken(): Promise<string | null> {
  // Return cached token if available
  if (csrfToken) {
    return csrfToken
  }

  // Strategy 1: Try meta tag first (Django standard pattern)
  const meta = document.querySelector('meta[name="csrf-token"]')
  if (meta) {
    csrfToken = meta.getAttribute('content')
    if (csrfToken) {
      console.log('[CSRF] Token loaded from meta tag (Django standard pattern)')
      return csrfToken
    }
  }

  // Strategy 2: Fallback to API endpoint (backward compatibility)
  console.warn('[CSRF] Meta tag not found, falling back to API endpoint')
  try {
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const response = await fetch(`${API_URL}/api/csrf/`, {
      method: 'GET',
      credentials: 'include', // Required to receive CSRF cookie
    })

    if (!response.ok) {
      console.error('[CSRF] Failed to fetch token from API:', response.status)
      return null
    }

    const data = await response.json()
    csrfToken = data.csrfToken

    console.log('[CSRF] Token loaded from API endpoint (fallback)')
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
 * Note: When using meta tag pattern, you'll need to reload the page
 * to get a new token, as meta tags are rendered server-side.
 *
 * @example
 * if (response.status === 403) {
 *   clearCsrfToken()
 *   const newToken = await getCsrfToken() // Will try meta tag again
 *   if (!newToken) {
 *     // Meta tag didn't help, reload page for new token
 *     window.location.reload()
 *   }
 * }
 */
export function clearCsrfToken(): void {
  csrfToken = null
}

export default {
  getCsrfToken,
  clearCsrfToken,
}
