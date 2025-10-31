/**
 * Centralized Sanitization Utilities
 *
 * Provides XSS protection for user input and rich content across the application.
 * Uses DOMPurify for HTML sanitization with preset configurations.
 *
 * IMPORTANT: Client-side sanitization is defense-in-depth only.
 * Always validate and sanitize on the server side as well.
 *
 * Usage:
 * - Form inputs: Use stripHtml() or sanitizeInput()
 * - Blog excerpts: Use SANITIZE_PRESETS.BASIC or SANITIZE_PRESETS.MINIMAL
 * - Blog content: Use SANITIZE_PRESETS.STANDARD or SANITIZE_PRESETS.FULL
 * - StreamField blocks: Use SANITIZE_PRESETS.STREAMFIELD
 */

import DOMPurify from 'dompurify'
import { logger } from './logger'

/**
 * Sanitization Preset Configurations
 *
 * Provides consistent XSS protection across all components.
 * Choose the most restrictive preset that meets your needs.
 */
export const SANITIZE_PRESETS = {
  /**
   * MINIMAL: Only basic inline formatting
   * Use for: Simple text excerpts, user comments
   * Allows: p, br, strong, em, u
   */
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u'],
    ALLOWED_ATTR: [],
  },

  /**
   * BASIC: Basic formatting + links
   * Use for: Blog card excerpts, short descriptions
   * Allows: MINIMAL + a (links)
   */
  BASIC: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  },

  /**
   * STANDARD: Rich text formatting
   * Use for: Blog introductions, user-generated content
   * Allows: BASIC + headings, lists, blockquote
   */
  STANDARD: {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'u',
      'a',
      'ul',
      'ol',
      'li',
      'h2',
      'h3',
      'h4',
      'blockquote',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  },

  /**
   * FULL: All safe content blocks
   * Use for: Full blog posts, documentation
   * Allows: STANDARD + code, pre, img
   */
  FULL: {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'u',
      'a',
      'ul',
      'ol',
      'li',
      'h1',
      'h2',
      'h3',
      'h4',
      'blockquote',
      'code',
      'pre',
      'img',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt', 'title'],
  },

  /**
   * STREAMFIELD: Wagtail StreamField blocks
   * Use for: StreamFieldRenderer component
   * Allows: FULL + additional formatting for rich content blocks
   */
  STREAMFIELD: {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'u',
      'a',
      'ul',
      'ol',
      'li',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'blockquote',
      'code',
      'pre',
      'img',
      'span',
      'div',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt', 'title', 'id'],
  },

  /**
   * FORUM: Rich forum posts with mentions, code blocks, images
   * Use for: Forum posts, thread content
   * Allows: FULL + mentions, code blocks, custom classes for syntax highlighting
   */
  FORUM: {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'u',
      'a',
      'ul',
      'ol',
      'li',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'blockquote',
      'code',
      'pre',
      'img',
      'span',
      'div',
    ],
    ALLOWED_ATTR: [
      'href',
      'target',
      'rel',
      'class',
      'src',
      'alt',
      'title',
      'data-mention',
      'data-mention-id',
    ],
    ALLOWED_CLASSES: {
      span: ['mention'],
      code: ['language-*'],
      div: ['code-block'],
    },
    ALLOW_DATA_ATTR: false,
  },
}

/**
 * Sanitize HTML content with preset or custom configuration
 *
 * @param {string} html - HTML content to sanitize
 * @param {object} options - DOMPurify options (defaults to STANDARD preset)
 * @returns {string} Sanitized HTML
 *
 * @example
 * // Using preset
 * const safe = sanitizeHtml(html, SANITIZE_PRESETS.BASIC)
 *
 * // Custom config
 * const safe = sanitizeHtml(html, { ALLOWED_TAGS: ['p', 'br'] })
 *
 * // Default (STANDARD preset)
 * const safe = sanitizeHtml(html)
 */
export function sanitizeHtml(html, options = null) {
  if (!html || typeof html !== 'string') {
    return ''
  }

  try {
    // Use STANDARD preset by default
    const config = options || SANITIZE_PRESETS.STANDARD
    return DOMPurify.sanitize(html, config)
  } catch (error) {
    logger.error('DOMPurify sanitization failed', {
      component: 'sanitize',
      error,
      context: { htmlLength: html?.length },
    })
    return ''
  }
}

/**
 * Create safe markup object for React's dangerouslySetInnerHTML
 *
 * @param {string} html - HTML content to sanitize
 * @param {object} options - DOMPurify options (defaults to STANDARD preset)
 * @returns {object} Object with __html property containing sanitized HTML
 *
 * @example
 * <div dangerouslySetInnerHTML={createSafeMarkup(content, SANITIZE_PRESETS.FULL)} />
 */
export function createSafeMarkup(html, options = null) {
  return {
    __html: sanitizeHtml(html, options),
  }
}

/**
 * Strip all HTML tags, returning only text content
 * Use for: Search indexing, excerpts, plain text display
 *
 * @param {string} html - HTML content to strip
 * @returns {string} Plain text with all HTML removed
 *
 * @example
 * const text = stripHtml('<p>Hello <strong>world</strong>!</p>')
 * // Returns: "Hello world!"
 */
export function stripHtml(html) {
  if (!html || typeof html !== 'string') {
    return ''
  }

  // DOMPurify with ALLOWED_TAGS: [] strips all HTML
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  }).trim()
}

/**
 * Check if HTML contains potentially dangerous content
 * Returns true if HTML is safe, false if suspicious patterns detected
 *
 * @param {string} html - HTML to check
 * @returns {boolean} True if safe, false if dangerous patterns found
 *
 * @example
 * if (!isSafeHtml(userInput)) {
 *   console.warn('Suspicious content detected')
 * }
 */
export function isSafeHtml(html) {
  if (!html || typeof html !== 'string') {
    return true
  }

  // Patterns that indicate XSS attempts
  const dangerousPatterns = [
    /<script[^>]*>/i,
    /javascript:/i,
    /vbscript:/i,
    /data:text\/html/i,
    /on\w+\s*=/i, // onclick, onerror, etc.
    /<iframe/i,
    /eval\(/i,
  ]

  return !dangerousPatterns.some((pattern) => pattern.test(html))
}

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

  // Strip ALL HTML tags from form inputs
  return stripHtml(input)
}

/**
 * Sanitize HTML content (for displaying rich text safely)
 * Allows safe HTML tags but removes scripts and dangerous attributes
 *
 * @param {string} html - HTML content to sanitize
 * @returns {string} Sanitized HTML
 * @deprecated Use sanitizeHtml() with presets instead
 *
 * @example
 * const safeHTML = sanitizeHTML(serverResponse.content)
 * // Safe: <p>Hello</p>
 * // Blocked: <script>alert('xss')</script>
 */
export function sanitizeHTML(html) {
  return sanitizeHtml(html, SANITIZE_PRESETS.STANDARD)
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
  return stripHtml(error)
}

export default {
  sanitizeInput,
  sanitizeHTML,
  sanitizeHtml,
  sanitizeError,
  createSafeMarkup,
  stripHtml,
  isSafeHtml,
  SANITIZE_PRESETS,
}
