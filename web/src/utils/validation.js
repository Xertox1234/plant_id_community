/**
 * Form Validation Utilities
 *
 * Client-side validation functions for common form fields.
 * These provide user feedback but should NOT replace server-side validation.
 */

/**
 * Validate email address format
 * @param {string} email - Email address to validate
 * @returns {boolean} True if valid email format
 */
export function validateEmail(email) {
  if (!email || typeof email !== 'string') {
    return false
  }

  // Basic email regex - matches most common email formats
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email.trim())
}

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {boolean} True if password meets minimum requirements
 */
export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return false
  }

  // Minimum 8 characters
  return password.length >= 8
}

/**
 * Validate required field
 * @param {string} value - Value to validate
 * @returns {boolean} True if value is not empty
 */
export function validateRequired(value) {
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
 * @param {string} password - Original password
 * @param {string} confirmPassword - Confirmation password
 * @returns {boolean} True if passwords match
 */
export function validatePasswordMatch(password, confirmPassword) {
  return password === confirmPassword && password.length > 0
}

/**
 * Get validation error message for email
 * @param {string} email - Email to validate
 * @returns {string|null} Error message or null if valid
 */
export function getEmailError(email) {
  if (!validateRequired(email)) {
    return 'Email is required'
  }

  if (!validateEmail(email)) {
    return 'Please enter a valid email address'
  }

  return null
}

/**
 * Get validation error message for password
 * @param {string} password - Password to validate
 * @returns {string|null} Error message or null if valid
 */
export function getPasswordError(password) {
  if (!validateRequired(password)) {
    return 'Password is required'
  }

  if (!validatePassword(password)) {
    return 'Password must be at least 8 characters long'
  }

  return null
}

/**
 * Get validation error message for name
 * @param {string} name - Name to validate
 * @returns {string|null} Error message or null if valid
 */
export function getNameError(name) {
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
 * @param {string} password - Original password
 * @param {string} confirmPassword - Confirmation password
 * @returns {string|null} Error message or null if valid
 */
export function getPasswordConfirmError(password, confirmPassword) {
  if (!validateRequired(confirmPassword)) {
    return 'Please confirm your password'
  }

  if (!validatePasswordMatch(password, confirmPassword)) {
    return 'Passwords do not match'
  }

  return null
}
