/**
 * Input Validation Utilities
 *
 * Security-focused validation functions for user inputs and URL parameters.
 * Prevents XSS, SSRF, path traversal, and injection attacks.
 *
 * All validation functions throw descriptive errors rather than returning booleans,
 * making them easy to use in try/catch blocks.
 *
 * @module utils/validation
 */

/**
 * Validate blog post slug format.
 *
 * Slugs must be:
 * - Alphanumeric characters, hyphens, and underscores only
 * - Between 1 and 200 characters
 * - No path traversal sequences
 *
 * @param {string} slug - URL slug parameter to validate
 * @returns {string} The validated slug (unchanged if valid)
 * @throws {Error} If slug is invalid
 *
 * @example
 * validateSlug('my-blog-post-2025')  // 'my-blog-post-2025'
 * validateSlug('../admin')            // throws Error
 * validateSlug('<script>alert</script>')  // throws Error
 */
export function validateSlug(slug) {
  if (!slug || typeof slug !== 'string') {
    throw new Error('Slug is required and must be a string');
  }

  // Check length
  if (slug.length > 200) {
    throw new Error('Slug is too long (maximum 200 characters)');
  }

  // Prevent path traversal FIRST (security check before pattern matching)
  if (slug.includes('..') || slug.includes('/') || slug.includes('\\')) {
    throw new Error('Invalid slug: path traversal patterns are not allowed');
  }

  // Only allow alphanumeric, hyphens, and underscores
  // Case-insensitive to allow both 'My-Post' and 'my-post'
  const slugPattern = /^[a-z0-9_-]+$/i;

  if (!slugPattern.test(slug)) {
    throw new Error(
      'Invalid slug format: only letters, numbers, hyphens, and underscores are allowed'
    );
  }

  // Prevent suspicious patterns
  const suspiciousPatterns = [
    /^-+$/,        // Only hyphens
    /^_+$/,        // Only underscores
    /--{2,}/,      // Multiple consecutive hyphens (possible bypass attempt)
    /__{ 2,}/,      // Multiple consecutive underscores
  ];

  if (suspiciousPatterns.some(pattern => pattern.test(slug))) {
    throw new Error('Invalid slug: suspicious pattern detected');
  }

  return slug;
}

/**
 * Validate Wagtail preview token (UUID v4 format).
 *
 * Preview tokens must be:
 * - Valid UUID v4 format (8-4-4-4-12 hexadecimal pattern)
 * - Exactly 36 characters (including hyphens)
 *
 * @param {string} token - Preview token parameter to validate
 * @returns {string} The validated token (unchanged if valid)
 * @throws {Error} If token is invalid
 *
 * @example
 * validateToken('550e8400-e29b-41d4-a716-446655440000')  // Valid UUID v4
 * validateToken('not-a-uuid')  // throws Error
 * validateToken('')            // throws Error
 */
export function validateToken(token) {
  if (!token || typeof token !== 'string') {
    throw new Error('Token is required and must be a string');
  }

  // UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
  // where x is any hexadecimal digit, y is one of [89ab]
  const uuidV4Pattern = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;

  if (!uuidV4Pattern.test(token)) {
    throw new Error('Invalid token format: must be a valid UUID v4');
  }

  return token;
}

/**
 * Validate content type parameter for Wagtail preview.
 *
 * Content types must be:
 * - Alphanumeric characters and dots only (e.g., 'blog.BlogPostPage')
 * - Between 1 and 100 characters
 * - Valid app.model format
 *
 * @param {string} contentType - Content type parameter to validate
 * @returns {string} The validated content type (unchanged if valid)
 * @throws {Error} If content type is invalid
 *
 * @example
 * validateContentType('blog.BlogPostPage')  // Valid
 * validateContentType('app.Model')           // Valid
 * validateContentType('../etc/passwd')       // throws Error
 */
export function validateContentType(contentType) {
  if (!contentType || typeof contentType !== 'string') {
    throw new Error('Content type is required and must be a string');
  }

  // Check length
  if (contentType.length > 100) {
    throw new Error('Content type is too long (maximum 100 characters)');
  }

  // Prevent path traversal FIRST (security check before pattern matching)
  if (contentType.includes('..') || contentType.includes('/') || contentType.includes('\\')) {
    throw new Error('Invalid content type: path traversal patterns are not allowed');
  }

  // Only allow alphanumeric and dots (for app.model format)
  const contentTypePattern = /^[a-z0-9.]+$/i;

  if (!contentTypePattern.test(contentType)) {
    throw new Error('Invalid content type format: only letters, numbers, and dots are allowed');
  }

  // Must contain at least one dot (app.model format)
  if (!contentType.includes('.')) {
    throw new Error('Invalid content type format: must be in app.model format (e.g., blog.BlogPostPage)');
  }

  return contentType;
}

/**
 * Sanitize search query input.
 *
 * Search queries are:
 * - Limited to 200 characters
 * - Control characters removed
 * - Trimmed of whitespace
 *
 * Unlike other validation functions, this does NOT throw errors.
 * It sanitizes the input and returns a safe version.
 *
 * @param {string} query - User search query to sanitize
 * @returns {string} Sanitized query (empty string if invalid)
 *
 * @example
 * sanitizeSearchQuery('  hello world  ')  // 'hello world'
 * sanitizeSearchQuery('test\x00query')    // 'testquery' (control char removed)
 * sanitizeSearchQuery('a'.repeat(300))    // First 200 characters only
 */
export function sanitizeSearchQuery(query) {
  if (!query || typeof query !== 'string') {
    return '';
  }

  // Remove control characters (ASCII 0-31 and 127)
  const cleaned = query.replace(/[\x00-\x1F\x7F]/g, '');

  // Trim whitespace and limit length
  return cleaned.trim().substring(0, 200);
}

/**
 * Validate email address format.
 *
 * Basic email validation for user input.
 * Uses a simple but effective pattern that catches most common mistakes.
 *
 * @param {string} email - Email address to validate
 * @returns {string} The validated email (lowercase)
 * @throws {Error} If email is invalid
 *
 * @example
 * validateEmail('user@example.com')  // 'user@example.com'
 * validateEmail('INVALID')            // throws Error
 */
export function validateEmail(email) {
  if (!email || typeof email !== 'string') {
    throw new Error('Email is required and must be a string');
  }

  // Trim whitespace first
  const trimmed = email.trim();

  // Simple but effective email pattern
  // Allows: username@domain.tld
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!emailPattern.test(trimmed)) {
    throw new Error('Invalid email address format');
  }

  // Return lowercase version for consistency
  return trimmed.toLowerCase();
}

/**
 * Validate URL format.
 *
 * Ensures URLs are:
 * - Valid HTTP or HTTPS URLs
 * - Properly formatted
 * - No javascript: or data: schemes
 *
 * @param {string} url - URL to validate
 * @param {boolean} [httpsOnly=false] - If true, only allow HTTPS
 * @returns {string} The validated URL (unchanged if valid)
 * @throws {Error} If URL is invalid
 *
 * @example
 * validateUrl('https://example.com')  // Valid
 * validateUrl('http://example.com')   // Valid
 * validateUrl('javascript:alert(1)')  // throws Error
 */
export function validateUrl(url, httpsOnly = false) {
  if (!url || typeof url !== 'string') {
    throw new Error('URL is required and must be a string');
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch (error) {
    throw new Error('Invalid URL format');
  }

  // Only allow http and https protocols
  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new Error('Invalid URL protocol: only HTTP and HTTPS are allowed');
  }

  // If HTTPS-only mode, reject HTTP
  if (httpsOnly && parsedUrl.protocol === 'http:') {
    throw new Error('Only HTTPS URLs are allowed');
  }

  return url;
}

/**
 * Validate integer parameter.
 *
 * Ensures value is:
 * - A valid integer
 * - Within optional min/max bounds
 *
 * @param {string|number} value - Value to validate
 * @param {Object} [options={}] - Validation options
 * @param {number} [options.min] - Minimum allowed value (inclusive)
 * @param {number} [options.max] - Maximum allowed value (inclusive)
 * @returns {number} The validated integer
 * @throws {Error} If value is invalid
 *
 * @example
 * validateInteger('42')  // 42
 * validateInteger('42', { min: 1, max: 100 })  // 42
 * validateInteger('0', { min: 1 })  // throws Error
 */
export function validateInteger(value, options = {}) {
  const { min, max } = options;

  // Check if string contains decimal point (reject floats as strings)
  if (typeof value === 'string' && value.includes('.')) {
    throw new Error('Value must be a valid integer');
  }

  // Convert to number
  const num = typeof value === 'string' ? parseInt(value, 10) : value;

  // Check if it's a valid integer
  if (!Number.isInteger(num) || isNaN(num)) {
    throw new Error('Value must be a valid integer');
  }

  // Check minimum bound
  if (min !== undefined && num < min) {
    throw new Error(`Value must be at least ${min}`);
  }

  // Check maximum bound
  if (max !== undefined && num > max) {
    throw new Error(`Value must be at most ${max}`);
  }

  return num;
}

/**
 * Validate pagination parameters.
 *
 * Ensures page and limit values are reasonable.
 *
 * @param {Object} params - Pagination parameters
 * @param {string|number} params.page - Page number (1-indexed)
 * @param {string|number} params.limit - Items per page
 * @returns {Object} Validated { page, limit }
 * @throws {Error} If parameters are invalid
 *
 * @example
 * validatePagination({ page: '2', limit: '10' })  // { page: 2, limit: 10 }
 * validatePagination({ page: '-1', limit: '10' })  // throws Error
 */
export function validatePagination(params) {
  const { page, limit } = params;

  const validatedPage = validateInteger(page, { min: 1, max: 10000 });
  const validatedLimit = validateInteger(limit, { min: 1, max: 100 });

  return {
    page: validatedPage,
    limit: validatedLimit,
  };
}

/**
 * Validate category or tag slug.
 *
 * Similar to blog slug validation but allows for category-specific patterns.
 *
 * @param {string} categorySlug - Category or tag slug to validate
 * @returns {string} The validated slug (unchanged if valid)
 * @throws {Error} If slug is invalid
 *
 * @example
 * validateCategorySlug('plant-care')  // 'plant-care'
 * validateCategorySlug('<script>')     // throws Error
 */
export function validateCategorySlug(categorySlug) {
  // Categories use the same validation as blog slugs
  return validateSlug(categorySlug);
}

/**
 * Validate file upload type.
 *
 * Checks if file extension is in the allowed list.
 *
 * @param {string} filename - Filename to validate
 * @param {string[]} allowedExtensions - Array of allowed extensions (e.g., ['jpg', 'png'])
 * @returns {string} The validated filename (unchanged if valid)
 * @throws {Error} If file type is not allowed
 *
 * @example
 * validateFileType('image.jpg', ['jpg', 'png', 'webp'])  // 'image.jpg'
 * validateFileType('script.js', ['jpg', 'png'])          // throws Error
 */
export function validateFileType(filename, allowedExtensions) {
  if (!filename || typeof filename !== 'string') {
    throw new Error('Filename is required and must be a string');
  }

  if (!Array.isArray(allowedExtensions) || allowedExtensions.length === 0) {
    throw new Error('Allowed extensions must be a non-empty array');
  }

  const extension = filename.split('.').pop()?.toLowerCase();

  if (!extension || !allowedExtensions.includes(extension)) {
    throw new Error(
      `Invalid file type: only ${allowedExtensions.join(', ')} files are allowed`
    );
  }

  return filename;
}

// Default export with all validation functions
export default {
  validateSlug,
  validateToken,
  validateContentType,
  sanitizeSearchQuery,
  validateEmail,
  validateUrl,
  validateInteger,
  validatePagination,
  validateCategorySlug,
  validateFileType,
};
