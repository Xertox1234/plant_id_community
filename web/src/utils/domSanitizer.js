/**
 * DOM Sanitizer Utility (Async Wrapper)
 *
 * Re-exports centralized sanitization utilities from sanitize.js.
 * This file is maintained for backward compatibility with components
 * that use async imports (like StreamFieldRenderer).
 *
 * @deprecated Consider importing directly from './sanitize' for synchronous usage.
 * The async pattern was originally used for code splitting, but DOMPurify is
 * already included in the main bundle via sanitize.js.
 */

import {
  sanitizeHtml as syncSanitizeHtml,
  createSafeMarkup as syncCreateSafeMarkup,
  SANITIZE_PRESETS,
} from './sanitize'

/**
 * Sanitizes HTML content to prevent XSS attacks.
 * Async wrapper for backward compatibility.
 *
 * @param {string} html - The HTML content to sanitize
 * @param {object} options - DOMPurify configuration options
 * @returns {Promise<string>} Sanitized HTML string
 */
export async function sanitizeHTML(html, options = {}) {
  // Convert to synchronous call wrapped in Promise for API compatibility
  return Promise.resolve(syncSanitizeHtml(html, options))
}

/**
 * Creates a safe markup object for React's dangerouslySetInnerHTML.
 * Async wrapper for backward compatibility.
 *
 * @param {string} html - The HTML content to sanitize
 * @param {object} options - DOMPurify configuration options
 * @returns {Promise<object>} Object with __html property containing sanitized HTML
 */
export async function createSafeMarkup(html, options = {}) {
  // Convert to synchronous call wrapped in Promise for API compatibility
  return Promise.resolve(syncCreateSafeMarkup(html, options))
}

// Re-export presets for convenience
export { SANITIZE_PRESETS }
