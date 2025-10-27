import DOMPurify from 'dompurify';

/**
 * HTML Sanitization Utilities
 *
 * Provides centralized XSS protection for all rich text content.
 * Uses DOMPurify to sanitize HTML with configurable whitelists.
 *
 * @module utils/sanitize
 */

/**
 * Default allowed HTML tags for blog content.
 * Conservative whitelist for maximum security.
 */
const DEFAULT_ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 'a',
  'ul', 'ol', 'li', 'blockquote',
  'h2', 'h3', 'h4', 'h5', 'h6',
  'code', 'pre'
];

/**
 * Default allowed HTML attributes.
 * Only permit safe attributes for links and styling.
 */
const DEFAULT_ALLOWED_ATTR = [
  'href', 'target', 'rel', 'class'
];

/**
 * Sanitization presets for different use cases.
 */
export const SANITIZE_PRESETS = {
  /**
   * Minimal: Only basic text formatting (p, strong, em)
   */
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u'],
    ALLOWED_ATTR: [],
  },

  /**
   * Basic: Text formatting + links
   */
  BASIC: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  },

  /**
   * Standard: Basic + lists + blockquotes
   */
  STANDARD: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'blockquote'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  },

  /**
   * Full: All safe tags including headings and code blocks
   */
  FULL: {
    ALLOWED_TAGS: DEFAULT_ALLOWED_TAGS,
    ALLOWED_ATTR: DEFAULT_ALLOWED_ATTR,
  },
};

/**
 * Create sanitized HTML markup safe for React's dangerouslySetInnerHTML.
 *
 * This function provides XSS protection by sanitizing HTML content
 * using DOMPurify with a configurable whitelist of allowed tags and attributes.
 *
 * @param {string} html - The raw HTML content to sanitize
 * @param {Object} options - DOMPurify configuration options
 * @param {string[]} [options.ALLOWED_TAGS] - Array of allowed HTML tag names
 * @param {string[]} [options.ALLOWED_ATTR] - Array of allowed HTML attributes
 * @param {RegExp} [options.ALLOWED_URI_REGEXP] - Regex for allowed URI schemes
 * @returns {Object} Object with __html property for dangerouslySetInnerHTML
 *
 * @example
 * // Basic usage with default settings
 * <div dangerouslySetInnerHTML={createSafeMarkup(post.introduction)} />
 *
 * @example
 * // With custom allowed tags
 * const markup = createSafeMarkup(content, {
 *   ALLOWED_TAGS: ['p', 'strong', 'a'],
 *   ALLOWED_ATTR: ['href']
 * });
 *
 * @example
 * // Using a preset
 * const markup = createSafeMarkup(content, SANITIZE_PRESETS.MINIMAL);
 */
export function createSafeMarkup(html, options = {}) {
  if (!html || typeof html !== 'string') {
    return { __html: '' };
  }

  const config = {
    ALLOWED_TAGS: DEFAULT_ALLOWED_TAGS,
    ALLOWED_ATTR: DEFAULT_ALLOWED_ATTR,
    // Prevent javascript: and data: URIs in href attributes
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    // Explicitly forbid dangerous event handlers
    FORBID_ATTR: ['onerror', 'onclick', 'onload', 'onmouseover'],
    ...options,
  };

  try {
    const sanitized = DOMPurify.sanitize(html, config);
    return { __html: sanitized };
  } catch (error) {
    console.error('[Sanitize] Error sanitizing HTML:', error);
    return { __html: '' };
  }
}

/**
 * Sanitize HTML and return as plain string (not React-safe object).
 * Useful for non-React contexts or when you need the raw sanitized HTML.
 *
 * @param {string} html - The raw HTML content to sanitize
 * @param {Object} options - DOMPurify configuration options
 * @returns {string} Sanitized HTML string
 *
 * @example
 * const cleanHtml = sanitizeHtml('<p>Hello <script>alert("xss")</script></p>');
 * // Returns: '<p>Hello </p>'
 */
export function sanitizeHtml(html, options = {}) {
  if (!html || typeof html !== 'string') {
    return '';
  }

  const config = {
    ALLOWED_TAGS: DEFAULT_ALLOWED_TAGS,
    ALLOWED_ATTR: DEFAULT_ALLOWED_ATTR,
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    FORBID_ATTR: ['onerror', 'onclick', 'onload', 'onmouseover'],
    ...options,
  };

  try {
    return DOMPurify.sanitize(html, config);
  } catch (error) {
    console.error('[Sanitize] Error sanitizing HTML:', error);
    return '';
  }
}

/**
 * Strip all HTML tags from a string.
 * Returns plain text only, removing all markup.
 *
 * This is safer than using regex patterns like .replace(/<[^>]*>/g, '')
 * because it uses DOMPurify to properly parse and strip HTML.
 *
 * @param {string} html - The HTML content to strip
 * @returns {string} Plain text with all HTML removed
 *
 * @example
 * const text = stripHtml('<p>Hello <strong>world</strong>!</p>');
 * // Returns: 'Hello world!'
 *
 * @example
 * // Creating an excerpt
 * const excerpt = stripHtml(post.introduction).substring(0, 200) + '...';
 */
export function stripHtml(html) {
  if (!html || typeof html !== 'string') {
    return '';
  }

  try {
    // Sanitize with NO allowed tags = strips all HTML
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [],
      KEEP_CONTENT: true,  // Keep text content, just remove tags
    }).trim();
  } catch (error) {
    console.error('[Sanitize] Error stripping HTML:', error);
    return '';
  }
}

/**
 * Check if a string contains potentially malicious content.
 * Returns true if the HTML appears to be safe (no dangerous patterns detected).
 *
 * Note: This is not a replacement for sanitization! Always sanitize before rendering.
 * This is useful for validation/logging purposes.
 *
 * @param {string} html - The HTML content to check
 * @returns {boolean} True if content appears safe, false if suspicious patterns detected
 *
 * @example
 * if (!isSafeHtml(userInput)) {
 *   console.warn('Suspicious HTML detected in user input');
 * }
 */
export function isSafeHtml(html) {
  if (!html || typeof html !== 'string') {
    return true;
  }

  // Patterns that indicate potential XSS attempts
  const suspiciousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+\s*=/i,  // Event handlers: onclick=, onload=, etc.
    /<iframe/i,
    /eval\(/i,
    /expression\(/i,  // CSS expressions (IE)
    /import\s+/i,
    /vbscript:/i,
    /data:text\/html/i,
  ];

  return !suspiciousPatterns.some(pattern => pattern.test(html));
}

export default {
  createSafeMarkup,
  sanitizeHtml,
  stripHtml,
  isSafeHtml,
  SANITIZE_PRESETS,
};
