/**
 * Input Sanitization Utilities
 *
 * Provides XSS protection for user input across the application.
 * Uses DOMPurify for HTML sanitization.
 *
 * IMPORTANT: Client-side sanitization is defense-in-depth only.
 * Always validate and sanitize on the server side as well.
 */

import DOMPurify from 'dompurify'

/**
 * Sanitize form input (email, name, password fields)
 * Strips all HTML tags to prevent XSS in form fields
 *
 * @param {string} input - User input to sanitize
 * @returns {string} Sanitized input with no HTML tags
 *
 * @example
 * const email = sanitizeInput(formData.email)
 * // "<script>alert('xss')</script>" → "alert('xss')"
 */
export function sanitizeInput(input) {
  if (!input || typeof input !== 'string') {
    return input
  }

  // Strip ALL HTML tags from form inputs (email, password, name)
  const cleaned = DOMPurify.sanitize(input, {
    ALLOWED_TAGS: [], // No HTML allowed in form inputs
    ALLOWED_ATTR: [],
  })

  return cleaned.trim()
}

/**
 * Sanitize HTML content (for displaying rich text safely)
 * Allows safe HTML tags but removes scripts and dangerous attributes
 *
 * @param {string} html - HTML content to sanitize
 * @returns {string} Sanitized HTML
 *
 * @example
 * const safeHTML = sanitizeHTML(serverResponse.content)
 * // Safe: <p>Hello</p>
 * // Blocked: <script>alert('xss')</script>
 */
export function sanitizeHTML(html) {
  if (!html || typeof html !== 'string') {
    return html
  }

  // Allow safe HTML tags but remove dangerous content
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3',
      'blockquote', 'code', 'pre',
    ],
    ALLOWED_ATTR: ['href', 'title', 'class'],
  })
}

/**
 * Sanitize error messages from server
 * Prevents XSS if server includes user input in error messages
 *
 * @param {string} error - Error message from server
 * @returns {string} Sanitized error message
 *
 * @example
 * const safeError = sanitizeError(apiResponse.error)
 * // "Email 'user@example.com' already exists" → safe
 * // "Email '<script>xss</script>' already exists" → script removed
 */
export function sanitizeError(error) {
  if (!error || typeof error !== 'string') {
    return error
  }

  // Strip all HTML from error messages
  return DOMPurify.sanitize(error, {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  })
}

export default {
  sanitizeInput,
  sanitizeHTML,
  sanitizeError,
}
