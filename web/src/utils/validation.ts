/**
 * Form Validation Utilities
 *
 * Client-side validation functions for common form fields.
 * These provide user feedback but should NOT replace server-side validation.
 *
 * Security-focused validation for:
 * - Slugs (blog posts, categories)
 * - Tokens (UUID v4)
 * - Content types (Wagtail)
 * - Search queries
 * - Emails, URLs, integers
 * - File types
 */

/**
 * Validate slug format (alphanumeric, hyphens, underscores only)
 * Prevents: XSS, path traversal, SQL injection
 */
export function validateSlug(slug: unknown): string {
  // Null/undefined/empty check
  if (!slug || typeof slug !== 'string' || slug.trim() === '') {
    throw new Error('Slug is required and must be a string')
  }

  // Length check
  if (slug.length > 200) {
    throw new Error('Slug is too long (maximum 200 characters)')
  }

  // Path traversal check
  if (slug.includes('..') || slug.includes('/') || slug.includes('\\')) {
    throw new Error('Invalid slug: path traversal patterns are not allowed')
  }

  // Suspicious pattern check (repeated delimiters)
  if (/---/.test(slug) || /___/.test(slug)) {
    throw new Error('Invalid slug: suspicious pattern detected')
  }

  // Format check (only alphanumeric, hyphens, underscores)
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) {
    throw new Error('Invalid slug format')
  }

  return slug
}

/**
 * Validate UUID v4 token format
 * Prevents: Path traversal, XSS
 */
export function validateToken(token: unknown): string {
  // Null/undefined/empty check
  if (!token || typeof token !== 'string' || token.trim() === '') {
    throw new Error('Token is required and must be a string')
  }

  // UUID v4 format check
  const uuidV4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  if (!uuidV4Regex.test(token)) {
    throw new Error('Invalid token format: must be a valid UUID v4')
  }

  return token
}

/**
 * Validate content type format (app.Model)
 * Prevents: Path traversal, XSS
 */
export function validateContentType(contentType: unknown): string {
  // Null/undefined/empty check
  if (!contentType || typeof contentType !== 'string' || contentType.trim() === '') {
    throw new Error('Content type is required and must be a string')
  }

  // Length check
  if (contentType.length > 100) {
    throw new Error('Content type is too long (maximum 100 characters)')
  }

  // Path traversal check
  if (contentType.includes('..') || contentType.includes('/') || contentType.includes('\\')) {
    throw new Error('Invalid content type: path traversal patterns are not allowed')
  }

  // Format check (app.Model format - alphanumeric, underscores, and dot)
  if (!/^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$/.test(contentType)) {
    if (!contentType.includes('.')) {
      throw new Error('Invalid content type format: must be in app.model format')
    }
    throw new Error('Invalid content type format')
  }

  return contentType
}

/**
 * Sanitize search query
 * Removes: Control characters, excess whitespace
 */
export function sanitizeSearchQuery(query: unknown): string {
  if (!query || typeof query !== 'string') {
    return ''
  }

  // Remove control characters (U+0000 to U+001F, U+007F)
  const sanitized = query.replace(/[\x00-\x1F\x7F]/g, '').trim()

  // Limit length
  return sanitized.slice(0, 200)
}

/**
 * Validate email address format
 */
export function validateEmail(email: unknown): string {
  // Null/undefined/empty check
  if (!email || typeof email !== 'string' || email.trim() === '') {
    throw new Error('Email is required and must be a string')
  }

  const trimmed = email.trim().toLowerCase()

  // Basic email regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(trimmed)) {
    throw new Error('Invalid email address format')
  }

  return trimmed
}

/**
 * Validate URL format (HTTP/HTTPS only)
 * Prevents: XSS (javascript:), SSRF (file:, ftp:)
 */
export function validateUrl(url: unknown, httpsOnly: boolean = false): string {
  // Null/undefined/empty check
  if (!url || typeof url !== 'string' || url.trim() === '') {
    throw new Error('URL is required and must be a string')
  }

  let parsedUrl: URL
  try {
    parsedUrl = new URL(url)
  } catch {
    throw new Error('Invalid URL format')
  }

  // Protocol check (only http/https allowed)
  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    throw new Error('Invalid URL protocol: only HTTP and HTTPS are allowed')
  }

  // HTTPS-only mode
  if (httpsOnly && parsedUrl.protocol !== 'https:') {
    throw new Error('Only HTTPS URLs are allowed')
  }

  return url
}

/**
 * Validate integer value
 */
export function validateInteger(
  value: unknown,
  options: { min?: number; max?: number } = {}
): number {
  // Check if string contains decimal point (float)
  if (typeof value === 'string' && value.includes('.')) {
    throw new Error('Value must be a valid integer')
  }

  // Convert string to number if needed
  const num = typeof value === 'string' ? parseInt(value, 10) : value

  // Check if valid number
  if (typeof num !== 'number' || isNaN(num) || !isFinite(num)) {
    throw new Error('Value must be a valid integer')
  }

  // Check if integer (not float)
  if (!Number.isInteger(num)) {
    throw new Error('Value must be a valid integer')
  }

  // Min/max bounds
  if (options.min !== undefined && num < options.min) {
    throw new Error(`Value must be at least ${options.min}`)
  }

  if (options.max !== undefined && num > options.max) {
    throw new Error(`Value must be at most ${options.max}`)
  }

  return num
}

/**
 * Validate pagination parameters
 */
export function validatePagination(params: {
  page: string | number
  limit: string | number
}): { page: number; limit: number } {
  const page = validateInteger(params.page, { min: 1, max: 10000 })
  const limit = validateInteger(params.limit, { min: 1, max: 100 })

  return { page, limit }
}

/**
 * Validate category slug (alias for validateSlug)
 */
export function validateCategorySlug(slug: unknown): string {
  return validateSlug(slug)
}

/**
 * Validate file type by extension
 */
export function validateFileType(filename: unknown, allowedExtensions: unknown): string {
  // Filename check
  if (!filename || typeof filename !== 'string' || filename.trim() === '') {
    throw new Error('Filename is required and must be a string')
  }

  // Allowed extensions check
  if (!Array.isArray(allowedExtensions) || allowedExtensions.length === 0) {
    throw new Error('Allowed extensions must be a non-empty array')
  }

  // Extract extension
  const parts = filename.split('.')
  if (parts.length < 2) {
    throw new Error(`Invalid file type: only ${allowedExtensions.join(', ')} files are allowed`)
  }

  const extension = parts[parts.length - 1].toLowerCase()

  // Check if extension is allowed
  const allowed = allowedExtensions.map((ext) => String(ext).toLowerCase())
  if (!allowed.includes(extension)) {
    throw new Error(`Invalid file type: only ${allowedExtensions.join(', ')} files are allowed`)
  }

  return filename
}

/**
 * Validate password strength
 */
export function validatePassword(password: string): boolean {
  if (!password || typeof password !== 'string') {
    return false
  }

  // Minimum 14 characters (Django backend requirement)
  return password.length >= 14
}

/**
 * Validate required field
 */
export function validateRequired(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false
  }

  if (typeof value === 'string') {
    return value.trim().length > 0
  }

  return true
}

/**
 * Validate passwords match
 */
export function validatePasswordMatch(password: string, confirmPassword: string): boolean {
  return password === confirmPassword && password.length > 0
}

/**
 * Get validation error message for email
 */
export function getEmailError(email: string): string | null {
  if (!validateRequired(email)) {
    return 'Email is required'
  }

  try {
    validateEmail(email)
    return null
  } catch (error) {
    if (error instanceof Error) {
      return error.message
    }
    return 'Please enter a valid email address'
  }
}

/**
 * Get validation error message for password
 */
export function getPasswordError(password: string): string | null {
  if (!validateRequired(password)) {
    return 'Password is required'
  }

  if (!validatePassword(password)) {
    return 'Password must be at least 14 characters long'
  }

  return null
}

/**
 * Get validation error message for name
 */
export function getNameError(name: string): string | null {
  if (!validateRequired(name)) {
    return 'Name is required'
  }

  if (name.trim().length < 2) {
    return 'Name must be at least 2 characters long'
  }

  return null
}

/**
 * Get validation error message for password confirmation
 */
export function getPasswordConfirmError(password: string, confirmPassword: string): string | null {
  if (!validateRequired(confirmPassword)) {
    return 'Please confirm your password'
  }

  if (!validatePasswordMatch(password, confirmPassword)) {
    return 'Passwords do not match'
  }

  return null
}
