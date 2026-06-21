/**
 * Form Validation Utilities
 *
 * Client-side validation functions for common form fields.
 * These provide user feedback but should NOT replace server-side validation.
 *
 * Covers:
 * - Search query sanitization (forum search input)
 * - Emails and passwords (auth forms)
 */

/**
 * Sanitize search query
 * Removes: Control characters, excess whitespace
 */
export function sanitizeSearchQuery(query: unknown): string {
  if (!query || typeof query !== 'string') {
    return '';
  }

  // Remove control characters (U+0000 to U+001F, U+007F)
  // eslint-disable-next-line no-control-regex -- intentionally strips ASCII control characters from user search input
  const sanitized = query.replace(/[\x00-\x1F\x7F]/g, '').trim();

  // Limit length
  return sanitized.slice(0, 200);
}

/**
 * Validate email address format
 */
export function validateEmail(email: unknown): string {
  // Null/undefined/empty check
  if (!email || typeof email !== 'string' || email.trim() === '') {
    throw new Error('Email is required and must be a string');
  }

  const trimmed = email.trim().toLowerCase();

  // Basic email regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) {
    throw new Error('Invalid email address format');
  }

  return trimmed;
}

/**
 * Validate password strength
 */
export function validatePassword(password: string): boolean {
  if (!password || typeof password !== 'string') {
    return false;
  }

  // Minimum 14 characters (Django backend requirement)
  return password.length >= 14;
}

/**
 * Validate required field
 */
export function validateRequired(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === 'string') {
    return value.trim().length > 0;
  }

  return true;
}

/**
 * Validate passwords match
 */
export function validatePasswordMatch(password: string, confirmPassword: string): boolean {
  return password === confirmPassword && password.length > 0;
}

/**
 * Get validation error message for email
 */
export function getEmailError(email: string): string | null {
  if (!validateRequired(email)) {
    return 'Email is required';
  }

  try {
    validateEmail(email);
    return null;
  } catch (error) {
    if (error instanceof Error) {
      return error.message;
    }
    return 'Please enter a valid email address';
  }
}

/**
 * Get validation error message for password
 */
export function getPasswordError(password: string): string | null {
  if (!validateRequired(password)) {
    return 'Password is required';
  }

  if (!validatePassword(password)) {
    return 'Password must be at least 14 characters long';
  }

  return null;
}

/**
 * Get validation error message for password confirmation
 */
export function getPasswordConfirmError(password: string, confirmPassword: string): string | null {
  if (!validateRequired(confirmPassword)) {
    return 'Please confirm your password';
  }

  if (!validatePasswordMatch(password, confirmPassword)) {
    return 'Passwords do not match';
  }

  return null;
}
