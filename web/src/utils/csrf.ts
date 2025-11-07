/**
 * CSRF Token Utilities
 *
 * Consolidated CSRF token extraction for Django backend.
 * Replaces 5 duplicate implementations across service files.
 *
 * Usage:
 * ```typescript
 * import { getCsrfToken } from '@/utils/csrf'
 *
 * const token = getCsrfToken()
 * if (token) {
 *   headers['X-CSRFToken'] = token
 * }
 * ```
 */

/**
 * Extract CSRF token from browser cookies
 *
 * Django sets a 'csrftoken' cookie that must be included in
 * POST/PUT/DELETE requests as the X-CSRFToken header.
 *
 * @returns CSRF token string or null if not found
 *
 * @example
 * const token = getCsrfToken()
 * // Returns: "abc123xyz..." or null
 */
export function getCsrfToken(): string | null {
  try {
    const match = document.cookie.match(/csrftoken=([^;]+)/)
    return match ? match[1] : null
  } catch {
    return null
  }
}

export default {
  getCsrfToken,
}
